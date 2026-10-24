"""A13: ротация бэкапов — проверяем именно то, что удаляет файлы.

`scripts/backup-rotate.sh` сносит старые дампы. Ошибка в пороге или в маске
файлов стоит всех резервных копий сразу, поэтому тесты фиксируют защиты:

* удаляются только `dwar_rater_backup_*.sql.gz` в самом каталоге;
* чужие файлы и подкаталоги не трогаются;
* пустой/нечисловой/нулевой порог ВЫКЛЮЧАЕТ ротацию (а не «удалить всё»);
* `--dry-run` ничего не удаляет.

Скрипт запускается через bash; если bash недоступен, тесты пропускаются.
"""

import os
import shutil
import subprocess
import sys
import time

import pytest

BASH = shutil.which('bash')
pytestmark = pytest.mark.skipif(BASH is None, reason='bash недоступен')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(os.path.dirname(ROOT), 'scripts', 'backup-rotate.sh')


def _set_age(path, days):
    stamp = time.time() - days * 86400
    os.utime(path, (stamp, stamp))


def _dump(directory, name, age_days, payload=b'dump'):
    path = os.path.join(directory, name)
    with open(path, 'wb') as f:
        f.write(payload)
    _set_age(path, age_days)
    return path


def _run(directory, keep_days, *extra):
    return subprocess.run(
        [BASH, SCRIPT, str(directory), str(keep_days), *extra],
        capture_output=True,
        text=True,
    )


def test_old_dumps_are_removed_and_fresh_are_kept(tmp_path):
    old = _dump(tmp_path, 'dwar_rater_backup_20200101_000000.sql.gz', 40)
    fresh = _dump(tmp_path, 'dwar_rater_backup_20260101_000000.sql.gz', 1)

    result = _run(tmp_path, 30)
    assert result.returncode == 0, result.stderr

    assert not os.path.exists(old), 'старый дамп не удалён'
    assert os.path.exists(fresh), 'свежий дамп удалён — это потеря данных'


def test_foreign_files_are_never_touched(tmp_path):
    foreign = _dump(tmp_path, 'notes.txt', 400)
    other_dump = _dump(tmp_path, 'other_backup_20200101.sql.gz', 400)
    old = _dump(tmp_path, 'dwar_rater_backup_20200101_000000.sql.gz', 40)

    result = _run(tmp_path, 30)
    assert result.returncode == 0, result.stderr

    assert not os.path.exists(old)
    assert os.path.exists(foreign), 'удалён посторонний файл'
    assert os.path.exists(other_dump), 'удалён дамп с другим именем'


def test_subdirectories_are_not_descended_into(tmp_path):
    sub = tmp_path / 'archive'
    sub.mkdir()
    nested = _dump(str(sub), 'dwar_rater_backup_20200101_000000.sql.gz', 400)

    result = _run(tmp_path, 30)
    assert result.returncode == 0, result.stderr
    assert os.path.exists(nested), 'ротация залезла в подкаталог'


@pytest.mark.parametrize('keep_days', ['0', '', 'abc', '-5'])
def test_disabled_or_invalid_threshold_deletes_nothing(tmp_path, keep_days):
    old = _dump(tmp_path, 'dwar_rater_backup_20200101_000000.sql.gz', 400)

    result = _run(tmp_path, keep_days)
    assert result.returncode == 0, result.stderr
    assert os.path.exists(old), (
        f'порог {keep_days!r} не должен ничего удалять — иначе опечатка в .env '
        'снесёт все бэкапы'
    )


def test_dry_run_deletes_nothing(tmp_path):
    old = _dump(tmp_path, 'dwar_rater_backup_20200101_000000.sql.gz', 400)

    result = _run(tmp_path, 30, '--dry-run')
    assert result.returncode == 0, result.stderr
    assert os.path.exists(old), '--dry-run удалил файл'
    assert 'было бы удалено' in result.stdout


def test_missing_directory_is_an_error_not_a_silent_pass(tmp_path):
    result = _run(tmp_path / 'nope', 30)
    assert result.returncode != 0, 'отсутствующий каталог должен быть ошибкой'


# --- A13: интерфейс обязан говорить правду о политике хранения --------------

def _label(monkeypatch, value):
    from features.admin import routes as admin_routes
    if value is None:
        monkeypatch.delenv('BACKUP_KEEP_DAYS', raising=False)
    else:
        monkeypatch.setenv('BACKUP_KEEP_DAYS', value)
    return admin_routes._backup_retention_label()


def test_retention_label_reports_configured_days(monkeypatch):
    assert _label(monkeypatch, '30') == 'Automatic deletion after 30 days'


def test_retention_label_says_disabled_when_zero(monkeypatch):
    assert 'disabled' in _label(monkeypatch, '0').lower()


def test_retention_label_says_disabled_when_unset(monkeypatch):
    assert 'disabled' in _label(monkeypatch, None).lower()


def test_retention_label_handles_garbage(monkeypatch):
    """Опечатка в .env не должна ронять админку 500-й."""
    assert 'disabled' in _label(monkeypatch, 'тридцать').lower()


def test_list_backups_endpoint_reports_the_real_policy(app, client, admin_headers, monkeypatch):
    monkeypatch.setenv('BACKUP_KEEP_DAYS', '30')
    resp = client.get('/api/admin/backups', headers=admin_headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert 'No automatic deletion' not in body.get('retention', ''), (
        'админка по-прежнему обещает, что бэкапы не удаляются'
    )
    assert '30' in body.get('retention', '')
