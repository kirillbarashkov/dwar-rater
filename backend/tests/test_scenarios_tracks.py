def test_scenarios_empty_list(client, admin_auth):
    resp = client.get('/api/scenarios', auth=admin_auth)
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_scenarios_create_admin_only(client, user_auth):
    resp = client.post('/api/scenarios', json={
        'name': 'Test',
        'data': {'target_stats': {}}
    }, auth=user_auth)
    assert resp.status_code == 403


def test_scenarios_requires_auth(client):
    resp = client.get('/api/scenarios')
    assert resp.status_code == 401


def test_tracks_requires_auth(client):
    resp = client.get('/api/tracks')
    assert resp.status_code == 401


def test_tracks_generate_no_data(client, admin_auth):
    resp = client.post('/api/tracks/generate', json={}, auth=admin_auth)
    assert resp.status_code == 400
