from flask import Blueprint, request, jsonify, g
from middleware.auth import check_credentials, require_auth


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/login', methods=['POST'])
def login():
    auth = request.authorization
    if not auth:
        return jsonify({'error': 'Неверный логин или пароль'}), 401
    if not check_credentials(auth.username, auth.password):
        return jsonify({'error': 'Неверный логин или пароль'}), 401
    return jsonify({'status': 'ok'})


@auth_bp.route('/api/me', methods=['GET'])
@require_auth
def me():
    user = g.current_user
    return jsonify({
        'id': user.id,
        'username': user.username,
        'role': user.role,
    })
