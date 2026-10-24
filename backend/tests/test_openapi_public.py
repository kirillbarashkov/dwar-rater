"""A23: спецификация OpenAPI публична — это решение, а не забывчивость.

Аудит нашёл, что `/api/openapi.yaml` отдаётся без авторизации, и предложил либо
задокументировать это, либо закрыть. Оставлено публичным: на спецификации
держится открытый `/apidocs` — Swagger UI запрашивает её из браузера без токена.
Секретов в файле нет, только описания маршрутов.

Тесты-замки здесь нужны, чтобы решение нельзя было отменить молча: если кто-то
закроет эндпоинт, отвалится Swagger UI; если изменится решение, придётся
обновить README — и это будет видно в дифе.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_spec_is_served_without_auth(client):
    response = client.get('/api/openapi.yaml')

    assert response.status_code == 200, 'спецификация закрылась — Swagger UI перестанет работать'
    assert 'yaml' in response.headers.get('Content-Type', ''), response.headers.get('Content-Type')


def test_spec_has_no_secrets(client):
    """Публичность допустима только пока в спеке нет настоящих секретов.

    Ищем конкретные литералы (дефолтные секреты из репозитория и строки
    подключения), а не слово «password»: пароль как поле контракта — это
    нормальная часть спецификации, а `/api/auth/change-password` содержит его
    прямо в пути.
    """
    body = client.get('/api/openapi.yaml').get_data(as_text=True)
    lowered = body.lower()

    # Только однозначные артефакты: конкретные дефолтные пароли/ключи и строки
    # подключения. Слова вроде «secret»/«password» встречаются в именах полей
    # схемы (`totp_secret`) и в путях (`/change-password`) — это не утечка.
    for literal in (
        'change-me-in-production',
        'dev-secret-key-change-me',
        'pre-start-key',
        'postgres://',
        'postgresql://',
        'bearer eyj',
    ):
        assert literal not in lowered, f'в публичной спеке найдено {literal!r}'


def test_swagger_ui_is_public(client):
    """Смысл публичной спеки — открытый /apidocs."""
    assert client.get('/apidocs').status_code == 200


def test_readme_documents_that_the_spec_is_public():
    readme = open(os.path.join(ROOT, 'README.md'), encoding='utf-8').read()

    assert 'openapi.yaml' in readme, 'README не упоминает публичную спецификацию'
    assert 'публичн' in readme.lower() or 'без авторизации' in readme.lower(), (
        'README не говорит, что спецификация публичная'
    )
