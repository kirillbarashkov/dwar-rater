"""A14: предмиграционная копия обязана существовать или честно провалиться.

Раньше `pg_dump` вызывался с `capture_output=True`, вывод выбрасывался, код
возврата не проверялся, а в лог всё равно шло «pre-migration backup created».
Тесты фиксируют: файл действительно создаётся, а при любом сбое — None и запись
об ошибке, без ложного «created».
"""

import gzip
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.services.pre_migration_backup import create_pre_migration_backup


class _Result:
    def __init__(self, returncode=0, stdout=b'', stderr=b''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _Logger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, msg):
        self.infos.append(msg)

    def error(self, msg):
        self.errors.append(msg)


def _runner(result):
    def run(*args, **kwargs):
        return result
    return run


def test_successful_dump_writes_a_valid_gzip(tmp_path):
    log = _Logger()
    path = create_pre_migration_backup(
        str(tmp_path), logger=log, runner=_runner(_Result(stdout=b'-- dump\n')
    ))
    assert path is not None, log.errors
    assert os.path.exists(path)
    with gzip.open(path, 'rb') as fh:
        assert fh.read() == b'-- dump\n'
    assert any('created' in m for m in log.infos)


def test_failed_pg_dump_returns_none_and_logs_error(tmp_path):
    log = _Logger()
    path = create_pre_migration_backup(
        str(tmp_path),
        logger=log,
        runner=_runner(_Result(returncode=1, stderr=b'connection refused')),
    )
    assert path is None
    assert not os.listdir(tmp_path), 'при сбое не должно оставаться файлов'
    assert log.errors and 'FAILED' in log.errors[0]
    assert not any('created' in m for m in log.infos), (
        'лог не должен утверждать, что копия создана'
    )


def test_empty_dump_is_treated_as_failure(tmp_path):
    """pg_dump может вернуть 0 и ничего не отдать — пустой файл бесполезен."""
    log = _Logger()
    path = create_pre_migration_backup(
        str(tmp_path), logger=log, runner=_runner(_Result(stdout=b''))
    )
    assert path is None
    assert not os.listdir(tmp_path)
    assert log.errors


def test_missing_pg_dump_binary_is_a_logged_failure(tmp_path):
    log = _Logger()

    def boom(*args, **kwargs):
        raise FileNotFoundError('pg_dump')

    path = create_pre_migration_backup(str(tmp_path), logger=log, runner=boom)
    assert path is None
    assert log.errors


def test_existing_directory_is_reused(tmp_path):
    nested = tmp_path / 'pre_migration'
    log = _Logger()
    path = create_pre_migration_backup(
        str(nested), logger=log, runner=_runner(_Result(stdout=b'x')
    ))
    assert path is not None
    assert os.path.dirname(path) == str(nested)
