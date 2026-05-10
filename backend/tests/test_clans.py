def test_clans_requires_auth(client):
    resp = client.get('/api/clans')
    assert resp.status_code == 401


def test_clans_empty_for_user(client, user_token):
    resp = client.get('/api/clans', headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_clan_create_admin_only(client, user_token):
    resp = client.post('/api/clans', json={'name': 'TestClan'},
                       headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 403


def test_clans_create_admin(client, admin_token):
    resp = client.post('/api/clans', json={'name': 'TestClan'},
                       headers={'Authorization': f'Bearer {admin_token}'})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['name'] == 'TestClan'


def test_clan_rooms_requires_auth(client):
    resp = client.get('/api/clans/1/rooms')
    assert resp.status_code == 401
