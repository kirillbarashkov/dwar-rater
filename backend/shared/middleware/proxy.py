"""A5: доверие заголовкам обратного прокси.

В проде бэкенд стоит за nginx в bridge-сети, поэтому без ProxyFix
`request.remote_addr` — это IP nginx-контейнера, а не клиента:

* rate-limit по IP становится общим на всех клиентов (один шумный выбирает
  лимит, остальные получают 429);
* `AuditLog.ip_address` теряет форензический смысл.

`frontend/nginx.conf` уже присылает `X-Forwarded-For`, `X-Forwarded-Proto` и
`Host`, а доверяем ровно одному прокси — самому nginx, поэтому счётчики = 1.
Если когда-нибудь перед nginx появится ещё один прокси (CDN, балансировщик),
число нужно увеличить, иначе клиентский IP будет вычислен неверно.
"""

from werkzeug.middleware.proxy_fix import ProxyFix


def install_proxy_fix(app):
    """Обернуть wsgi_app в ProxyFix.

    Вызывается и из `create_app()`, и из `create_test_app()`: если применить
    только в одной фабрике, тесты перестают проверять поведение прода.
    """
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    return app
