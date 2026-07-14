import bcrypt
from functools import wraps
from flask import request, jsonify, g
from shared.models import db
from shared.models.user import User
from shared.config import Config


def check_credentials(username, password):
    """Check user credentials against the database (single source of truth)."""
    user = User.query.filter_by(username=username).first()
    if user and user.password_hash:
        try:
            return bcrypt.checkpw(password.encode(), user.password_hash.encode('utf-8'))
        except ValueError:
            return False
    return False


def require_auth(f):
    """Decorator requiring HTTP Basic auth.

    Note: the primary auth flow is session-based Bearer tokens via
    before_request + @require_permission. This decorator is kept for
    legacy/CLI endpoints that still use Basic Auth.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not Config.AUTH_ENABLED:
            # Only health-check-like endpoints allowed without auth
            if request.path == '/api/health':
                return f(*args, **kwargs)
            return jsonify({'error': 'Аутентификация отключена'}), 401
        auth = request.authorization
        if not auth or not check_credentials(auth.username, auth.password):
            return jsonify({'error': 'Требуется авторизация'}), 401
        g.current_user = User.query.filter_by(username=auth.username).first()
        if not g.current_user:
            return jsonify({'error': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)
    return decorated
