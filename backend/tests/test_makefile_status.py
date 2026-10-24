"""A25: `make status` не должен врать про БД и бэкапы.

Аудит утверждал, что запрос «невалиден», потому что `pg_stat_file` нельзя
положить в `FROM`. Проверка на живой БД это **опровергла**: запрос выполняется.
Настоящий дефект другой и хуже — метрика `Backups` считалась как
`COUNT(*) FROM (SELECT 1 FROM pg_stat_file('/backups') LIMIT 0)`, то есть
`LIMIT 0` гарантирует ноль строк **всегда**. На dev-volume лежало 2047 файлов,
а цель печатала `Backups | 0`.

Плюс два побочных: жёстко зашитые `-U dwar -d dwar_rater` и `2>/dev/null`,
который превращал любую настоящую ошибку в бодрое «DB not accessible».

Тесты статические: читают Makefile как текст (запускать `make` в CI нечем).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAKEFILE = os.path.join(ROOT, 'Makefile')


def _status_block():
    text = open(MAKEFILE, encoding='utf-8').read()
    start = text.index('status:')
    end = text.index('\n\n', start)
    return text[start:end]


def test_no_always_zero_backup_metric():
    """`LIMIT 0` в подзапросе — метрика, которая всегда 0."""
    block = _status_block()
    assert 'LIMIT 0' not in block, 'метрика бэкапов снова считается через LIMIT 0'
    assert 'pg_stat_file' not in block, 'pg_stat_file не перечисляет файлы — нужен pg_ls_dir'


def test_backups_are_counted_from_the_directory():
    block = _status_block()
    assert "pg_ls_dir('/backups')" in block, 'бэкапы не читаются из каталога'
    assert "LIKE '%.sql.gz'" in block, 'считаются все файлы, а не только дампы'


def test_credentials_come_from_env_not_hardcoded():
    text = open(MAKEFILE, encoding='utf-8').read()
    # комментарии не считаем: в них по делу упомянут старый хардкод
    code = '\n'.join(l for l in text.split('\n') if not l.lstrip().startswith('#'))
    assert '$(PG_USER)' in code and '$(PG_DB)' in code, 'учётные данные всё ещё зашиты'
    assert '-U dwar -d dwar_rater' not in code, 'остался хардкод пользователя/БД'
    assert "s/^POSTGRES_USER=//p" in code, 'значения не берутся из .env'


def test_errors_are_not_swallowed():
    block = _status_block()
    psql_lines = [l for l in block.split('\n') if 'psql' in l]
    assert psql_lines, 'в цели нет вызова psql'
    assert '2>/dev/null' not in psql_lines[0], 'ошибка psql снова глушится'
    assert 'DB not accessible' not in block or '2>/dev/null' not in block, (
        'сообщение «DB not accessible» перекрывает настоящую ошибку'
    )


def test_status_target_uses_compose_service():
    """Имя контейнера может отличаться между окружениями — берём сервис."""
    block = _status_block()
    assert 'docker compose exec -T postgres' in block, 'вызов привязан к имени контейнера'


def test_makefile_still_defines_required_targets():
    text = open(MAKEFILE, encoding='utf-8').read()
    for target in ('start:', 'stop:', 'backup:', 'migrate:', 'status:', 'restore:'):
        assert re.search(rf'(?m)^{re.escape(target)}', text), f'пропала цель {target}'
