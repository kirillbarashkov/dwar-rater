"""RBAC for the treasury surface + the «Казначей» role.

Guards two regressions that made the role impossible before:
  1. every treasury write endpoint carried a hardcoded
     ``g.current_user.role != "admin"`` check that bypassed RBAC entirely;
  2. treasury writes lived under ``clan_info:admin`` (import of clan members).

Unique clan ids per file: the suite shares one database, ids used elsewhere
(e.g. 2315 / 9870xx) must not be reused or assertions depend on module order.
"""

import os
import sys
import secrets
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.user import User
from shared.models.clan_info import ClanInfo, TreasuryOperation
from shared.rbac.models import SessionToken, Role, Permission, UserPermission, AuditLog

CLAN = 987101


def _login(app, username, role):
    """Create (or reuse) a user and return a Bearer token for them."""
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(
                username=username,
                password_hash='x',
                role=role,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
        token = secrets.token_hex(32)
        db.session.add(
            SessionToken(
                user_id=user.id,
                token_hash=SessionToken.hash_token(token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.session.commit()
        return token


def _headers(token):
    return {'Authorization': f'Bearer {token}'}


def _seed_clan_with_operation(app):
    with app.app_context():
        clan = ClanInfo.query.filter_by(clan_id=CLAN).first()
        if not clan:
            db.session.add(ClanInfo(clan_id=CLAN, name='TestClan'))
            db.session.commit()
        op = TreasuryOperation(
            clan_id=CLAN,
            date='15.01.2026 10:00',
            nick='Payer',
            operation_type='Деньги',
            object_name='Монеты',
            quantity=10,
        )
        db.session.add(op)
        db.session.commit()
        return op.id


def _role_level(app, role_name, feature, action):
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        perm = Permission.query.filter_by(feature=feature, action=action).first()
        if not role or not perm:
            return None
        from shared.rbac.models import RolePermission

        rp = RolePermission.query.filter_by(
            role_id=role.id, permission_id=perm.id
        ).first()
        return rp.level if rp else None


def test_treasurer_role_is_seeded(app):
    with app.app_context():
        role = Role.query.filter_by(name='treasurer').first()
        assert role is not None
        assert role.label == 'Казначей'


def test_treasurer_default_levels(app):
    assert _role_level(app, 'treasurer', 'treasury', 'write') == 'full'
    assert _role_level(app, 'treasurer', 'treasury', 'approve') == 'full'
    # Decision: import/backup (treasury:admin) is NOT granted by default.
    assert _role_level(app, 'treasurer', 'treasury', 'admin') == 'none'


def test_admin_keeps_full_treasury(app):
    assert _role_level(app, 'admin', 'treasury', 'write') == 'full'
    assert _role_level(app, 'admin', 'treasury', 'approve') == 'full'
    assert _role_level(app, 'admin', 'treasury', 'admin') == 'full'


def test_plain_user_has_no_treasury_write(app):
    assert _role_level(app, 'user', 'treasury', 'write') in (None, 'none')


def test_treasurer_can_correct_operation(app, client):
    op_id = _seed_clan_with_operation(app)
    token = _login(app, 'treasurer1', 'treasurer')

    resp = client.put(
        f'/api/clan/{CLAN}/treasury/{op_id}',
        json={'quantity': 250, 'compensation_comment': 'исправлено казначеем'},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()['quantity'] == 250

    with app.app_context():
        op = TreasuryOperation.query.get(op_id)
        assert op.quantity == 250
        assert op.compensation_comment == 'исправлено казначеем'
        # Filter by target: the suite shares one database and other modules
        # write the same action, so `.first()` alone is order-dependent.
        entry = AuditLog.query.filter_by(
            action='treasury_operation_update', target_id=op_id
        ).first()
        assert entry is not None


def test_plain_user_cannot_correct_operation(app, client):
    op_id = _seed_clan_with_operation(app)
    token = _login(app, 'plainuser1', 'user')

    resp = client.put(
        f'/api/clan/{CLAN}/treasury/{op_id}',
        json={'quantity': 999},
        headers=_headers(token),
    )
    assert resp.status_code == 403

    with app.app_context():
        assert TreasuryOperation.query.get(op_id).quantity == 10


def test_non_admin_role_with_permission_passes(app, client):
    """The hardcoded role check is gone: a granted non-admin role succeeds."""
    op_id = _seed_clan_with_operation(app)
    token = _login(app, 'custom1', 'custom')

    with app.app_context():
        user = User.query.filter_by(username='custom1').first()
        perm = Permission.query.filter_by(feature='treasury', action='write').first()
        db.session.add(
            UserPermission(user_id=user.id, permission_id=perm.id, level='full')
        )
        db.session.commit()

    resp = client.put(
        f'/api/clan/{CLAN}/treasury/{op_id}',
        json={'quantity': 42},
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_treasurer_can_create_compensation(app, client):
    _seed_clan_with_operation(app)
    token = _login(app, 'treasurer2', 'treasurer')

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/compensation',
        json={'nick': 'Payer', 'norm_amount': 100, 'months': [2], 'year': 2026,
              'comment': 'зачтено казначеем'},
        headers=_headers(token),
    )
    assert resp.status_code == 201, resp.get_data(as_text=True)
    assert resp.get_json()['created'] == 1


def test_treasurer_without_treasury_admin_cannot_import(app, client):
    """Decision: import/backup stays closed until granted in the matrix."""
    _seed_clan_with_operation(app)
    token = _login(app, 'treasurer3', 'treasurer')

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/import',
        json={'operations': [], 'replace': False},
        headers=_headers(token),
    )
    assert resp.status_code == 403


def test_admin_can_import(app, client):
    _seed_clan_with_operation(app)
    token = _login(app, 'admin2', 'admin')

    resp = client.post(
        f'/api/clan/{CLAN}/treasury/import',
        json={
            'operations': [
                {'date': '16.01.2026 10:00', 'nick': 'Payer',
                 'operation_type': 'Деньги', 'object_name': 'Монеты', 'quantity': 5}
            ],
            'replace_range': True,
        },
        headers=_headers(token),
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_read_level_does_not_grant_approve(app, client):
    """A 'read' level on an approve action must be refused."""
    _seed_clan_with_operation(app)
    _login(app, 'reader1', 'custom')

    # No carryover endpoint exists yet (stage 2); assert the decorator logic
    # directly so the rule is pinned before the route lands. The user must be
    # fetched inside the open app context, otherwise it is detached.
    with app.app_context():
        from flask import g
        from shared.rbac import require_permission

        user = User.query.filter_by(username='reader1').first()
        perm = Permission.query.filter_by(feature='treasury', action='approve').first()
        db.session.add(
            UserPermission(user_id=user.id, permission_id=perm.id, level='read')
        )
        db.session.commit()

        @require_permission('treasury', 'approve')
        def _probe():
            return 'ok'

        with app.test_request_context('/'):
            g.current_user = user
            g.user_perms = {'treasury:approve': 'read'}
            result = _probe()

        status = result[1] if isinstance(result, tuple) else 200
        assert status == 403
