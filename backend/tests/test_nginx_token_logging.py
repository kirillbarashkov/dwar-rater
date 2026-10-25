"""A41: токен SSE не должен попадать в access-log nginx.

SSE-эндпоинты принимают токен query-параметром (`?token=…`), а стандартный
формат access-log пишет `$request_uri` — строку запроса целиком. То есть сырой
токен живой сессии оказывался в `/var/log/nginx/access.log` на VM.

Что проверяется:
* для `/api/` включён формат без аргументов, и этот формат использует `$uri`
  (путь), а не `$request_uri` (путь + параметры);
* в конфиге нет других `access_log`, возвращающих стандартный формат для API.

Отдельно зафиксировано (с проверкой), чего в находке **не** оказалось: деплой
печатает логи backend и postgres, но не nginx; gunicorn запускается без
`--access-logfile`, поэтому URL с токеном в логи Actions не попадал.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NGINX = os.path.join(ROOT, 'frontend', 'nginx.conf')
DEPLOY = os.path.join(ROOT, '.github', 'workflows', 'deploy.yml')
ENTRYPOINT = os.path.join(ROOT, 'backend', 'entrypoint.sh')


def _nginx_config():
    return open(NGINX, encoding='utf-8').read()


def _api_block(config):
    start = config.index('location /api/ {')
    return config[start:config.index('}', start)]


def test_api_block_uses_an_argument_free_log_format():
    block = _api_block(_nginx_config())
    assert 'access_log' in block, 'для /api/ не задан формат лога — действует `main` с $request_uri'
    assert 'no_args' in block, 'для /api/ не используется безопасный формат'


def test_the_safe_format_logs_path_without_query():
    config = _nginx_config()
    match = re.search(r'log_format\s+no_args\s+(.+?);', config, re.S)
    assert match, 'формат no_args не объявлен'
    body = match.group(1)

    assert '$uri' in body, 'в формате нет $uri — нечего логировать вместо параметров'
    assert '$request_uri' not in body, '$request_uri снова логирует query-строку с токеном'
    assert '$args' not in body and '$query_string' not in body, 'в формате остались аргументы'


def test_no_other_access_log_in_the_api_location():
    block = _api_block(_nginx_config())
    lines = [l.strip() for l in block.split('\n') if l.strip().startswith('access_log')]
    assert len(lines) == 1, f'для /api/ несколько access_log: {lines}'


def test_gunicorn_does_not_log_requests():
    """Иначе токен уходил бы в логи backend, а те печатаются при падении деплоя."""
    entrypoint = open(ENTRYPOINT, encoding='utf-8').read()
    gunicorn = [l for l in entrypoint.split('\n') if 'gunicorn' in l and 'exec' in l]
    assert gunicorn, 'не найдена команда запуска gunicorn'
    assert '--access-logfile' not in gunicorn[0], (
        'gunicorn включил access-log: URL с токеном попадёт в логи backend'
    )


def test_deploy_prints_backend_logs_not_nginx():
    """Логи backend/postgres печатаются при падении — это допустимо, пока в них нет URL.

    nginx access-log в диагностику НЕ попадает: проверяем, что его там нет.
    """
    text = open(DEPLOY, encoding='utf-8').read()
    assert 'logs --tail' in text, 'диагностика логов пропала из деплоя'
    assert 'access.log' not in text, 'деплой печатает access.log — сырые токены уйдут в Actions'
