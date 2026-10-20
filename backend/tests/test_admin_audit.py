"""A1: каждое админское действие обязано оставлять запись в audit_log.

Регрессия: _audit() только делает db.session.add(entry) — запись появляется в БД
лишь при следующем commit(). Если _audit() вызван ПОСЛЕ commit() (или без
коммита вовсе) — запись теряется, и журнал аудита молча неполон.

Потеряны были 11 записей:
  * 8 мест — _audit() ПОСЛЕ commit() (update_user, deactivate_user,
    admin_unbind_character, revoke_user_other_sessions, revoke_user_session,
    update_role_permissions, update_user_permissions, delete_deprecated_permissions);
  * 3 места — _audit() БЕЗ commit() (create_backup, delete_backup, restore_backup).
"""
import pytest

from shared.models import db
from shared.models.user import User
from shared.rbac.models import AuditLog, Role

NICK = 'a1probe'


def _count(app, action):
    """Сколько записей с таким action в журнале.

    Читать AuditLog надо внутри app-контекста: после client-запроса сессия
    flask-sqlalchemy уже снята, и AuditLog.query без контекста падает.
    """
    with app.app_context():
        return AuditLog.query.filter_by(action=action).count()


def _role_id(app, name):
    with app.app_context():
        role = Role.query.filter_by(name=name).first()
        assert role is not None, f'роль {name} не засеяна'
        return role.id


@pytest.fixture
def target_user(app):
    """Пользователь-цель для админских операций.

    Берём testuser — он пересоздаётся фикстурой app на каждый тест, потому что
    test_auth.py его деактивирует, а app остаётся function scope намеренно.
    """
    with app.app_context():
        u = User.query.filter_by(username='testuser').first()
        assert u is not None
        db.session.commit()
        yield u.id


def test_user_update_is_audited(app, client, admin_headers, target_user):
    before = _count(app, 'user_update')
    r = client.put(f'/api/admin/users/{target_user}',
                   json={'is_active': True}, headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'user_update') == before + 1


def test_user_deactivate_is_audited(app, client, admin_headers, target_user):
    before = _count(app, 'user_deactivate')
    r = client.delete(f'/api/admin/users/{target_user}', headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'user_deactivate') == before + 1


def test_revoke_other_sessions_is_audited(app, client, admin_headers, target_user):
    before = _count(app, 'admin_revoke_sessions')
    r = client.delete(f'/api/admin/users/{target_user}/sessions/others',
                      headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'admin_revoke_sessions') == before + 1


def test_role_permissions_update_is_audited(app, client, admin_headers):
    role_id = _role_id(app, 'treasurer')
    before = _count(app, 'role_permissions_update')
    r = client.put(f'/api/admin/permissions/role/{role_id}',
                   json={'permissions': {}}, headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'role_permissions_update') == before + 1


def test_user_permissions_update_is_audited(app, client, admin_headers, target_user):
    before = _count(app, 'user_permissions_update')
    r = client.put(f'/api/admin/permissions/user/{target_user}',
                   json={'permissions': {}}, headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'user_permissions_update') == before + 1


def test_deprecated_permissions_delete_is_audited(app, client, admin_headers):
    before = _count(app, 'deprecated_permissions_deleted')
    r = client.delete('/api/admin/permissions/deprecated', headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'deprecated_permissions_deleted') == before + 1
