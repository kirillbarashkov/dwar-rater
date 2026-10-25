"""A47: запросы к API идут по одному правилу, а не мимо клиента.

Было два правила для одного и того же адреса: axios-клиент собирал базу как
`VITE_API_URL || ''`, а сырые вызовы и SSE — как `VITE_API_URL ||
window.location.origin`. Плюс сырые `fetch` не обрабатывали 401: при умершей
сессии пользователь видел вечный спиннер или сырую ошибку вместо перехода на
`/login`.

Решение: `apiFetch(path, init)` — токен, `Content-Type` и реакция на 401 те же,
что у интерсептора; `apiUrl(path)` — единственное правило сборки адреса (в том
числе для `EventSource`, который нельзя провести через `fetch`).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')
CLIENT = os.path.join(SRC, 'api', 'client.ts')


def _sources():
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for name in filenames:
            if name.endswith(('.ts', '.tsx')):
                yield os.path.join(dirpath, name)


def _code_only(text):
    without_block = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(
        line for line in without_block.split('\n') if not line.strip().startswith('//')
    )


def test_raw_fetch_lives_only_in_the_client():
    offenders = []
    for path in _sources():
        if os.path.abspath(path) == os.path.abspath(CLIENT):
            continue
        code = _code_only(open(path, encoding='utf-8').read())
        for number, line in enumerate(code.split('\n'), 1):
            if re.search(r'(?<![\w.])fetch\(', line):
                offenders.append(f'{os.path.relpath(path, SRC)}:{number}')
    assert not offenders, (
        'сырой fetch в обход клиента (не будет обработки 401):\n' + '\n'.join(offenders)
    )


def test_only_one_base_url_rule():
    offenders = []
    for path in _sources():
        code = _code_only(open(path, encoding='utf-8').read())
        if 'window.location.origin' in code:
            offenders.append(os.path.relpath(path, SRC))
    assert not offenders, f'второе правило сборки адреса: {offenders}'


def test_client_exposes_fetch_and_url_helpers():
    source = open(CLIENT, encoding='utf-8').read()
    assert 'export async function apiFetch' in source, 'нет apiFetch'
    assert 'export function apiUrl' in source, 'нет apiUrl — SSE не сможет собрать адрес'
    assert 'API_BASE_URL' in source, 'база берётся не из общего модуля констант'


def test_fetch_helper_handles_unauthorized():
    source = open(CLIENT, encoding='utf-8').read()
    assert '401' in source, 'apiFetch не реагирует на 401'
    assert "removeItem('auth_token')" in source, 'токен не сбрасывается при 401'
    assert "'/login'" in source, 'нет перехода на страницу входа'


def test_fetch_helper_attaches_the_token():
    source = open(CLIENT, encoding='utf-8').read()
    assert 'Bearer ${token}' in source, 'заголовок Authorization не ставится'


def test_streams_use_the_shared_url_helper():
    """SSE нельзя провести через fetch — но адрес обязан собираться общим правилом."""
    for rel in ('components/clan/MembershipImportTab.tsx',):
        source = open(os.path.join(SRC, rel), encoding='utf-8').read()
        assert 'apiUrl(' in source, f'{rel}: SSE-адрес собран не общим правилом'
