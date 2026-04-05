import os
import hashlib
import json
from functools import wraps
from flask import request, jsonify, g
from backend.models import db
from backend.models.user import User
from backend.config import Config


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
users_file = os.path.join(BASE_DIR, 'users.json')

USERS = {}
if os.path.exists(users_file):
    with open(users_file, 'r') as f:
        USERS = json.load(f)
else:
    admin_user = Config.ADMIN_USER
    admin_pass = Config.ADMIN_PASS
    if Config.AUTH_ENABLED:
        USERS[admin_user] = {
            'password_hash': hashlib.sha256(admin_pass.encode()).hexdigest(),
            'role': 'admin'
        }


def check_credentials(username, password):
    if username not in USERS:
        return False
    return USERS[username]['password_hash'] == hashlib.sha256(password.encode()).hexdigest()


def _ensure_default_user():
    user = User.query.filter_by(username=Config.ADMIN_USER).first()
    if not user:
        user = User(
            username=Config.ADMIN_USER,
            password_hash=hashlib.sha256(Config.ADMIN_PASS.encode()).hexdigest(),
            role='admin'
        )
        db.session.add(user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    return user


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not Config.AUTH_ENABLED:
            g.current_user = _ensure_default_user()
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_credentials(auth.username, auth.password):
            return jsonify({'error': 'Требуется авторизация'}), 401
        g.current_user = User.query.filter_by(username=auth.username).first()
        if not g.current_user:
            user_data = USERS.get(auth.username, {})
            g.current_user = User(
                username=auth.username,
                password_hash=user_data.get('password_hash', hashlib.sha256(auth.password.encode()).hexdigest()),
                role=user_data.get('role', 'user')
            )
            db.session.add(g.current_user)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return f(*args, **kwargs)
    return decorated
