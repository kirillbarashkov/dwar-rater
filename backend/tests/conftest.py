import pytest
import sys
import os
import json
import bcrypt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import middleware.auth
middleware.auth._cached_users = None

from app import create_app
from models import db
from models.user import User
from config import Config


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


@pytest.fixture(autouse=True)
def reset_config():
    Config.ADMIN_USER = 'admin'
    Config.ADMIN_PASS = 'testpass'
    Config.AUTH_ENABLED = True
    middleware.auth._cached_users = None
    yield
    middleware.auth._cached_users = None


@pytest.fixture
def app():
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['AUTH_ENABLED'] = 'true'
    os.environ['ADMIN_USER'] = 'admin'
    os.environ['ADMIN_PASS'] = 'testpass'
    os.environ['RATE_LIMIT_MAX'] = '100'
    os.environ['RATE_LIMIT_WINDOW'] = '60'
    os.environ['SECRET_KEY'] = 'test-secret-key'

    Config.ADMIN_USER = 'admin'
    Config.ADMIN_PASS = 'testpass'
    Config.AUTH_ENABLED = True
    middleware.auth._cached_users = None

    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=bcrypt.hashpw('testpass'.encode(), bcrypt.gensalt()).decode('utf-8'),
                role='admin'
            )
            db.session.add(admin)
        if not User.query.filter_by(username='testuser').first():
            user = User(
                username='testuser',
                password_hash=bcrypt.hashpw('testpass'.encode(), bcrypt.gensalt()).decode('utf-8'),
                role='user'
            )
            db.session.add(user)
        db.session.commit()
    yield app

    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_auth():
    return ('admin', 'testpass')


@pytest.fixture
def user_auth():
    return ('testuser', 'testpass')


@pytest.fixture
def fixture_data():
    """Load JSON fixtures from tests/fixtures/.

    Usage:
        def test_something(fixture_data):
            data = fixture_data("parse_full_profile")
            assert data["name"] == "ТестовыйПерсонаж"
    """
    def _load(name):
        path = os.path.join(FIXTURES_DIR, f'{name}.json')
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return _load
