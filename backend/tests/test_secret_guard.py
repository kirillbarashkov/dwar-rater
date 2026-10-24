"""A22: дефолтные секреты не должны проходить молча.

`SECRET_KEY` и `ADMIN_PASS` имели дефолты прямо в коде (`dev-secret-key-change-me`,
`admin`). В проде compose требует эти переменные без дефолта, но сам код продолжал
принимать «дефолтное» значение и работать как ни в чём не бывало — то есть
опечатка в `.env` или скопированный пример не приводили ни к какой ошибке.

Проверка различает два режима:
* `STRICT_SECRETS=true` (прод) — старт падает;
* иначе — CRITICAL в лог, чтобы локальная разработка не умирала.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from shared.config import (
    INSECURE_SECRETS,
    Config,
    enforce_secrets,
    inspect_secrets,
)

GOOD_SECRET = 'Xk9-vT2m-Qw7p-Lr4z-Bn8s'
GOOD_PASS = 'Yh3-rM6t-Kp1w-Zd9c'


def test_good_secrets_produce_no_problems():
    assert inspect_secrets(GOOD_SECRET, GOOD_PASS) == []


def test_each_known_default_is_detected():
    for value in INSECURE_SECRETS['SECRET_KEY']:
        assert inspect_secrets(value, GOOD_PASS), f'SECRET_KEY={value!r} не пойман'
    for value in INSECURE_SECRETS['ADMIN_PASS']:
        assert inspect_secrets(GOOD_SECRET, value), f'ADMIN_PASS={value!r} не пойман'


def test_empty_and_none_are_detected():
    assert 'SECRET_KEY не задан' in inspect_secrets('', GOOD_PASS)
    assert 'SECRET_KEY не задан' in inspect_secrets(None, GOOD_PASS)
    assert 'ADMIN_PASS не задан' in inspect_secrets(GOOD_SECRET, '   ')


def test_strict_mode_raises_and_names_the_variable():
    with pytest.raises(RuntimeError) as err:
        enforce_secrets(True, secret_key='dev-secret-key-change-me', admin_pass=GOOD_PASS)
    assert 'SECRET_KEY' in str(err.value)


def test_strict_mode_raises_for_default_admin_password():
    with pytest.raises(RuntimeError) as err:
        enforce_secrets(True, secret_key=GOOD_SECRET, admin_pass='admin')
    assert 'ADMIN_PASS' in str(err.value)


def test_non_strict_mode_logs_critical_but_does_not_raise(caplog):
    logger = logging.getLogger('test.secrets')
    with caplog.at_level(logging.CRITICAL, logger='test.secrets'):
        problems = enforce_secrets(False, logger=logger,
                                   secret_key=GOOD_SECRET, admin_pass='admin')
    assert problems, 'проблема не найдена'
    assert any(r.levelname == 'CRITICAL' for r in caplog.records), 'нет CRITICAL в логе'
    assert any('ADMIN_PASS' in r.getMessage() for r in caplog.records)


def test_good_secrets_never_raise_even_in_strict_mode():
    assert enforce_secrets(True, secret_key=GOOD_SECRET, admin_pass=GOOD_PASS) == []


def test_create_app_calls_the_guard():
    """Страж: проверка обязана вызываться из фабрики, иначе она мертва."""
    import inspect as pyinspect

    import app as app_module

    source = pyinspect.getsource(app_module.create_app)
    assert '_enforce_secrets()' in source, 'create_app не вызывает _enforce_secrets'
    guard_source = pyinspect.getsource(app_module._enforce_secrets)
    assert 'Config.STRICT_SECRETS' in guard_source, 'флаг STRICT_SECRETS не проброшен'


def test_strict_flag_defaults_to_false():
    """Локальная разработка и тесты не должны падать из-за дефолтов."""
    assert Config.STRICT_SECRETS is False


def test_prod_compose_passes_both_secrets():
    """Прод обязан получать секреты из окружения (без дефолтов в compose)."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    compose = open(os.path.join(root, 'docker-compose.prod.yml'), encoding='utf-8').read()
    assert 'SECRET_KEY: ${SECRET_KEY}' in compose
    assert 'ADMIN_PASS: ${ADMIN_PASS}' in compose
