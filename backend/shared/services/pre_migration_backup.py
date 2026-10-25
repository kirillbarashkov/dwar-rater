"""A14: предмиграционная копия БД, которая действительно создаётся.

Раньше `app.py` вызывал `subprocess.run(['pg_dump', ...], capture_output=True)` и
выбрасывал результат: файла не появлялось, код возврата не проверялся, а в лог
всё равно писалось «pre-migration backup created». То есть при сбое миграции
опереться было не на что, а оператор считал, что копия есть.

Замечание о долговечности: файл кладётся в каталог внутри контейнера, поэтому
переживает сбой миграции, но не пересоздание контейнера. Постоянное хранение —
задача A39 (бэкапы в томе), здесь закрывается только правдивость и
работоспособность копии.
"""

import gzip
import os
import subprocess
from datetime import datetime, timezone


def create_pre_migration_backup(dump_dir, *, logger=None, runner=None):
    """Создать gzip-дамп БД перед миграцией.

    Возвращает путь к файлу или None, если дамп не удался. Никогда не
    притворяется успехом: при ненулевом коде возврата pg_dump или пустом
    выводе файл удаляется.
    """
    runner = runner or subprocess.run
    os.makedirs(dump_dir, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    # A39: имя должно попадать в шаблон `dwar_rater_backup_*.sql.gz`. Иначе
    # `make restore`, ротация и pre-destroy-check (все ищут этот шаблон)
    # премиграционную копию не видят — она лежит рядом и считается мусором.
    path = os.path.join(dump_dir, f'dwar_rater_backup_pre_migration_{stamp}.sql.gz')

    user = os.environ.get('POSTGRES_USER', 'dwar')
    dbname = os.environ.get('POSTGRES_DB', 'dwar_rater')
    # A39: без -h/-p pg_dump идёт в локальный сокет. В контейнере бэкенда
    # Postgres'а нет — дамп падал с "connection to server on socket ... failed",
    # то есть премиграционных копий в проде не было вообще.
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    port = os.environ.get('POSTGRES_PORT', '5432')

    try:
        result = runner(
            ['pg_dump', '-h', host, '-p', port, '-U', user, '-d', dbname,
             '--no-owner', '--no-acl'],
            capture_output=True,
            timeout=300,
        )
    except Exception as err:  # pg_dump отсутствует, таймаут, OSError
        if logger:
            logger.error(f'Pre-migration backup FAILED (pg_dump): {err}')
        return None

    if getattr(result, 'returncode', 1) != 0:
        stderr = getattr(result, 'stderr', b'') or b''
        if logger:
            logger.error(
                'Pre-migration backup FAILED: pg_dump вернул '
                f'{result.returncode}: {stderr[:300]!r}'
            )
        return None

    payload = getattr(result, 'stdout', b'') or b''
    if not payload:
        if logger:
            logger.error('Pre-migration backup FAILED: pg_dump вернул пустой дамп')
        return None

    try:
        with gzip.open(path, 'wb') as fh:
            fh.write(payload)
        # Проверка, что архив читается: обрезанный gzip бесполезен ровно тогда,
        # когда понадобится.
        with gzip.open(path, 'rb') as fh:
            fh.read(1)
    except OSError as err:
        if logger:
            logger.error(f'Pre-migration backup FAILED (запись файла): {err}')
        try:
            os.remove(path)
        except OSError:
            pass
        return None

    if logger:
        logger.info(
            f'Pre-migration backup created: {path} ({len(payload) / 1024:.1f} KB)'
        )
    return path
