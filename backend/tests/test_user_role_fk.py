"""User.role is now backed by role_id FK (A3) — reads/writes and admin
filtering must keep working."""
from shared.models import db
from shared.models.user import User


def test_role_property_backed_by_role_id(app, admin_token):
    with app.app_context():
        u = User.query.filter_by(username='admin').first()
        assert u.role_id is not None
        assert u.role == 'admin'
        original = u.role_id

        # setter resolves a role NAME to the FK
        u.role = 'user'
        db.session.commit()
        db.session.refresh(u)
        assert u.role == 'user'
        assert u.role_id != original

        u.role = 'admin'
        db.session.commit()
        db.session.refresh(u)
        assert u.role == 'admin'
        assert u.role_id == original


def test_admin_users_filter_by_role_name(app, client, admin_headers):
    r = client.get('/api/admin/users?role=admin', headers=admin_headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data['total'] >= 1
    assert all(u['role'] == 'admin' for u in data['users'])


def test_admin_users_unknown_role_returns_empty(app, client, admin_headers):
    r = client.get('/api/admin/users?role=__nope__', headers=admin_headers)
    assert r.status_code == 200
    assert r.get_json()['total'] == 0