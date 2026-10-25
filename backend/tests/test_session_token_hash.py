"""A52: токены сессий хешируются ключом, которого нет в базе.

Было — `hashlib.sha256(token.encode()).hexdigest()`. Токены случайные
(`secrets.token_hex(32)`, 256 бит), подобрать их оффлайн нельзя, поэтому это не
«слабое хеширование пароля». Настоящая проблема другая: голый SHA-256 не требует
секрета, и утечка таблицы `session_token` давала возможность **проверить**
конкретный токен — например, найденный в логах nginx (A41). Пароли в проекте
защищены bcrypt-ом, токены — нет.

Теперь — HMAC-SHA256 с `SECRET_KEY`. Хранение — те же 64 hex-символа, колонка
`token_hash` не меняется.

Ключевое требование к решению: деплой не должен разлогинивать всех (для admin
это ещё и повторный TOTP). Поэтому старые строки, посчитанные голым SHA-256,
находятся вторым запросом и обновляются до HMAC при первом успешном совпадении.
"""

import hashlib
import hmac
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_app import create_test_app  # noqa: E402
from shared.models import db  # noqa: E402
from shared.models.user import User  # noqa: E402
from shared.rbac.models import SessionToken  # noqa: E402
from shared.utils import token_hash  # noqa: E402

TOKEN = 'a' * 64


@pytest.fixture()
def app():
    application = create_test_app()
    with application.app_context():
        db.create_all()
        db.session.query(SessionToken).delete()
        yield application
        db.session.rollback()


def test_hash_is_not_the_plain_digest():
    digest = SessionToken.hash_token(TOKEN)
    assert digest == token_hash.hash_token(TOKEN)
    assert digest != hashlib.sha256(TOKEN.encode()).hexdigest(), (
        'хеш снова совпадает с голым SHA-256 — секрет не участвует'
    )


def test_hash_is_stable_and_hex():
    first = SessionToken.hash_token(TOKEN)
    assert first == SessionToken.hash_token(TOKEN)
    assert len(first) == 64, 'длина не влезает в token_hash VARCHAR(64)'
    int(first, 16)  # падает, если это не hex


def test_different_secrets_give_different_hashes(app):
    own = SessionToken.hash_token(TOKEN)
    with app.app_context():
        app.config['SECRET_KEY'] = 'another-secret-for-this-probe'
        other = SessionToken.hash_token(TOKEN)
    assert own != other, 'хеш не зависит от серверного секрета'


def _make_user():
    user = User(
        username=f'tokhash-{uuid.uuid4().hex[:10]}',
        password_hash='bcrypt-probe-not-used',
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_new_session_is_found_by_hmac(app):
    user = _make_user()
    row = SessionToken(
        user_id=user.id,
        token_hash=SessionToken.hash_token(TOKEN),
        expires_at=db.func.now(),
    )
    db.session.add(row)
    db.session.commit()

    found = SessionToken.find_by_token(TOKEN)
    assert found is not None and found.id == row.id


def test_legacy_row_still_logs_in_and_is_upgraded(app):
    """Сессии, выданные до релиза, обязаны продолжать работать."""
    user = _make_user()
    legacy = token_hash.legacy_hash_token(TOKEN)
    row = SessionToken(
        user_id=user.id,
        token_hash=legacy,
        expires_at=db.func.now(),
    )
    db.session.add(row)
    db.session.commit()

    found = SessionToken.find_by_token(TOKEN)
    assert found is not None, 'старая сессия перестала находиться — деплой разлогинит всех'
    db.session.expire_all()
    upgraded = db.session.get(SessionToken, row.id)
    assert upgraded.token_hash == SessionToken.hash_token(TOKEN), (
        'строка не обновлена до HMAC и останется уязвимой к проверке догадки'
    )
    assert hmac.compare_digest(upgraded.token_hash, SessionToken.hash_token(TOKEN))


def test_unknown_token_is_not_found(app):
    _make_user()
    assert SessionToken.find_by_token('b' * 64) is None
    assert SessionToken.find_by_token('') is None
