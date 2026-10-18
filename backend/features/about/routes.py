"""Вкладка «О проекте» — документы о проекте одним эндпоинтом.

Контент лежит markdown-файлами в `backend/docs/about/`. Так решено намеренно:
правка текста — это обычный коммит (попадает в релиз вместе с кодом), новые
зависимости не нужны, а рендер разметки живёт на фронте. Файлов может не быть —
тогда таб честно скажет, что документ ещё не написан, а не отдаст 500.

Отдельно отдаём текущий релиз (`/api/version` знает его же, но вкладке нужен
рядом с архивом: сверху — то, что реально записано в git, ниже — подробный
разбор релизов, который в git не попадает).
"""

import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from shared.rbac import Permission as PermDef, register_feature, require_permission
from shared.utils.version import get_version_info, read_release_notes

about_bp = Blueprint('about', __name__)

register_feature('about', [
    PermDef('read', 'О проекте', 'GET /api/about — описание, что нового, релизы, техдолг'),
])

# Ключ раздела = ключ вкладки на фронте, файл — имя в docs/about/. Порядок здесь
# и есть порядок табов: фронт их не сортирует, а рисует как пришли.
SECTIONS = (
    ('description', 'Описание и цели проекта', 'description.md'),
    ('whatsnew', 'Что нового', 'whatsnew.md'),
    ('releases', 'Релиз', 'releases.md'),
    ('techdebt', 'Техдолг', 'techdebt.md'),
)

DOCS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'docs', 'about')
)


def _read_section(filename):
    """Markdown раздела и время правки файла. Нет файла — пустой текст, не ошибка."""
    path = os.path.join(DOCS_DIR, filename)
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            markdown = handle.read().strip()
    except (FileNotFoundError, OSError):
        return '', None

    updated = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    return markdown, updated.isoformat()


@about_bp.route('/api/about', methods=['GET'])
@require_permission('about', 'read')
def about_documents():
    """Документы вкладки «О проекте» + текущий релиз из git."""
    info = get_version_info()

    documents = []
    for key, title, filename in SECTIONS:
        markdown, updated = _read_section(filename)
        documents.append({
            'key': key,
            'title': title,
            'file': filename,
            'updated': updated,
            'markdown': markdown,
        })

    return jsonify({
        'documents': documents,
        'release': {
            'version': info['version'],
            'git_hash': info['git_hash'],
            'build_date': info['build_date'],
            'branch': info['branch'],
            'notes': read_release_notes(),
        },
    })
