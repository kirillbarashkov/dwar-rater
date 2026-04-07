def test_clans_requires_auth(client):
    resp = client.get('/api/clans')
    assert resp.status_code == 401


def test_clans_empty_for_user(client, user_auth):
    resp = client.get('/api/clans', auth=user_auth)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_clan_create_admin_only(client, user_auth):
    resp = client.post('/api/clans', json={'name': 'TestClan'}, auth=user_auth)
    assert resp.status_code == 403


def test_clans_create_admin(client, admin_auth):
    resp = client.post('/api/clans', json={'name': 'TestClan'}, auth=admin_auth)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['name'] == 'TestClan'


def test_clan_rooms_requires_auth(client):
    resp = client.get('/api/clans/1/rooms')
    assert resp.status_code == 401
