"""A5: IP клиента берётся из X-Forwarded-For, а не из адреса nginx.

Без ProxyFix `request.remote_addr` в проде — IP nginx-контейнера. Тогда
`AuditLog.ip_address` одинаков для всех клиентов, а rate-limit делит один
лимит между всеми. Проверяем оба следствия на реальном коде, а не на факте
наличия middleware.
"""

import secrets
from datetime import datetime, timedelta, timezone

from shared.models import db
from shared.models.user import User
from shared.rbac.models import AuditLog, SessionToken

FORWARDED_IP = '203.0.113.77'


def _user_with_token(app, username='proxy_probe', role='custom'):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, password_hash='x', role=role, is_active=True)
            db.session.add(user)
            db.session.commit()
        token = secrets.token_hex(32)
        db.session.add(SessionToken(
            user_id=user.id,
            token_hash=SessionToken.hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.session.commit()
    return token


def test_audit_log_records_forwarded_ip(app, client):
    """IP из X-Forwarded-For попадает в audit_log, а не адрес прокси."""
    token = _user_with_token(app)

    resp = client.post(
        '/api/auth/logout',
        headers={'Authorization': f'Bearer {token}', 'X-Forwarded-For': FORWARDED_IP},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)

    with app.app_context():
        row = (
            AuditLog.query.filter_by(action='logout')
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert row is not None, 'выход не оставил следа в audit_log'
        assert row.ip_address == FORWARDED_IP, (
            f'в аудит записан {row.ip_address!r} вместо IP клиента '
            f'{FORWARDED_IP!r} — ProxyFix не применён'
        )


def test_rate_limit_keys_on_forwarded_ip(app, client):
    """Разные X-Forwarded-For — разные корзины лимита (не общая на всех)."""
    # /api/version не в skip-листе before_request, поэтому проходит rate-limit.
    ips_in = ('198.51.100.1', '198.51.100.2')
    for ip in ips_in:
        client.get('/api/version', headers={'X-Forwarded-For': ip})

    from sqlalchemy import text
    with app.app_context():
        rows = db.session.execute(
            text("SELECT DISTINCT ip_address FROM rate_limit WHERE ip_address IS NOT NULL")
        ).fetchall()
    keys = {r[0] for r in rows}

    for ip in ips_in:
        assert ip in keys, (
            f'корзина лимита для {ip} не создана; в таблице {sorted(keys)!r} — '
            'значит rate-limit ключуется на IP прокси, а не клиента'
        )


def test_proxy_fix_installed_in_both_factories(app):
    """Прод-фабрика и тестовая обязаны вести себя одинаково."""
    from werkzeug.middleware.proxy_fix import ProxyFix

    assert isinstance(app.wsgi_app, ProxyFix), 'create_test_app без ProxyFix'

    import ast
    import os
    src = open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py'),
        encoding='utf-8',
    ).read()
    tree = ast.parse(src)
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert 'install_proxy_fix' in calls, 'create_app не вызывает install_proxy_fix'
