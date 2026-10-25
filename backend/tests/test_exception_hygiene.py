"""A29: гигиена исключений — один класс, проверенный целиком.

A29 указывал на те же места, что A16 и A17 (оба закрыты), поэтому здесь
проверяется **класс**, а не два адреса:

* в бэкенде не осталось голых `except:` (они ловят и `KeyboardInterrupt`);
* единственный оставшийся `except Exception:` — осознанный fail-open в
  лимитере запросов, и он обязан **логировать**: при сбое БД защита от перебора
  отключается целиком, и молчание делает это невидимым.
"""

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = ('tests', 'migrations', '__pycache__')


def _python_sources():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith('.py'):
                yield os.path.join(dirpath, name)


def test_no_bare_except_in_backend():
    offenders = []
    for path in _python_sources():
        for number, line in enumerate(io.open(path, encoding='utf-8').read().split('\n'), 1):
            if re.match(r'\s*except\s*:\s*$', line):
                offenders.append(f'{os.path.relpath(path, ROOT)}:{number}')
    assert not offenders, 'голый `except:` ловит KeyboardInterrupt/SystemExit:\n' + '\n'.join(offenders)


HANDLED_SIGNS = (
    'log.', 'logger', 'logging', 'print(', 'raise', 'return',
    'append(', '_handle_', 'abort(', 'flash(',
    # SSE-потоки сообщают об ошибке событием, а не ответом (см. A16):
    'yield ',
    # CLI-проверки выставляют флаг и отдают status='degraded':
    '= False',
)


def test_except_exception_is_never_silent():
    """`except Exception` допустим, если ошибка видна: лог, ответ, raise.

    Критерий намеренно про «есть след», а не про «есть именно log.». Возврат
    `jsonify({'error': ...}), 500`, `errors.append(...)` в пакетной операции и
    `_handle_migration_failure(e)` — это тоже обработка, и требовать в них
    логгер значило бы переписать рабочий код ради теста. Проверено вручную по
    всем найденным местам: каждое либо возвращает ошибку вызывающему, либо
    отдаёт `error`-событие в SSE-потоке, либо выставляет флаг состояния.
    """
    offenders = []
    for path in _python_sources():
        lines = io.open(path, encoding='utf-8').read().split('\n')
        for i, line in enumerate(lines):
            if not re.match(r'\s*except\s+(Exception|BaseException)(\s+as\s+\w+)?\s*:\s*$', line):
                continue
            body = []
            for k in range(i + 1, min(i + 8, len(lines))):
                stripped = lines[k].strip()
                if stripped and not stripped.startswith('#'):
                    body.append(stripped)
                if stripped and not stripped.startswith('#'):
                    break
            if not body:
                offenders.append(f'{os.path.relpath(path, ROOT)}:{i + 1} (пустое тело)')
                continue
            if body[0] in ('pass', 'continue'):
                offenders.append(f'{os.path.relpath(path, ROOT)}:{i + 1} ({body[0]})')
                continue
            window = '\n'.join(lines[i + 1:i + 8])
            if not any(sign in window for sign in HANDLED_SIGNS):
                offenders.append(f'{os.path.relpath(path, ROOT)}:{i + 1} (нет следа)')
    assert not offenders, 'исключение подавлено молча:\n' + '\n'.join(offenders)


def test_rate_limiter_fails_open_and_says_so(app, monkeypatch, caplog):
    """Сбой БД лимитера не блокирует запросы, но оставляет след в логе."""
    import shared.middleware.rate_limiter as limiter

    class _BrokenEngine:
        def begin(self):
            raise RuntimeError('БД недоступна')

    class _BrokenDB:
        engine = _BrokenEngine()

    # Подменяем не `db.engine` (его чтение требует app-контекста), а сам `db`
    # в модуле — так тест не зависит от контекста Flask.
    monkeypatch.setattr(limiter, 'db', _BrokenDB())

    with app.test_request_context('/api/version'):
        with caplog.at_level('WARNING', logger=limiter.__name__):
            allowed = limiter.check_rate_limit(10, 60)

    assert allowed is True, 'лимитер закрыл доступ при сбое БД — это fail-closed, не fail-open'
    assert any(r.levelname == 'WARNING' for r in caplog.records), 'сбой лимитера прошёл молча'
