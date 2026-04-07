def test_snapshots_empty_list(client, admin_auth):
    resp = client.get('/api/snapshots', auth=admin_auth)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['snapshots'] == []


def test_snapshots_user_sees_own_only(client, user_auth, admin_auth):
    resp = client.get('/api/snapshots', auth=user_auth)
    assert resp.status_code == 200


def test_snapshots_requires_auth(client):
    resp = client.get('/api/snapshots')
    assert resp.status_code == 401
