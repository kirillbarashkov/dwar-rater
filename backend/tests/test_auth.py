def test_health_check(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ok'


def test_login_success(client, admin_auth):
    resp = client.post('/api/login', auth=admin_auth)
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'ok'


def test_login_wrong_password(client):
    resp = client.post('/api/login', auth=('admin', 'wrong'))
    assert resp.status_code == 401


def test_login_no_auth(client):
    resp = client.post('/api/login')
    assert resp.status_code == 401


def test_me_endpoint(client, admin_auth):
    resp = client.get('/api/me', auth=admin_auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['username'] == 'admin'
    assert data['role'] == 'admin'


def test_me_user_role(client, user_auth):
    resp = client.get('/api/me', auth=user_auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['username'] == 'testuser'
    assert data['role'] == 'user'


def test_me_no_auth(client):
    resp = client.get('/api/me')
    assert resp.status_code == 401


def test_protected_endpoints_require_auth(client):
    for path in ['/api/snapshots', '/api/scenarios', '/api/tracks', '/api/clans']:
        resp = client.get(path)
        assert resp.status_code == 401, f'{path} should require auth'
