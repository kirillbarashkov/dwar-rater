"""Тесты вкладки «О проекте».

Документы вкладки — markdown-файлы в `backend/docs/about/`, они едут в образ
вместе с кодом. Поэтому проверяем не только контракт (права, ключи, порядок), но
и НАЛИЧИЕ текста: пустой markdown означает, что файл не попал в сборку или в
чекаут, и вкладка молча покажет пустоту — это должно падать здесь, а не в проде.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EXPECTED_KEYS = ['description', 'whatsnew', 'releases', 'techdebt']


def test_about_requires_auth(client):
    """Без токена вкладка закрыта: это часть приложения, а не публичная страница."""
    assert client.get('/api/about').status_code == 401


def test_about_returns_all_sections(client, admin_headers):
    response = client.get('/api/about', headers=admin_headers)
    assert response.status_code == 200

    documents = response.get_json()['documents']
    assert [doc['key'] for doc in documents] == EXPECTED_KEYS

    for doc in documents:
        assert doc['title'], f"{doc['key']}: пустой заголовок вкладки"
        assert doc['markdown'].strip(), f"{doc['file']} пуст или не попал в сборку"
        assert doc['updated'], f"{doc['file']}: не отдано время правки"


def test_about_regular_user_can_read(client, user_headers):
    """Вкладка — рассказ о проекте, а не рабочий инструмент: читает любая роль."""
    assert client.get('/api/about', headers=user_headers).status_code == 200


def test_about_release_block_matches_version(client, admin_headers):
    """Рядом с архивом отдаём текущий релиз — то, что реально записано в git."""
    release = client.get('/api/about', headers=admin_headers).get_json()['release']
    assert set(release) == {'version', 'git_hash', 'build_date', 'branch', 'notes'}
    assert release['version']
