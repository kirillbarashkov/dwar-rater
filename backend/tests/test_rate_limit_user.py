"""Per-user rate limiting (A7): authenticated requests are keyed by user_id,
not by shared/NAT IP.

These tests clear the rate_limit table up front so they do not depend on
cross-test isolation (the suite's TRUNCATE-based reset proved unreliable —
a stale bucket makes the very first request 429).
"""
from shared.config import Config
from shared.models import db


def _reset_buckets(app):
    with app.app_context():
        db.session.execute(db.text('TRUNCATE TABLE rate_limit RESTART IDENTITY'))
        db.session.commit()


def test_rate_limit_keys_per_user(app, client, user_token, admin_headers):
    _reset_buckets(app)
    Config.RATE_LIMIT_MAX = 3
    Config.RATE_LIMIT_WINDOW = 60
    headers = {'Authorization': f'Bearer {user_token}'}
    codes = [client.get('/api/auth/sessions', headers=headers).status_code for _ in range(6)]
    # bucket for THIS user: allowed 3, then rate-limited
    assert codes[:3] == [200, 200, 200], codes
    assert codes[3:] == [429, 429, 429], codes
    # another identity is unaffected → the key really is the user, not the IP
    r = client.get('/api/auth/sessions', headers=admin_headers)
    assert r.status_code == 200


def test_rate_limit_does_not_leak_between_users(app, client, user_token, admin_token):
    _reset_buckets(app)
    Config.RATE_LIMIT_MAX = 2
    Config.RATE_LIMIT_WINDOW = 60
    uh = {'Authorization': f'Bearer {user_token}'}
    ah = {'Authorization': f'Bearer {admin_token}'}
    # drain the USER's bucket
    for _ in range(3):
        client.get('/api/auth/sessions', headers=uh)
    # a different user (admin) is not throttled by the user's bucket
    r = client.get('/api/auth/sessions', headers=ah)
    assert r.status_code == 200, r.status_code