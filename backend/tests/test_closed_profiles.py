"""A3: слепок закрытого профиля обязан сохраняться в JSON.

Регрессия: features/closed_profiles/routes.py писал snapshot_data=str(dict) —
это Python-repr, а не JSON. Все читатели используют json.loads
(snapshots/routes.py, export/routes.py, tracks/routes.py), поэтому такой
слепок не читался: json.loads падал с JSONDecodeError.
"""
import json

import pytest

from shared.models import db
from shared.models.character_snapshot import CharacterSnapshot
from shared.models.closed_profile import ClosedProfile

NICK = 'a61probe'


@pytest.fixture(autouse=True)
def cleanup_probe_rows(app):
    """Убрать за собой.

    Общий TRUNCATE в conftest — молчаливый no-op (в списке есть несуществующая
    таблица equipment_item), поэтому БД между тестами не чистится. Тест,
    который что-то пишет, обязан убирать это сам: иначе
    test_snapshots_empty_list видит оставшиеся слепки.
    """
    yield
    with app.app_context():
        # Порядок важен: closed_profiles.snapshot_id ссылается на character_snapshot,
        # поэтому профиль сначала обрываем (FK → NULL), потом удаляем слепок.
        ClosedProfile.query.filter_by(nick=NICK).update({'snapshot_id': None})
        db.session.commit()
        CharacterSnapshot.query.filter_by(nick=NICK).delete()
        db.session.commit()


def _make_profile(app):
    """Создать профиль заново, устойчиво к остаткам прошлого прогона.

    closed_profiles.snapshot_id ссылается на character_snapshot, поэтому старый
    профиль сначала обрываем (FK → NULL), иначе удаление падает с
    ForeignKeyViolation.
    """
    with app.app_context():
        ClosedProfile.query.filter_by(nick=NICK).update({'snapshot_id': None})
        db.session.commit()
        ClosedProfile.query.filter_by(nick=NICK).delete()
        db.session.commit()
        db.session.add(ClosedProfile(nick=NICK, status='closed'))
        db.session.commit()


def test_saved_snapshot_is_valid_json(app, client, user_headers):
    """POST save-snapshot → в БД лежит валидный JSON, а не Python-repr."""
    _make_profile(app)

    payload = {
        'name': 'Гном',
        'race': ' dwarf',
        'rank': '100',
        'clan': 'Клан',
    }
    r = client.post(
        f'/api/closed-profiles/{NICK}/save-snapshot',
        json={'snapshot_data': payload, 'snapshot_name': 'probe'},
        headers=user_headers,
    )
    assert r.status_code == 200, r.get_json()
    snapshot_id = r.get_json()['snapshot_id']

    with app.app_context():
        snap = CharacterSnapshot.query.get(snapshot_id)
        raw = snap.snapshot_data
        # Это и есть суть дефекта: раньше здесь лежало "{'name': 'Гном', ...}"
        parsed = json.loads(raw)
        assert parsed['name'] == 'Гном'
        assert parsed['clan'] == 'Клан'


def test_snapshot_is_readable_by_the_api(app, client, admin_headers, user_headers):
    """Читательский эндпоинт не должен падать на битом слепке.

    GET /api/snapshots/<id> проверяет user_id: у слепка из closed_profiles его
    нет (nullable), поэтому читаем под админом.
    """
    _make_profile(app)

    payload = {'name': 'Гном', 'race': ' dwarf', 'rank': '100', 'clan': 'Клан'}
    r = client.post(
        f'/api/closed-profiles/{NICK}/save-snapshot',
        json={'snapshot_data': payload, 'snapshot_name': 'probe'},
        headers=user_headers,
    )
    assert r.status_code == 200, r.get_json()
    snapshot_id = r.get_json()['snapshot_id']

    r2 = client.get(f'/api/snapshots/{snapshot_id}', headers=admin_headers)
    assert r2.status_code == 200, r2.get_json()
    assert r2.get_json()['name'] == 'Гном'
