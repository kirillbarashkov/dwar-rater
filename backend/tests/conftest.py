import pytest
import sys
import os
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db
from models.user import User


@pytest.fixture
def app():
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['AUTH_ENABLED'] = 'true'
    os.environ['ADMIN_USER'] = 'admin'
    os.environ['ADMIN_PASS'] = 'admin'
    os.environ['RATE_LIMIT_MAX'] = '100'
    os.environ['RATE_LIMIT_WINDOW'] = '60'
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.app_context():
        db.create_all()
        admin = User(
            username='admin',
            password_hash=hashlib.sha256('admin'.encode()).hexdigest(),
            role='admin'
        )
        user = User(
            username='testuser',
            password_hash=hashlib.sha256('testpass'.encode()).hexdigest(),
            role='user'
        )
        db.session.add(admin)
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
    return ('admin', 'admin')


@pytest.fixture
def user_auth():
    return ('testuser', 'testpass')
