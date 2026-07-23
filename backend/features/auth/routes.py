"""Session-based authentication endpoints.

Replaces HTTP Basic Auth with Bearer token sessions.
- 1 session per user (new login invalidates old)
- TTL: 24h (user/custom), 8h (admin/superuser)
- TOTP 2FA for admin (required), superuser (optional)
"""

import os
import secrets
import bcrypt
import pyotp
import qrcode
import base64
import io
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse, parse_qs
from flask import Blueprint, request, jsonify, g
from shared.models import db
from shared.models.user import User
from shared.rbac.models import SessionToken, AuditLog
from shared.rbac import get_user_permission, Permission as PermDef, feature, require_permission
from shared.utils.validators import validate_dwar_url

auth_bp = Blueprint('auth', __name__)

SESSION_TTL = {
    'admin': 8,
    'superuser': 8,
    'user': 24,
    'custom': 24,
}

DEFAULT_PASSWORD = 'ChangeMe123!'


def _generate_token() -> str:
    return secrets.token_hex(32)


def _create_session(user: User) -> tuple[SessionToken, str]:
    """Create a new session token, invalidating all existing sessions.

    Returns (session, plain_token) — plain_token is returned to client,
    only token_hash is stored in DB.
    """
    SessionToken.query.filter_by(user_id=user.id).delete()

    ttl_hours = SESSION_TTL.get(user.role, 24)
    plain_token = _generate_token()
    session = SessionToken(
        user_id=user.id,
        token_hash=SessionToken.hash_token(plain_token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
    )
    db.session.add(session)
    return session, plain_token


def _audit(action: str, user=None, target_type=None, target_id=None, old=None, new=None):
    """Log an audit entry."""
    entry = AuditLog(
        user_id=user.id if user else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        old_value=old if old is None else (old if isinstance(old, str) else str(old)),
        new_value=new if new is None else (new if isinstance(new, str) else str(new)),
        ip_address=request.remote_addr,
    )
    db.session.add(entry)


@feature('auth', [
    PermDef('read', 'Аутентификация', 'POST /api/auth/login'),
])
@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'username и password обязательны'}), 400

    user = User.query.filter_by(username=data['username']).first()
    if not user:
        return jsonify({'error': 'Неверный логин или пароль'}), 401

    if not user.is_active:
        return jsonify({'error': 'Аккаунт деактивирован'}), 403

    if not user.password_hash:
        return jsonify({'error': 'Неверный логин или пароль'}), 401

    try:
        pw_hash = user.password_hash
        if isinstance(pw_hash, bytes):
            pw_hash = pw_hash.decode('utf-8')
        if not bcrypt.checkpw(data['password'].encode(), pw_hash.encode()):
            return jsonify({'error': 'Неверный логин или пароль'}), 401
    except (ValueError, AttributeError):
        return jsonify({'error': 'Неверный логин или пароль'}), 401

    if user.role in ('admin', 'superuser') and user.totp_secret:
        return jsonify({
            'requires_2fa': True,
            'user_id': user.id,
            'username': user.username,
        }), 200

    session, plain_token = _create_session(user)
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    _audit('login', user=user, target_type='session', target_id=session.id)

    return jsonify({
        'token': plain_token,
        'user': user.to_dict(),
        'must_change_password': user.must_change_password,
        'expires_at': session.expires_at.isoformat(),
    })


@auth_bp.route('/api/auth/login/2fa', methods=['POST'])
def login_2fa():
    data = request.json
    if not data or 'user_id' not in data or 'code' not in data:
        return jsonify({'error': 'user_id и code обязательны'}), 400

    user = User.query.get(data['user_id'])
    if not user or not user.totp_secret:
        return jsonify({'error': '2FA не настроена'}), 400

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(data['code']):
        return jsonify({'error': 'Неверный код'}), 401

    session, plain_token = _create_session(user)
    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    _audit('login_2fa', user=user, target_type='session', target_id=session.id)

    return jsonify({
        'token': plain_token,
        'user': user.to_dict(),
        'must_change_password': user.must_change_password,
        'expires_at': session.expires_at.isoformat(),
    })


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        session = SessionToken.find_by_token(token)
        if session:
            _audit('logout', user=session.user, target_type='session', target_id=session.id)
            db.session.delete(session)
            db.session.commit()
    return jsonify({'status': 'ok'})


@auth_bp.route('/api/auth/me', methods=['GET'])
def me():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({'error': 'Требуется авторизация'}), 401

    session = SessionToken.find_by_token(token)
    if not session or session.is_expired:
        return jsonify({'error': 'Сессия истекла'}), 401

    user = session.user
    if not user.is_active:
        return jsonify({'error': 'Аккаунт деактивирован'}), 403

    # Use cached permissions from g.user_perms (populated in session_auth)
    from flask import g
    permissions = getattr(g, 'user_perms', None)
    if permissions is None:
        # Fallback: load permissions directly (e.g. if before_request didn't run)
        permissions = {}
        from shared.rbac.models import Permission as PermModel
        for perm in PermModel.query.filter_by(is_deprecated=False).all():
            level = get_user_permission(user, perm.feature, perm.action)
            permissions[f"{perm.feature}:{perm.action}"] = level

    return jsonify({
        'user': user.to_dict(),
        'permissions': permissions,
    })


@auth_bp.route('/api/auth/change-password', methods=['POST'])
def change_password():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    session = SessionToken.find_by_token(token)
    if not session or session.is_expired:
        return jsonify({'error': 'Требуется авторизация'}), 401

    user = session.user
    data = request.json
    if not data or 'new_password' not in data:
        return jsonify({'error': 'new_password обязателен'}), 400

    if len(data['new_password']) < 8:
        return jsonify({'error': 'Пароль должен быть не менее 8 символов'}), 400

    user.password_hash = bcrypt.hashpw(data['new_password'].encode(), bcrypt.gensalt()).decode()
    user.must_change_password = False
    db.session.commit()

    _audit('password_change', user=user, target_type='user', target_id=user.id)

    return jsonify({'status': 'ok'})


@auth_bp.route('/api/auth/2fa/setup', methods=['POST'])
@require_permission('auth', 'read')
def setup_2fa():
    user = g.current_user
    if user.role not in ('admin', 'superuser'):
        return jsonify({'error': '2FA доступна только для admin и superuser'}), 403

    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.session.commit()

    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.username, issuer_name='Dwar Rater'
    )
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    _audit('2fa_setup', user=user, target_type='user', target_id=user.id)

    return jsonify({
        'secret': secret,
        'qr_code': f'data:image/png;base64,{qr_base64}',
    })


@auth_bp.route('/api/auth/2fa/verify', methods=['POST'])
@require_permission('auth', 'read')
def verify_2fa():
    user = g.current_user
    if not user.totp_secret:
        return jsonify({'error': '2FA не настроена'}), 400

    data = request.json
    if not data or 'code' not in data:
        return jsonify({'error': 'code обязателен'}), 400

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(data['code']):
        return jsonify({'error': 'Неверный код'}), 401

    _audit('2fa_verified', user=user, target_type='user', target_id=user.id)

    return jsonify({'status': 'ok'})


@auth_bp.route('/api/auth/2fa/disable', methods=['POST'])
@require_permission('auth', 'read')
def disable_2fa():
    user = g.current_user
    if user.role == 'admin':
        return jsonify({'error': 'Admin не может отключить 2FA'}), 403

    user.totp_secret = None
    db.session.commit()

    _audit('2fa_disabled', user=user, target_type='user', target_id=user.id)

    return jsonify({'status': 'ok'})


def _normalize_character_url(raw_url):
    """Валидирует и нормализует URL персонажа.

    Возвращает (url, nick, error):
      - пустая строка → (None, None, None) — означает «отвязать персонажа»
      - ошибка валидации → (None, None, 'сообщение об ошибке')
      - успех → (url, nick, None)
    """
    raw_url = (raw_url or '').strip()
    if not raw_url:
        return None, None, None

    valid, error = validate_dwar_url(raw_url)
    if not valid:
        return None, None, error

    if not raw_url.startswith('http'):
        nick = raw_url
        if 'nick=' in nick:
            nick = nick.split('nick=')[1].split('&')[0]
        if not nick:
            return None, None, 'Не удалось извлечь ник из URL'
        url = f'https://w1.dwar.ru/user_info.php?nick={nick}'
    else:
        nick = parse_qs(urlparse(raw_url).query).get('nick', [''])[0]
        if not nick:
            return None, None, 'Не удалось извлечь ник из URL'
        url = raw_url

    return url, nick, None


@auth_bp.route('/api/auth/profile', methods=['PUT'])
@require_permission('character', 'write')
def update_profile():
    user = g.current_user
    data = request.json or {}
    raw_url = data.get('character_url')

    url, nick, error = _normalize_character_url(raw_url)
    if error:
        return jsonify({'error': error}), 400

    old_value = {'character_url': user.character_url, 'character_nick': user.character_nick}
    user.character_url = url
    user.character_nick = nick
    db.session.commit()

    _audit(
        'update_profile',
        user=user,
        target_type='user',
        target_id=user.id,
        old=old_value,
        new={'character_url': user.character_url, 'character_nick': user.character_nick},
    )

    return jsonify({'user': user.to_dict()})
