import pytest
import sys
import os
import json
import bcrypt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shared.middleware.auth
shared.middleware.auth._cached_users = None

from test_app import create_test_app
from shared.models import db
from shared.models.user import User
from shared.rbac.models import SessionToken
from shared.config import Config
from datetime import datetime, timezone, timedelta
import secrets


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _create_token(user_id, hours=24):
    """Create a session token for a user and return the token string."""
    token = secrets.token_hex(32)
    session = SessionToken(
        user_id=user_id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
    )
    db.session.add(session)
    db.session.commit()
    return token


def _truncate_all():
    """Truncate all tables between tests.

    Uses CASCADE to handle FK dependencies.
    """
    try:
        db.session.execute(db.text('TRUNCATE TABLE audit_log, user_permission, role_permission, session_token, equipment_item, compare_character, improvement_track, analysis_log, treasury_operations, clan_member_info, clan_chat_message, clan_chat_room, clan_member, character_snapshot, character_cache, closed_profiles, clan_info, clan, permission, app_user, role, leveling_scenario RESTART IDENTITY CASCADE'))
        db.session.commit()
    except Exception:
        db.session.rollback()


@pytest.fixture(autouse=True)
def reset_config():
    Config.ADMIN_USER = 'admin'
    Config.ADMIN_PASS = 'testpass'
    Config.AUTH_ENABLED = True
    shared.middleware.auth._cached_users = None
    yield
    shared.middleware.auth._cached_users = None


@pytest.fixture
def app():
    test_db_url = os.environ.get(
        'TEST_DATABASE_URL',
        'postgresql://dwar:change-me-in-production@postgres:5432/dwar_rater_test'
    )
    os.environ['DATABASE_URL'] = test_db_url
    os.environ['AUTH_ENABLED'] = 'true'
    os.environ['ADMIN_USER'] = 'admin'
    os.environ['ADMIN_PASS'] = 'testpass'
    os.environ['RATE_LIMIT_MAX'] = '100'
    os.environ['RATE_LIMIT_WINDOW'] = '60'
    os.environ['SECRET_KEY'] = 'test-secret-key'

    Config.DATABASE_URL = test_db_url
    Config.ADMIN_USER = 'admin'
    Config.ADMIN_PASS = 'testpass'
    Config.AUTH_ENABLED = True
    shared.middleware.auth._cached_users = None

    app = create_test_app()
    app.config['TESTING'] = True

    with app.app_context():
        db.create_all()

        # Seed RBAC data (roles, permissions, role_permissions)
        from shared.rbac.seed import seed_all
        seed_all(db)
        db.session.commit()

        # Create or update test users
        admin = User.query.filter_by(username='admin').first()
        if admin:
            admin.password_hash = bcrypt.hashpw('testpass'.encode(), bcrypt.gensalt()).decode('utf-8')
            admin.role = 'admin'
            admin.is_active = True
        else:
            admin = User(
                username='admin',
                password_hash=bcrypt.hashpw('testpass'.encode(), bcrypt.gensalt()).decode('utf-8'),
                role='admin'
            )
            db.session.add(admin)

        user = User.query.filter_by(username='testuser').first()
        if user:
            user.password_hash = bcrypt.hashpw('testpass'.encode(), bcrypt.gensalt()).decode('utf-8')
            user.role = 'user'
            user.is_active = True
        else:
            user = User(
                username='testuser',
                password_hash=bcrypt.hashpw('testpass'.encode(), bcrypt.gensalt()).decode('utf-8'),
                role='user'
            )
            db.session.add(user)
        db.session.commit()

    yield app

    with app.app_context():
        _truncate_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_token(app):
    """Create a session token for the admin user. Returns the token string."""
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        return _create_token(admin.id)


@pytest.fixture
def user_token(app):
    """Create a session token for the testuser. Returns the token string."""
    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        return _create_token(user.id)


@pytest.fixture
def admin_auth():
    """Legacy fixture for backward compatibility. Returns Basic Auth tuple."""
    return ('admin', 'testpass')


@pytest.fixture
def user_auth():
    """Legacy fixture for backward compatibility. Returns Basic Auth tuple."""
    return ('testuser', 'testpass')


@pytest.fixture
def admin_headers(admin_token):
    """HTTP headers with admin Bearer token."""
    return {'Authorization': f'Bearer {admin_token}'}


@pytest.fixture
def user_headers(user_token):
    """HTTP headers with user Bearer token."""
    return {'Authorization': f'Bearer {user_token}'}


@pytest.fixture
def fixture_data():
    def _load(name):
        path = os.path.join(FIXTURES_DIR, f'{name}.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return _load
