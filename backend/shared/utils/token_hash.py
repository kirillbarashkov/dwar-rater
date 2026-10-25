"""Хеширование токенов сессий: HMAC-SHA256 с серверным секретом (A52).

Токены генерируются `secrets.token_hex(32)` — 256 бит энтропии, подобрать их
оффлайн нельзя. Проблема была в другом: голый SHA-256 не требует секрета, поэтому
утечка таблицы `session_token` давала готовые хеши, по которым можно проверить
догадку о конкретном токене (например, найденном в логах — см. A41). Пароли в
этом проекте защищены bcrypt-ом, а токены — нет.

Теперь хеш считается ключом, которого в базе нет: HMAC-SHA256 с `SECRET_KEY`.
Хранение остаётся 64 hex-символа, поэтому колонка `token_hash` не меняется.

Старые строки, посчитанные голым SHA-256, продолжают работать: при успешном
совпадении хеш переписывается на HMAC. Без этого деплой разлогинил бы всех —
включая admin, которому нужен ещё и TOTP.
"""

import hashlib
import hmac
import logging
import os

_log = logging.getLogger(__name__)

_FALLBACK_KEY = 'dwar-rater-token-hash-fallback-key'


def _secret() -> bytes:
    secret = None
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            secret = (
                current_app.config.get('TOKEN_HASH_KEY')
                or current_app.config.get('SECRET_KEY')
            )
    except Exception:  # pragma: no cover - flask всегда доступен в рантайме
        secret = None
    if not secret:
        secret = os.environ.get('SECRET_KEY')
    if not secret:
        _log.warning('SECRET_KEY недоступен — токен хешируется ключом-заглушкой')
        secret = _FALLBACK_KEY
    return secret.encode()


def hash_token(token: str) -> str:
    """HMAC-SHA256 токена; результат — 64 hex, как и прежний SHA-256."""
    return hmac.new(_secret(), token.encode(), hashlib.sha256).hexdigest()


def legacy_hash_token(token: str) -> str:
    """Прежняя схема — только для чтения старых строк и их обновления."""
    return hashlib.sha256(token.encode()).hexdigest()
