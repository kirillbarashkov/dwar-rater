"""A37: SSE аутентифицируется короткоживущим билетом, а не токеном сессии в URL.

`EventSource` не умеет отправлять заголовки, поэтому клиент передавал основной
токен сессии прямо в адресе: `?token=...`. Такой URL попадает в историю браузера,
в логи nginx и в Referer — то есть токен с жизнью 8–24 часа утекал именно там,
где его не ищут. A41 закрыл логи nginx, но сама передача токена в URL осталась.

Решение — билет: `issue_ticket(user_id)` = HMAC-подпись над `user_id.exp`,
живёт 60 секунд, проверяется без обращения к БД. Он stateless (ключ — `SECRET_KEY`),
поэтому не требует ни таблицы, ни миграции и работает при двух gunicorn-воркерах
(хранилище в памяти процесса не подошло бы).

Компромисс зафиксирован в коде: билет не одноразовый в строгом смысле — минуту
его можно переиспользовать. Это меньшее зло, чем сессионный токен в URL, и не
требует состояния.

Старый путь (`?token=` и `Authorization`) сохранён на время перехода, иначе
открытые вкладки и внешние клиенты сломались бы в день релиза.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.utils.sse_ticket import TICKET_TTL, issue_ticket, verify_ticket  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ticket_round_trip():
    ticket = issue_ticket(42)
    assert verify_ticket(ticket) == 42


def test_ticket_expires(monkeypatch):
    """ttl зажимается снизу (билет не может родиться мёртвым), поэтому срок
    проверяем сдвигом часов, а не отрицательным ttl."""
    import time as time_module

    original = time_module.time
    ticket = issue_ticket(42, ttl=1)
    assert verify_ticket(ticket) == 42
    monkeypatch.setattr(time_module, 'time', lambda: original() + 10)
    assert verify_ticket(ticket) is None, 'просроченный билет принят'


def test_tampered_ticket_is_rejected():
    ticket = issue_ticket(42)
    encoded, signature = ticket.rsplit('.', 1)
    forged = issue_ticket(7).split('.')[0] + '.' + signature
    assert verify_ticket(forged) is None, 'подпись не защищает user_id'
    assert verify_ticket(encoded + '.' + ('0' * len(signature))) is None
    assert verify_ticket('') is None
    assert verify_ticket(None) is None
    assert verify_ticket('garbage') is None


def test_ttl_is_short():
    assert TICKET_TTL <= 120, 'билет живёт слишком долго — смысл теряется'


def test_ticket_signature_depends_on_the_secret(monkeypatch):
    ticket = issue_ticket(42)
    monkeypatch.setenv('SECRET_KEY', 'another-secret-for-this-probe')
    assert verify_ticket(ticket) is None, 'подпись не зависит от серверного секрета'


def test_sse_endpoints_stop_reading_the_token_directly():
    """Три SSE-эндпоинта казны обязаны идти через общий резолвер."""
    routes = open(
        os.path.join(ROOT, 'backend', 'features', 'clan_info', 'routes.py'), encoding='utf-8'
    ).read()
    assert routes.count('current_user = resolve_sse_user(request)') == 3, (
        'часть SSE-эндпоинтов снова разбирает токен сама'
    )
    assert 'request.args.get("token")' not in routes, (
        'остался прямой разбор токена из query — билет будет игнорироваться'
    )


def test_ticket_endpoint_exists_and_requires_a_session():
    auth = open(
        os.path.join(ROOT, 'backend', 'features', 'auth', 'routes.py'), encoding='utf-8'
    ).read()
    assert "/api/auth/sse-ticket" in auth
    block = auth.split('def issue_sse_ticket')[1][:600]
    assert 'find_by_token' in block, 'билет выдаётся без проверки сессии'
    assert '401' in block


def test_frontend_uses_the_ticket_in_event_source_urls():
    source = open(
        os.path.join(ROOT, 'frontend', 'src', 'components', 'clan', 'MembershipImportTab.tsx'),
        encoding='utf-8',
    ).read()
    assert 'sseTicket()' in source
    assert '?ticket=' in source
    assert '?token=' not in source, 'токен сессии снова уходит в адрес потока'
