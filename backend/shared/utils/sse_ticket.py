"""A37: одноразовый короткоживущий билет для SSE вместо токена сессии в URL.

`EventSource` не умеет отправлять заголовки, поэтому клиент передавал основной
токен сессии в query-параметре: `?token=...`. Такой URL попадает в историю
браузера, в логи nginx и в Referer, и полный токен (8–24 часа жизни) утекал
именно там, где его меньше всего ждут.

Билет решает это без изменения модели сессий:

* `issue_ticket(user_id)` — HMAC-подпись над `user_id.exp`, живёт 60 секунд;
* `verify_ticket(ticket)` — проверяет подпись и срок, возвращает `user_id`.

Билет stateless: подпись считается ключом `SECRET_KEY`, поэтому не нужен ни
стол, ни миграция, и он работает при нескольких gunicorn-воркерах (воркеров 2 —
хранилище в памяти процесса не подошло бы).

Плата: билет не «одноразовый» в строгом смысле — в течение минуты его можно
переиспользовать. Это осознанный компромисс: утечка минутного билета даёт
меньше, чем утечка сессионного токена, а отказ от состояния сохраняет
масштабирование.
"""

import base64
import hashlib
import hmac
import os
import time

TICKET_TTL = 60


def _secret() -> bytes:
    secret = os.environ.get('SECRET_KEY') or 'dwar-rater-sse-ticket-fallback'
    return secret.encode()


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def issue_ticket(user_id: int, ttl: int = TICKET_TTL) -> str:
    """Вернуть билет вида `<base64(user_id.exp)>.<подпись>`."""
    payload = f'{int(user_id)}.{int(time.time()) + max(1, int(ttl))}'
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')
    return f'{encoded}.{_sign(payload)}'


def verify_ticket(ticket: str | None) -> int | None:
    """Проверить билет. Возвращает user_id или None, если билет негоден."""
    if not ticket or '.' not in ticket:
        return None
    encoded, signature = ticket.rsplit('.', 1)

    padding = '=' * (-len(encoded) % 4)
    try:
        payload = base64.urlsafe_b64decode(encoded + padding).decode()
    except (ValueError, UnicodeDecodeError):
        return None

    if not hmac.compare_digest(_sign(payload), signature):
        return None

    try:
        user_id_text, exp_text = payload.split('.')
        user_id, expires_at = int(user_id_text), int(exp_text)
    except ValueError:
        return None

    if expires_at < int(time.time()):
        return None
    return user_id


def resolve_sse_user(request):
    """Пользователь по билету, а если его нет — по прежнему `?token=`/заголовку.

    Поддержка `?token=` оставлена на время перехода: старые вкладки и внешние
    клиенты не должны ломаться в день релиза. Когда фронтенд везде перейдёт на
    билет, эту ветку можно удалить.
    """
    from datetime import datetime, timezone

    from shared.models.user import User
    from shared.rbac.models import SessionToken

    user_id = verify_ticket(request.args.get('ticket'))
    if user_id is not None:
        user = User.query.get(user_id)
        return user if user and user.is_active else None

    token = request.args.get('token') or request.headers.get(
        'Authorization', ''
    ).replace('Bearer ', '')
    if not token:
        return None

    session_token = SessionToken.find_by_token(token)
    if not session_token:
        return None

    expires = session_token.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return None
    return User.query.get(session_token.user_id)
