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
