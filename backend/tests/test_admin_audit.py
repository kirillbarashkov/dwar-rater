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
import os

import pytest

from shared.models import db
from shared.models.user import User
from shared.rbac.models import AuditLog, Role

NICK = 'a1probe'


class _FakePgDump:
    """Заглушка pg_dump: возвращает «пустой» дамп и нулевой код возврата."""
    returncode = 0
    stdout = b'-- fake dump\n'
    stderr = b''


def _fake_pg_dump(*args, **kwargs):
    return _FakePgDump()


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
    # Меняем роль, а не is_active: у _audit('user_update') стоит `if changes:`
    # — если переданное значение совпадает с текущим, изменений нет и след
    # не пишется (это осознанное поведение, а не потеря записи).
    before = _count(app, 'user_update')
    r = client.put(f'/api/admin/users/{target_user}',
                   json={'role': 'superuser'}, headers=admin_headers)
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


# ── Операции с бэкапами: там _audit() был вообще без commit() ──────────────

@pytest.fixture
def backup_dir(app, tmp_path, monkeypatch):
    """Временный каталог бэкапов вместо /backups и заглушка вместо pg_dump."""
    import features.admin.routes as admin_routes

    monkeypatch.setattr(admin_routes, 'BACKUP_DIR', str(tmp_path))
    monkeypatch.setattr(admin_routes.subprocess, 'run', _fake_pg_dump)
    return tmp_path


def test_backup_created_is_audited(app, client, admin_headers, backup_dir):
    before = _count(app, 'backup_created')
    # POST без тела Flask отвергает с 415 — шлём пустой JSON.
    r = client.post('/api/admin/backups', json={}, headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'backup_created') == before + 1

    # Файл бэкапа должен существовать и быть валидным gzip — на Windows это
    # ловило баг с os.rename поверх открытого файла (A1, побочно).
    filename = r.get_json()['backup']['filename']
    path = os.path.join(str(backup_dir), filename)
    assert os.path.exists(path)
    import gzip
    with gzip.open(path, 'rb') as gz:
        assert gz.read().startswith(b'-- fake dump')


def test_backup_deleted_is_audited(app, client, admin_headers, backup_dir):
    # Сначала создаём бэкап, чтобы было что удалять.
    r = client.post('/api/admin/backups', json={}, headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    filename = r.get_json()['backup']['filename']

    before = _count(app, 'backup_deleted')
    r2 = client.delete(f'/api/admin/backups/{filename}', headers=admin_headers)
    assert r2.status_code == 200, r2.get_json()
    assert _count(app, 'backup_deleted') == before + 1
    assert not os.path.exists(os.path.join(str(backup_dir), filename))


def test_backup_restored_is_audited(app, client, admin_headers, backup_dir):
    r = client.post('/api/admin/backups', json={}, headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    filename = r.get_json()['backup']['filename']

    # restore дергает psql — тоже подменяем, чтобы не трогать реальную БД.
    import features.admin.routes as admin_routes
    original_run = admin_routes.subprocess.run
    try:
        admin_routes.subprocess.run = _fake_pg_dump
        before = _count(app, 'backup_restored')
        r2 = client.post(f'/api/admin/backups/{filename}/restore', json={}, headers=admin_headers)
    finally:
        admin_routes.subprocess.run = original_run

    assert r2.status_code == 200, r2.get_json()
    assert _count(app, 'backup_restored') == before + 1
