def test_analyze_invalid_url(client, admin_auth):
    resp = client.post('/api/analyze', json={'url': 'https://evil.com/hack'}, auth=admin_auth)
    assert resp.status_code == 400


def test_analyze_empty_url(client, admin_auth):
    resp = client.post('/api/analyze', json={'url': ''}, auth=admin_auth)
    assert resp.status_code == 400


def test_analyze_no_auth(client):
    resp = client.post('/api/analyze', json={'url': 'https://w1.dwar.ru/user_info.php?nick=Test'})
    assert resp.status_code == 401


def test_analyze_requires_json(client, admin_auth):
    resp = client.post('/api/analyze', data='not json', auth=admin_auth,
                       content_type='text/plain')
    assert resp.status_code == 415
