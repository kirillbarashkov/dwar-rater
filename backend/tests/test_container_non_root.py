"""A62: контейнеры работают под непривилегированным пользователем.

До правки `USER` не был задан ни в одном Dockerfile: nginx-master, gunicorn и —
что важнее — `pg_dump`/`pg_restore`/`psql`, которые бэкенд запускает через
`subprocess`, работали под root. Компрометация любого из них давала root внутри
контейнера, а с монтированными томами — доступ к данным и бэкапам.

Что сделано:

* `backend/Dockerfile` — пользователь `app` (uid 10001), `chown` на `/app` и
  `/backups`, `USER app`;
* `frontend/Dockerfile.prod` — `USER nginx` (uid 101) и свой основной конфиг
  `nginx.main.conf`: pid и временные каталоги в `/tmp`, потому что штатный
  `/etc/nginx/nginx.conf` рассчитан на master под root; сервер слушает 8080,
  наружу по-прежнему публикуется 80 (`"80:8080"`);
* `frontend/Dockerfile` (dev) — `USER node`;
* оба compose — `security_opt: [no-new-privileges:true]` для backend и frontend.

`postgres` намеренно оставлен без `USER`: официальный образ сам сбрасывает права
на `postgres` при старте, а `no-new-privileges` сломал бы `gosu`. Это записано в
документе, а не забыто.

Побочная находка, найденная при проверке под non-root: в образе `BASE_DIR = '/'`,
поэтому каталог состояния вычислялся как `/backend/instance`. Под root он молча
создавался; под uid 10001 это `PermissionError` на старте. Добавлен фолбэк на
каталог приложения — тот же приём, что уже был для `alembic.ini`.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


def _compose(rel):
    return _read(rel)


def test_backend_dockerfile_switches_user():
    text = _read('backend/Dockerfile')
    assert re.search(r'^USER app\s*$', text, re.M), 'бэкенд снова стартует под root'
    assert 'chown -R app:app /app' in text, 'каталог приложения не отдан пользователю'
    assert 'useradd -u 10001' in text, 'uid не зафиксирован — права на томах поплывут'
    assert '/backups' in text, 'каталог бэкапов не создан/не отдан пользователю'


def test_prod_frontend_runs_unprivileged():
    text = _read('frontend/Dockerfile.prod')
    assert re.search(r'^USER nginx\s*$', text, re.M), 'nginx в проде снова под root'
    assert 'nginx.main.conf' in text, 'основной конфиг не подменён — nginx не стартует без root'
    assert 'EXPOSE 8080' in text


def test_prod_frontend_listens_on_unprivileged_port():
    server = _read('frontend/nginx.conf')
    assert 'listen 8080;' in server, 'порт < 1024 под непривилегированным nginx недоступен'
    assert 'listen 80;' not in server
    main_conf = _read('frontend/nginx.main.conf')
    assert 'pid /tmp/nginx.pid;' in main_conf, 'pid-файл попадёт в /run — нет прав'
    for path in ('/tmp/client_body', '/tmp/proxy'):
        assert path in main_conf, f'временный каталог {path} не перенастроен'


def test_prod_compose_publishes_port_80_to_8080():
    text = _compose('docker-compose.prod.yml')
    assert '"80:8080"' in text, 'внешний порт прода изменился или перестал вести на 8080'


def test_dev_frontend_runs_as_node_user():
    text = _read('frontend/Dockerfile')
    assert re.search(r'^USER node\s*$', text, re.M)
    assert 'chown -R node:node /app' in text


def test_no_new_privileges_everywhere_it_applies():
    for rel in ('docker-compose.yml', 'docker-compose.prod.yml'):
        text = _compose(rel)
        assert text.count('no-new-privileges:true') == 2, (
            f'{rel}: ожидались backend и frontend; postgres — намеренное исключение'
        )


def test_postgres_is_deliberately_left_as_is():
    """Официальный образ сам сбрасывает права; ломать его `USER` нельзя."""
    text = _read('Dockerfile.postgres')
    assert 'USER ' not in text, 'postgres-образу задан USER — он перестанет стартовать'


def test_instance_dir_has_a_fallback_for_the_image_layout():
    """Под non-root `/backend/instance` не создаётся — нужен фолбэк."""
    app = _read('backend/app.py')
    block = app.split("instance_dir = os.path.join(BASE_DIR, 'backend', 'instance')")[1][:900]
    assert 'if not os.path.isdir(os.path.dirname(instance_dir))' in block, (
        'фолбэк убран — под uid 10001 приложение упадёт на старте (PermissionError)'
    )
    assert "os.path.dirname(os.path.abspath(__file__)), 'instance'" in block
