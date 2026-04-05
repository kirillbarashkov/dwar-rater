from flask import Blueprint, request, jsonify
from backend.middleware.auth import check_credentials, require_auth


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/login', methods=['POST'])
def login():
    auth = request.authorization
    if not auth:
        return jsonify({'error': 'Неверный логин или пароль'}), 401
    if not check_credentials(auth.username, auth.password):
        return jsonify({'error': 'Неверный логин или пароль'}), 401
    return jsonify({'status': 'ok'})
