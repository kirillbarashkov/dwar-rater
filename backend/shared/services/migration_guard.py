"""A6: политика поведения при провале миграций Alembic.

Вынесено из `app.py`, чтобы тест мог проверить решение, не импортируя модуль
`app` (тот на уровне модуля вызывает `create_app()` — миграции, сиды, тяжёлые
побочные эффекты).

`db.create_all()` создаёт схему по моделям: он **не** добавляет столбцы в
существующие таблицы и **не** проставляет `alembic_version`. То есть после
провала миграции приложение продолжает работать на схеме, которая расходится с
моделями, и падает уже в бою (`UndefinedColumn`). Поэтому в проде падение
миграции — фатальная ошибка старта.
"""


def handle_migration_failure(err, *, strict: bool, logger=None, create_all=None):
    """Решить судьбу приложения при провале миграции.

    strict=True  → выбросить RuntimeError (контейнер не стартует, деплой
                   падает на health-check вместо тихой порчи схемы);
    strict=False → предупредить и создать схему по моделям (dev/SQLite).
    """
    if strict:
        if logger:
            logger.error(
                'Alembic migration failed and STRICT_MIGRATIONS=true — '
                f'отказываюсь стартовать на create_all(): {err}'
            )
        raise RuntimeError(f'Миграция БД провалилась, старт запрещён: {err}') from (
            err if isinstance(err, BaseException) else None
        )

    if logger:
        logger.warning(
            f'Alembic migration failed, falling back to db.create_all(): {err}'
        )
    if create_all:
        create_all()
