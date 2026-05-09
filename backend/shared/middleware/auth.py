import os
import json
import bcrypt
from functools import wraps
from flask import request, jsonify, g
from shared.models import db
from shared.models.user import User
from shared.config import Config


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
users_file = os.path.join(BASE_DIR, 'users.json')

_cached_users = None


def _get_users():
    global _cached_users
    if _cached_users is not None:
        return _cached_users
    
    users = {}
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            users = json.load(f)
    elif Config.AUTH_ENABLED:
        users[Config.ADMIN_USER] = {
            'password_hash': bcrypt.hashpw(Config.ADMIN_PASS.encode(), bcrypt.gensalt()).decode('utf-8'),
            'role': 'admin'
        }
    _cached_users = users
    return users


def check_credentials(username, password):
    users = _get_users()
    if username in users:
        stored_hash = users[username]['password_hash'].encode('utf-8')
        return bcrypt.checkpw(password.encode(), stored_hash)
    user = User.query.filter_by(username=username).first()
    if user and user.password_hash:
        try:
            return bcrypt.checkpw(password.encode(), user.password_hash.encode('utf-8'))
        except ValueError:
            return False
    return False


def _ensure_default_user():
    user = User.query.filter_by(username=Config.ADMIN_USER).first()
    if not user:
        user = User(
            username=Config.ADMIN_USER,
            password_hash=bcrypt.hashpw(Config.ADMIN_PASS.encode(), bcrypt.gensalt()).decode('utf-8'),
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
            users = _get_users()
            user_data = users.get(auth.username, {})
            password_hash = user_data.get('password_hash')
            if not password_hash:
                password_hash = bcrypt.hashpw(auth.password.encode(), bcrypt.gensalt()).decode('utf-8')
            g.current_user = User(
                username=auth.username,
                password_hash=password_hash,
                role=user_data.get('role', 'user')
            )
            db.session.add(g.current_user)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return f(*args, **kwargs)
    return decorated
