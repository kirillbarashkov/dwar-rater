"""A63: смена пароля требует текущий пароль (а при 2FA — и код).

До правки `POST /api/auth/change-password` принимал только `new_password` и
валидный токен. Поле `current_password` в коде не упоминалось вовсе.

Последствие не «неудобство», а захват аккаунта: укравший токен сессии (чужой
открытый ноутбук, украденный браузерный профиль, XSS) меняет пароль и
выбрасывает владельца. Для admin/superuser это потеря контроля над системой, а
для пользователя с 2FA — обход второго фактора ровно в самой чувствительной
операции.

Теперь: `current_password` обязателен, сверяется через bcrypt; неверный пароль
даёт 403 и запись `password_change_failed` в аудит; для пользователя с
настроенной 2FA обязателен и верный `totp_code` (иначе 400/403 и запись
`password_change_failed_2fa`).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db  # noqa: E402
from shared.models.user import User  # noqa: E402
from shared.rbac.models import AuditLog, SessionToken  # noqa: E402

OLD = 'old-password-123'
NEW = 'new-password-456'


def _headers(token):
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user_token(app, client):
    """Свежий пользователь и его сессия — без role_id, чтобы не задевать RBAC."""
    with app.app_context():
        stale = User.query.filter_by(username='a63-user').first()
        if stale is not None:
            db.session.query(AuditLog).filter_by(user_id=stale.id).delete()
            db.session.query(SessionToken).filter_by(user_id=stale.id).delete()
            db.session.commit()
            User.query.filter_by(username='a63-user').delete()
            db.session.commit()
        user = User(username='a63-user', password_hash='', is_active=True)
        user.password_hash = _hash(OLD)
        db.session.add(user)
        db.session.commit()
        token = 'a63token' + '0' * 56
        db.session.query(SessionToken).filter_by(user_id=user.id).delete()
        db.session.add(
            SessionToken(
                user_id=user.id,
                token_hash=SessionToken.hash_token(token),
                expires_at=_in_hour(),
            )
        )
        db.session.commit()
        yield user.id, token
        # порядок важен: audit_log и session_token ссылаются на пользователя
        db.session.query(AuditLog).filter_by(user_id=user.id).delete()
        db.session.query(SessionToken).filter_by(user_id=user.id).delete()
        db.session.commit()
        User.query.filter_by(username='a63-user').delete()
        db.session.commit()


def _hash(password):
    import bcrypt

    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _in_hour():
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone.utc) + timedelta(hours=1)


def _password_works(app, user_id, candidate):
    """Проверка идёт тем же сеансом, что и запросы: fixture держит app context."""
    import bcrypt

    db.session.expire_all()
    user = db.session.get(User, user_id)
    return bcrypt.checkpw(candidate.encode(), user.password_hash.encode())


def _audit_actions(app):
    db.session.expire_all()
    return [row.action for row in AuditLog.query.order_by(AuditLog.id.desc()).limit(5)]


def test_current_password_is_required(client, user_token):
    _user_id, token = user_token
    response = client.post(
        '/api/auth/change-password',
        json={'new_password': NEW},
        headers=_headers(token),
    )
    assert response.status_code == 400
    assert 'current_password' in response.get_json()['error']


def test_wrong_current_password_is_rejected_and_audited(app, client, user_token):
    user_id, token = user_token
    response = client.post(
        '/api/auth/change-password',
        json={'current_password': 'not-the-password', 'new_password': NEW},
        headers=_headers(token),
    )
    assert response.status_code == 403
    assert _password_works(app, user_id, OLD), 'пароль изменился без знания текущего'
    assert not _password_works(app, user_id, NEW)
    assert 'password_change_failed' in _audit_actions(app)


def test_correct_current_password_changes_it(app, client, user_token):
    user_id, token = user_token
    response = client.post(
        '/api/auth/change-password',
        json={'current_password': OLD, 'new_password': NEW},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.get_json()
    assert _password_works(app, user_id, NEW)
    assert not _password_works(app, user_id, OLD), 'старый пароль продолжает работать'


def test_short_new_password_is_rejected_before_anything_else(client, user_token):
    _user_id, token = user_token
    response = client.post(
        '/api/auth/change-password',
        json={'current_password': OLD, 'new_password': 'short'},
        headers=_headers(token),
    )
    assert response.status_code == 400


def test_two_factor_user_needs_a_code(app, client, user_token):
    user_id, token = user_token
    import pyotp

    secret = pyotp.random_base32()
    # Важно: без вложенного app_context. Fixture держит контекст открытым, и
    # запросы используют его же сеанс — правка из другого сеанса осталась бы
    # невидимой из-за identity map (на этом тест уже один раз обманулся).
    target = db.session.get(User, user_id)
    target.totp_secret = secret
    db.session.commit()
    db.session.expire_all()
    assert db.session.get(User, user_id).totp_secret == secret, 'секрет не сохранился' 

    without_code = client.post(
        '/api/auth/change-password',
        json={'current_password': OLD, 'new_password': NEW},
        headers=_headers(token),
    )
    assert without_code.status_code == 400
    assert 'totp_code' in without_code.get_json()['error']

    wrong = client.post(
        '/api/auth/change-password',
        json={'current_password': OLD, 'new_password': NEW, 'totp_code': '000000'},
        headers=_headers(token),
    )
    assert wrong.status_code == 403
    assert _password_works(app, user_id, OLD), 'пароль сменился без верного кода 2FA'

    good = client.post(
        '/api/auth/change-password',
        json={
            'current_password': OLD,
            'new_password': NEW,
            'totp_code': pyotp.TOTP(secret).now(),
        },
        headers=_headers(token),
    )
    assert good.status_code == 200, good.get_json()


def test_frontend_sends_the_current_password():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    api = open(os.path.join(root, 'frontend', 'src', 'api', 'auth.ts'), encoding='utf-8').read()
    assert 'current_password' in api, 'клиент не присылает текущий пароль'
    page = open(
        os.path.join(root, 'frontend', 'src', 'pages', 'auth', 'LoginPage.tsx'),
        encoding='utf-8',
    ).read()
    assert 'changePassword(newPassword, currentPassword' in page, (
        'форма смены пароля не передаёт текущий пароль'
    )
