def test_analyze_invalid_url(client, admin_token):
    resp = client.post('/api/analyze', json={'url': 'https://evil.com/hack'},
                       headers={'Authorization': f'Bearer {admin_token}'})
    assert resp.status_code == 400


def test_analyze_empty_url(client, admin_token):
    resp = client.post('/api/analyze', json={'url': ''},
                       headers={'Authorization': f'Bearer {admin_token}'})
    assert resp.status_code == 400


def test_analyze_no_auth(client):
    resp = client.post('/api/analyze', json={'url': 'https://w1.dwar.ru/user_info.php?nick=Test'})
    assert resp.status_code == 401


def test_analyze_requires_json(client, admin_token):
    resp = client.post('/api/analyze', data='not json',
                       headers={'Authorization': f'Bearer {admin_token}', 'Content-Type': 'text/plain'})
    assert resp.status_code == 415
