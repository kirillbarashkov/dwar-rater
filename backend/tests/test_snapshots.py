def test_snapshots_empty_list(client, admin_token):
    resp = client.get('/api/snapshots', headers={'Authorization': f'Bearer {admin_token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['snapshots'] == []


def test_snapshots_user_sees_own_only(client, user_token):
    resp = client.get('/api/snapshots', headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 200


def test_snapshots_requires_auth(client):
    resp = client.get('/api/snapshots')
    assert resp.status_code == 401
