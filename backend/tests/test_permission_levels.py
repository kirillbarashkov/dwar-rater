"""A2: уровень 'read' не должен открывать действия уровня write/admin.

Дефект: SSE-эндпоинты и force_refresh проверяли только `!= 'none'`, поэтому
пользователь с уровнем `read` проходил гейт `admin`/`write` — то есть получал
право запускать импорт и тратить ресурсы. `require_permission` такое же
сочетание блокирует, поэтому две ветки проверки расходились.
"""

import secrets

import pytest

from shared.models import db
from shared.models.user import User
from shared.rbac.models import UserPermission, Permission


def _make_user_with_level(app, username, grants):
    """Создать активного пользователя с заданными уровнями прав.

    grants: список (feature, action, level). Роль 'custom' — чтобы права
    выдавались только явно, без побочных full от роли 'user'/'admin'.
    """
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            UserPermission.query.filter_by(user_id=user.id).delete()
        else:
            user = User(
                username=username,
                password_hash='x',
                role='custom',
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

        granted = {}
        for feature, action, level in grants:
            perm = Permission.query.filter_by(feature=feature, action=action).first()
            assert perm is not None, f'нет права {feature}:{action} в сиде'
            db.session.add(
                UserPermission(user_id=user.id, permission_id=perm.id, level=level)
            )
            granted[f'{feature}:{action}'] = level
        db.session.commit()

        token = secrets.token_hex(32)
        from datetime import datetime, timedelta, timezone
        from shared.rbac.models import SessionToken
        db.session.add(SessionToken(
            user_id=user.id,
            token_hash=SessionToken.hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.session.commit()

    return token, granted


def _sse_is_forbidden(resp):
    """SSE-эндпоинт отвечает 200 и стримит событие error/forbidden."""
    body = resp.get_data(as_text=True)
    return '"reason": "forbidden"' in body or '"reason":"forbidden"' in body


# ---------------------------------------------------------------------------
# SSE: уровень read НЕ должен проходить гейт admin
# ---------------------------------------------------------------------------

def test_treasury_sse_refuses_read_level(app, client):
    token, _ = _make_user_with_level(app, 'reader_treasury', [('treasury', 'admin', 'read')])
    resp = client.get(
        '/api/clan/1/treasury/auto-fetch-stream',
        query_string={'token': token},
    )
    assert _sse_is_forbidden(resp), (
        'уровень read на treasury:admin открыл SSE-импорт казны'
    )


def test_members_sse_refuses_read_level(app, client):
    token, _ = _make_user_with_level(app, 'reader_members', [('clan_info', 'admin', 'read')])
    resp = client.get(
        '/api/clan/1/members/auto-fetch-stream',
        query_string={'token': token},
    )
    assert _sse_is_forbidden(resp), (
        'уровень read на clan_info:admin открыл SSE-импорт состава'
    )


def test_level_events_sse_refuses_read_level(app, client):
    token, _ = _make_user_with_level(app, 'reader_events', [('clan_info', 'admin', 'read')])
    resp = client.get(
        '/api/clan/1/level-events/import-stream',
        query_string={'token': token},
    )
    assert _sse_is_forbidden(resp), (
        'уровень read на clan_info:admin открыл SSE-импорт уровней'
    )


# ---------------------------------------------------------------------------
# force_refresh: уровень read на analyze:write не должен проходить
# ---------------------------------------------------------------------------

def test_force_refresh_refuses_read_level(app, client):
    token, _ = _make_user_with_level(app, 'reader_analyze', [('analyze', 'write', 'read')])
    resp = client.post(
        '/api/tracks/generate',
        json={'target_type': 'character', 'target_ref': 'X', 'force_refresh': True},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 403, (
        f'уровень read на analyze:write открыл force_refresh (было {resp.status_code})'
    )


def test_analyze_force_refresh_refuses_read_level(app, client):
    token, _ = _make_user_with_level(app, 'reader_analyze2', [('analyze', 'write', 'read')])
    resp = client.post(
        '/api/analyze',
        json={'url': 'https://dwar.ru/char/1/', 'force_refresh': True},
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == 403, (
        f'уровень read на analyze:write открыл force_refresh в /api/analyze '
        f'(было {resp.status_code})'
    )


# ---------------------------------------------------------------------------
# Контроль: full по-прежнему проходит гейт (иначе фикс сломал бы доступ)
# ---------------------------------------------------------------------------

def test_full_level_still_passes_the_gate(app, client):
    token, _ = _make_user_with_level(app, 'full_treasury', [('treasury', 'admin', 'full')])
    resp = client.get(
        '/api/clan/1/treasury/auto-fetch-stream',
        query_string={'token': token},
    )
    assert not _sse_is_forbidden(resp), 'уровень full обязан проходить гейт admin'


def test_has_permission_helper_matches_require_permission():
    """Хелпер и декоратор обязаны применять одно и то же правило."""
    from shared.rbac import has_permission, _level_allows

    for action in ('write', 'delete', 'admin', 'approve'):
        assert not _level_allows('read', action), f'read не должен давать {action}'
        assert _level_allows('full', action), f'full должен давать {action}'
    for action in ('read',):
        assert _level_allows('read', action)
        assert _level_allows('full', action)
    for action in ('read', 'write', 'admin'):
        assert not _level_allows('none', action)
