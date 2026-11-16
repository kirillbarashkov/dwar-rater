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
"""

import os
import re

import pytest

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


@pytest.mark.parametrize(
    'url',
    [
        '/api/admin/users/sync',
        '/api/admin/backups',
        '/api/admin/backups/dwar_rater_backup_20260101_000000.sql.gz/restore',
    ],
)
def test_admin_post_is_not_rejected_by_the_middleware(client, admin_headers, url):
    """С `{}` запрос доходит до обработчика; без тела — 415 от middleware.

    Статус обработчика здесь не проверяется (pg_dump в тестовом контейнере может
    отсутствовать, а восстановление вообще деструктивно) — важно только, что
    гейт тела больше не мешает.
    """
    assert client.post(url, headers=admin_headers).status_code == 415

    resp = client.post(url, headers=admin_headers, json={})
    assert resp.status_code != 415, (
        f'{url}: с телом запрос всё равно отбит middleware — {resp.get_data(as_text=True)}'
    )
