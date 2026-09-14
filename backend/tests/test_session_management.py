"""Session management (U9): admin can view/revoke any user's sessions; a user
can view/revoke their own. Verified against create_test_app (Bearers)."""
from datetime import datetime, timezone, timedelta
import secrets

from shared.models import db
from shared.models.user import User
from shared.rbac.models import SessionToken


def _make_session(user_id):
    token = secrets.token_hex(32)
    s = SessionToken(
        user_id=user_id,
        token_hash=SessionToken.hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
    )
    db.session.add(s)
    db.session.commit()
    return s.id


def _user_id(app, username):
    with app.app_context():
        u = User.query.filter_by(username=username).first()
        return u.id


def test_admin_lists_user_sessions(app, client, admin_headers, user_token):
    with app.app_context():
        u = User.query.filter_by(username='testuser').first()
        uid = u.id
        _make_session(uid)
        total = SessionToken.query.filter_by(user_id=uid).count()
    r = client.get(f'/api/admin/users/{uid}/sessions', headers=admin_headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data['username'] == 'testuser'
    assert data['total'] == total
    assert all('current' in s for s in data['sessions'])


def test_admin_revokes_single_session(app, client, admin_headers):
    uid = _user_id(app, 'testuser')
    with app.app_context():
        sid = _make_session(uid)
    r = client.delete(f'/api/admin/users/{uid}/sessions/{sid}', headers=admin_headers)
    assert r.status_code == 200
    assert r.get_json()['status'] == 'revoked'
    with app.app_context():
        assert SessionToken.query.get(sid) is None


def test_admin_revokes_others_keeps_caller(app, client, admin_headers, user_token):
    uid = _user_id(app, 'testuser')
    with app.app_context():
        _make_session(uid)
        before = SessionToken.query.filter_by(user_id=uid).count()
    assert before >= 2
    r = client.delete(f'/api/admin/users/{uid}/sessions/others', headers=admin_headers)
    assert r.status_code == 200
    assert r.get_json()['revoked'] == before
    with app.app_context():
        assert SessionToken.query.filter_by(user_id=uid).count() == 0
    # admin's own session untouched → token still valid
    r2 = client.get('/api/admin/users', headers=admin_headers)
    assert r2.status_code == 200


def test_admin_revoke_missing_session_404(app, client, admin_headers):
    uid = _user_id(app, 'testuser')
    r = client.delete(f'/api/admin/users/{uid}/sessions/999999', headers=admin_headers)
    assert r.status_code == 404


def test_self_list_and_revoke(app, client, user_token):
    headers = {'Authorization': f'Bearer {user_token}'}
    r = client.get('/api/auth/sessions', headers=headers)
    assert r.status_code == 200
    data = r.get_json()
    assert data['total'] >= 1
    sid = data['sessions'][0]['id']
    r2 = client.delete(f'/api/auth/sessions/{sid}', headers=headers)
    assert r2.status_code == 200


def test_self_sessions_requires_auth(app, client):
    r = client.get('/api/auth/sessions')
    assert r.status_code == 401