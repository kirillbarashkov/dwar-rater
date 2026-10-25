"""A39: бэкап из админки живёт в общем томе, а не в слое контейнера.

Было: `postgres_backups:/backups` смонтирован только в `postgres`, а бэкенд
писал в свой эфемерный `/backups` (`BACKUP_DIR` по умолчанию). Последствия:
бэкап из админки исчезал при `docker compose down` / пересоздании контейнера и
не был виден `make backup`; список в UI показывал не то, что лежит в томе.

Плюс две вещи, найденные при разборе и относящиеся к тому же механизму:

* `pg_dump` в премиграционной копии вызывался без `-h/-p`, то есть шёл в
  локальный сокет. В контейнере бэкенда Postgres'а нет — дамп падал с
  `connection to server on socket ... failed`, и премиграционных копий в проде
  не существовало вовсе (в логах это было видно как `Pre-migration backup FAILED`);
* файл назывался `pre_migration_<stamp>.sql.gz`, а `make restore`,
  `backup-rotate.sh` и `pre-destroy-check.sh` ищут `dwar_rater_backup_*.sql.gz` —
  копия не попадала ни в ротацию, ни в восстановление.

После A62 бэкенд работает под uid 10001, а postgres — под gid 70, поэтому одного
монтирования мало: нужна общая группа и setgid на каталоге, иначе файлы,
созданные одной стороной, другая не перезапишет и не удалит.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


def _service_block(compose_text, service):
    """Тело сервиса без остальных сервисов."""
    start = compose_text.index(f'  {service}:')
    rest = compose_text[start + 1:]
    end = rest.find('\n  ' + ' ' * 0)
    block = rest
    for trigger in ('\n  postgres:', '\n  backend:', '\n  frontend:', '\n  networks:', '\nvolumes:'):
        pos = block.find(trigger)
        if pos != -1:
            block = block[:pos]
    return block


def test_backend_mounts_the_shared_backup_volume():
    for rel in ('docker-compose.yml', 'docker-compose.prod.yml'):
        block = _service_block(_read(rel), 'backend')
        assert 'postgres_backups:/backups' in block, (
            f'{rel}: бэкенд снова пишет бэкапы в собственный слой контейнера'
        )


def test_postgres_and_backend_share_a_group():
    backend = _read('backend/Dockerfile')
    postgres = _read('Dockerfile.postgres')
    assert 'groupadd -o -g 70 dbbackups' in backend, 'общая группа с postgres не создана'
    assert 'usermod -aG dbbackups app' in backend, 'пользователь app не добавлен в группу'
    assert 'chown 10001:70 /backups' in backend, 'каталог не принадлежит общей группе'
    assert 'chmod 2775 /backups' in backend, 'нет setgid — файлы не унаследуют группу'
    assert 'chmod 2775 /backups' in postgres, 'postgres не даёт бэкенду писать в каталог'


def test_existing_volume_permissions_are_repaired_at_start():
    """Тома, созданные до правки, пришли с root:root 755."""
    postgres = _read('Dockerfile.postgres')
    cmd = postgres.split('CMD [')[1]
    assert 'chown postgres:postgres /backups' in cmd, 'права старого тома не чинятся'
    assert 'chmod 2775 /backups' in cmd


def test_cron_dumps_are_group_writable():
    script = _read('scripts/db-backup.sh')
    assert 'umask 002' in script, (
        'cron создаёт дампы 644 — бэкенд под uid 10001 не сможет их удалить'
    )


def test_pre_migration_backup_uses_the_restore_pattern():
    source = _read('backend/shared/services/pre_migration_backup.py')
    assert 'dwar_rater_backup_pre_migration_' in source, (
        'имя снова не попадает в шаблон dwar_rater_backup_*.sql.gz'
    )
    assert not re.search(r"f'pre_migration_", source), 'старое имя вернулось'


def test_pre_migration_dump_targets_the_real_server():
    source = _read('backend/shared/services/pre_migration_backup.py')
    assert "'-h', host" in source and "'-p', port" in source, (
        'pg_dump пойдёт в локальный сокет и упадёт в контейнере'
    )
    assert "os.environ.get('POSTGRES_HOST'" in source
    assert "os.environ.get('POSTGRES_PORT'" in source


def test_restore_and_rotation_look_for_the_same_pattern():
    for rel in ('scripts/backup-rotate.sh', 'scripts/pre-destroy-check.sh'):
        assert 'dwar_rater_backup_*.sql.gz' in _read(rel), f'{rel}: шаблон имени разошёлся'
