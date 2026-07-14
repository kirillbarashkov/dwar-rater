def test_health_check(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ok'


def test_login_success(client):
    resp = client.post('/api/auth/login', json={'username': 'admin', 'password': 'testpass'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'token' in data
    assert data['user']['role'] == 'admin'


def test_login_wrong_password(client):
    resp = client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong'})
    assert resp.status_code == 401


def test_login_no_auth(client):
    resp = client.post('/api/auth/login', json={})
    assert resp.status_code == 400


def test_me_endpoint(client, admin_token):
    resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {admin_token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['user']['username'] == 'admin'
    assert data['user']['role'] == 'admin'


def test_me_user_role(client, user_token):
    resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['user']['username'] == 'testuser'
    assert data['user']['role'] == 'user'


def test_me_no_auth(client):
    resp = client.get('/api/auth/me')
    assert resp.status_code == 401


def test_protected_endpoints_require_auth(client):
    for path in ['/api/snapshots', '/api/scenarios', '/api/tracks', '/api/clans']:
        resp = client.get(path)
        assert resp.status_code in (401, 403), f'{path} should require auth'


# ── S1: Session token hashing ──────────────────────────────────────────

def test_token_stored_as_hash_not_plaintext(client, app):
    """S1: After login, the DB must store token_hash (sha256), not plain token."""
    from shared.rbac.models import SessionToken

    resp = client.post('/api/auth/login', json={'username': 'admin', 'password': 'testpass'})
    assert resp.status_code == 200
    plain_token = resp.get_json()['token']

    with app.app_context():
        session = SessionToken.find_by_token(plain_token)
        assert session is not None
        assert session.token_hash == SessionToken.hash_token(plain_token)
        assert not hasattr(session, 'token') or session.__dict__.get('token') is None


def test_find_by_token_with_invalid_token(client, app):
    """S1: find_by_token returns None for garbage input."""
    from shared.rbac.models import SessionToken
    with app.app_context():
        assert SessionToken.find_by_token('garbage') is None
        assert SessionToken.find_by_token('') is None


# ── S4: Session invalidation on permission/role change ─────────────────

def test_session_invalidated_on_role_change(client, app, admin_headers, user_token):
    """S4: After admin changes a user's role, the user's old token must be invalid."""
    with app.app_context():
        from shared.models.user import User
        user = User.query.filter_by(username='testuser').first()
        user_id = user.id

    # User's token works before change
    resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 200

    # Admin changes user's role
    resp = client.put(f'/api/admin/users/{user_id}',
                      json={'role': 'superuser'},
                      headers=admin_headers)
    assert resp.status_code == 200

    # Old token must now be invalid (session invalidated)
    resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 401


def test_session_invalidated_on_deactivate(client, app, admin_headers, user_token):
    """S4: After admin deactivates a user, the user's old token must be invalid."""
    with app.app_context():
        from shared.models.user import User
        user = User.query.filter_by(username='testuser').first()
        user_id = user.id

    # Token works before deactivation
    resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 200

    # Admin deactivates user
    resp = client.delete(f'/api/admin/users/{user_id}', headers=admin_headers)
    assert resp.status_code == 200

    # Old token must now be invalid
    resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 401


def test_session_invalidated_on_password_reset(client, app, admin_headers, user_token):
    """S4: After admin resets a user's password, the user's old token must be invalid."""
    with app.app_context():
        from shared.models.user import User
        user = User.query.filter_by(username='testuser').first()
        user_id = user.id

    resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 200

    resp = client.put(f'/api/admin/users/{user_id}',
                      json={'password': 'NewPassword123'},
                      headers=admin_headers)
    assert resp.status_code == 200

    resp = client.get('/api/auth/me', headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 401


# ── S5: No hardcoded admin bypass ──────────────────────────────────────

def test_admin_access_works_without_bypass(client, admin_headers):
    """S5: Admin can still access endpoints because seed gives full permissions,
    not because of a hardcoded role=='admin' bypass."""
    resp = client.get('/api/admin/users', headers=admin_headers)
    assert resp.status_code == 200

    resp = client.get('/api/admin/permissions', headers=admin_headers)
    assert resp.status_code == 200

    resp = client.get('/api/admin/audit', headers=admin_headers)
    assert resp.status_code == 200


def test_user_cannot_access_admin_endpoints(client, user_headers):
    """S5: Regular user is blocked from admin endpoints (admin:read = none)."""
    resp = client.get('/api/admin/users', headers=user_headers)
    assert resp.status_code == 403

    resp = client.get('/api/admin/permissions', headers=user_headers)
    assert resp.status_code == 403
