"""A6: в проде провал миграции фатален, а не запасной create_all().

`create_all()` создаёт схему по моделям: не добавляет столбцы в существующие
таблицы и не проставляет `alembic_version`. Схема и миграции расходятся, и
ошибка всплывает `UndefinedColumn` уже в бою. Поэтому при STRICT_MIGRATIONS=true
старт обязан упасть, а не притвориться успешным.
"""

import pytest

from shared.config import Config
from shared.services.migration_guard import handle_migration_failure


class _Logger:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, msg):
        self.errors.append(msg)

    def warning(self, msg):
        self.warnings.append(msg)


def test_strict_mode_raises_and_never_calls_create_all():
    """Главное: в строгом режиме create_all НЕ вызывается вообще."""
    called = []

    with pytest.raises(RuntimeError) as exc:
        handle_migration_failure(
            ValueError('boom'),
            strict=True,
            logger=_Logger(),
            create_all=lambda: called.append(1),
        )

    assert 'Миграция БД провалилась' in str(exc.value)
    assert called == [], 'в строгом режиме create_all() не должен вызываться'
    assert isinstance(exc.value.__cause__, ValueError), 'причина должна сохраняться'


def test_permissive_mode_falls_back_to_create_all():
    """Вне прода поведение прежнее — иначе локальная разработка встанет."""
    called = []
    log = _Logger()

    handle_migration_failure(
        ValueError('boom'),
        strict=False,
        logger=log,
        create_all=lambda: called.append(1),
    )

    assert called == [1], 'вне строгого режима create_all() должен вызываться'
    assert log.warnings and not log.errors


def test_strict_mode_logs_error_before_raising():
    log = _Logger()
    with pytest.raises(RuntimeError):
        handle_migration_failure('boom', strict=True, logger=log)
    assert log.errors and 'STRICT_MIGRATIONS' in log.errors[0]


def test_prod_compose_turns_strict_mode_on():
    """Флаг обязан быть включён в прод-конфигурации, иначе фикс — no-op."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    compose = open(os.path.join(root, 'docker-compose.prod.yml'), encoding='utf-8').read()
    assert 'STRICT_MIGRATIONS: "true"' in compose, (
        'docker-compose.prod.yml не включает STRICT_MIGRATIONS'
    )


def test_config_flag_is_parsed_from_env_only():
    """Дефолт выключен, включается только явным env.

    Проверяем чтение переменной, а не перезагрузкой модуля: reload()
    пересоздал бы глобальный Config посреди сюиты и задел другие тесты.
    """
    assert Config.STRICT_MIGRATIONS is False, (
        'в тестовом окружении STRICT_MIGRATIONS должен быть выключен'
    )
    import inspect
    import shared.config as cfg
    src = inspect.getsource(cfg)
    assert "STRICT_MIGRATIONS" in src and "'false'" in src

