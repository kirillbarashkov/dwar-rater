"""Каждый POST из фронтенда обязан уходить с телом — иначе 415.

Глобальный `security_checks` в `app.py` отвечает 415 на POST без
`Content-Type: application/json`, а axios не ставит этот заголовок, если тела
нет. Так молча ломались: запрос билета SSE (импорт состава клана переставал
стартовать) и три кнопки админки — «синхронизировать пользователей»,
«создать бэкап», «восстановить бэкап» (TD-13, 16.11.2026).

Тест статический: он ловит НОВЫЙ вызов без тела на этапе ревью, а не в проде.
Проверяются только вызовы `apiClient.post(...)` (axios-клиент проекта); пути,
которые middleware пропускает по белому списку (логин, logout), исключены —
список читается из `app.py`, чтобы не расходиться с кодом.

Живая часть намеренно работает через заглушки view-функций: реальный
`users/sync` создал бы пользователей из состава клана, а `backups` запустил бы
pg_dump. Тест не имеет права писать в общую тестовую БД — иначе он роняет чужой
модуль при другом порядке запуска (поллюция между модулями: зелёный локально и
красный в CI).
"""

import os
import re

import pytest
from flask import jsonify

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')
APP_PY = os.path.join(ROOT, 'backend', 'app.py')

# apiClient.post(url) | apiClient.post<T>(url) | apiClient.post(urlVar)
BODYLESS_POST = re.compile(
    r"apiClient\.post(?:<[^>]*>)?\(\s*"
    r"(?P<arg>[`'\"][^`'\"]*[`'\"]|[A-Za-z_$][\w$.]*)"
    r"\s*\)",
    re.S,
)

# Путь внутри литерала: `...${expr}...` → шаблон, сравнивать с белым списком нельзя.
TEMPLATE_EXPR = re.compile(r"\$\{[^}]*\}")

RESTORE_URL = '/api/admin/backups/dwar_rater_backup_20260101_000000.sql.gz/restore'

TARGETS = (
    ('admin.sync_users_from_clan', '/api/admin/users/sync', lambda: jsonify({'status': 'stub'})),
    ('admin.create_backup', '/api/admin/backups', lambda: jsonify({'status': 'stub'})),
    ('admin.restore_backup', RESTORE_URL, lambda filename: jsonify({'status': 'stub'})),
)


def _middleware_whitelist():
    """Пути, которые `security_checks` пропускает (проверка тела к ним не идёт)."""
    app_source = open(APP_PY, encoding='utf-8').read()
    match = re.search(r'request\.path in \(([^)]*)\)', app_source)
    assert match, 'не нашёл белый список путей в app.py::security_checks'
    return set(re.findall(r"'([^']+)'", match.group(1)))


def _normalise(raw_arg):
    literal = raw_arg[1:-1]
    return literal, bool(TEMPLATE_EXPR.search(literal))


def test_no_bodyless_post_calls():
    whitelist = _middleware_whitelist()
    offenders = []

    for dirpath, _, filenames in os.walk(SRC):
        for filename in filenames:
            if not filename.endswith(('.ts', '.tsx')):
                continue
            path = os.path.join(dirpath, filename)
            text = open(path, encoding='utf-8').read()
            for match in BODYLESS_POST.finditer(text):
                literal, is_template = _normalise(match.group('arg').strip())
                if not is_template and literal in whitelist:
                    continue
                line = text.count('\n', 0, match.start()) + 1
                where = os.path.relpath(path, ROOT).replace('\\', '/')
                offenders.append(f'{where}:{line} → {match.group(0)[:70]}')

    assert not offenders, (
        'POST без тела получит 415 (app.py::security_checks). Добавь `{}`:\n'
        + '\n'.join(offenders)
    )


@pytest.mark.parametrize('url', [url for _, url, _ in TARGETS])
def test_bodyless_post_is_rejected_by_the_middleware(client, admin_headers, url):
    """Без тела запрос отбивается до обработчика — белый список его не спасает."""
    assert client.post(url, headers=admin_headers).status_code == 415


@pytest.mark.parametrize('endpoint,url,stub', TARGETS)
def test_json_body_reaches_the_handler(app, client, admin_headers, endpoint, url, stub):
    """С `{}` запрос проходит middleware и доходит до обработчика (заглушки)."""
    original = app.view_functions.get(endpoint)
    app.view_functions[endpoint] = stub
    try:
        resp = client.post(url, headers=admin_headers, json={})
    finally:
        if original is not None:
            app.view_functions[endpoint] = original
    assert resp.status_code == 200, f'{url}: {resp.get_data(as_text=True)}'
