"""A50: сетевой обрыв не должен разлогинивать пользователя.

Было:

```tsx
.catch(() => {
  clearSession();
  setUser(null);
  setPermissions({});
})
```

`clearSession()` удаляет токен из `localStorage`, то есть **уничтожает сессию**.
Любая ошибка запроса — секундный обрыв Wi-Fi, таймаут, 502 от прокси — выкидывала
пользователя из аккаунта, и восстановить вход можно было только заново.

Решение: сбрасываем сессию только когда сервер прямо сказал, что она
недействительна (401) или аккаунт деактивирован (403, так отвечает `/api/auth/me`
для выключенного пользователя). На остальных ошибках оставляем сохранённые
данные: пользователь увидит ошибку запроса, но не потеряет вход.

Тесты статические: фронтенд-раннера в проекте нет, а проверяется структура
обработчика.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUTH = os.path.join(ROOT, 'frontend', 'src', 'hooks', 'useAuth.tsx')


def _source():
    return open(AUTH, encoding='utf-8').read()


def _code_only(text):
    without_block = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(
        line for line in without_block.split('\n') if not line.strip().startswith('//')
    )


def _fetch_me_catch_body():
    code = _code_only(_source())
    start = code.index('fetchMe()')
    catch = code.index('.catch(', start)
    depth, index = 0, code.index('{', catch)
    while index < len(code):
        if code[index] == '{':
            depth += 1
        elif code[index] == '}':
            depth -= 1
            if depth == 0:
                break
        index += 1
    return code[catch:index]


def test_session_is_cleared_only_for_invalid_sessions():
    body = _fetch_me_catch_body()
    assert '401' in body, 'обработчик не различает истёкшую сессию'
    assert '403' in body, 'обработчик не различает деактивированный аккаунт'
    # clearSession обязан стоять внутри ветки, а не первой строкой обработчика.
    first_statement = next(
        line.strip() for line in body.split('\n')[1:] if line.strip()
    )
    assert first_statement != 'clearSession();', (
        'clearSession вызывается до проверки статуса — обрыв связи снова разлогинит'
    )


def test_network_error_keeps_the_stored_session():
    body = _fetch_me_catch_body()
    assert 'getStoredUser()' in body, 'при сетевой ошибке не восстанавливается пользователь'
    assert 'getStoredPermissions()' in body, 'при сетевой ошибке не восстанавливаются права'


def test_no_bare_clear_session_in_the_provider():
    """Ни одно место в провайдере не должно стирать сессию без разбора ошибки."""
    code = _code_only(_source())
    for match in re.finditer(r'clearSession\(\)', code):
        window = code[max(0, match.start() - 400):match.start()]
        assert ('401' in window or '403' in window or 'logout' in window.lower()), (
            'clearSession вызывается без проверки статуса ошибки'
        )


def test_status_is_read_from_the_axios_error_shape():
    code = _code_only(_source())
    assert 'response?.status' in code, 'статус не извлекается из ответа'
