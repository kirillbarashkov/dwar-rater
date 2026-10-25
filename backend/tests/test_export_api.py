"""A28: у фичи `export` не было ни одного теста.

`features/export/routes.py` — единственный маршрут, который отдаёт файл
пользователю, и до сих пор его не покрывал ни один тест. Здесь проверяется
именно то, что легко сломать незаметно: валидация входа, права на чужой слепок,
имя файла и content-type.

Отдельно зафиксировано расхождение, найденное при написании тестов: фича
объявляет права `export:*`, а гейт стоит на `analyze:read` (см. A64 в реестре).
Тест намеренно проверяет текущее поведение `analyze:read` — чтобы правка на
`export:read` была осознанной и не проскочила молча.
"""

import io
import json
import os
import secrets
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.user import User
from shared.models.character_snapshot import CharacterSnapshot
from shared.rbac.models import SessionToken


def _login(app, username, role='user'):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, password_hash='x', role=role, is_active=True)
            db.session.add(user)
            db.session.commit()
        token = secrets.token_hex(32)
        db.session.add(SessionToken(
            user_id=user.id,
            token_hash=SessionToken.hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.session.commit()
        return token, user.id


def _headers(token):
    return {'Authorization': f'Bearer {token}'}


def _analysis(name='Гимли'):
    return {
        'name': name,
        'race': 'Гном',
        'rank': 'Воин',
        'level': 20,
        'clan': 'Тестовый',
    }


def _payload(**overrides):
    body = {'format': 'markdown', 'sections': ['identity'], 'data': _analysis()}
    body.update(overrides)
    return body


def test_export_requires_auth(client):
    response = client.post('/api/export/character', json=_payload())
    assert response.status_code in (401, 403), response.status_code


def test_empty_body_is_refused(app, client):
    token, _ = _login(app, 'a28_exporter')
    response = client.post('/api/export/character', json={}, headers=_headers(token))
    assert response.status_code == 400
    assert 'обязательно' in response.get_json()['error']


def test_unknown_format_is_refused(app, client):
    token, _ = _login(app, 'a28_exporter')
    response = client.post('/api/export/character', json=_payload(format='docx'),
                           headers=_headers(token))
    assert response.status_code == 400
    assert 'docx' not in response.get_json()['error']
    assert 'html' in response.get_json()['error']


def test_empty_sections_are_refused(app, client):
    token, _ = _login(app, 'a28_exporter')
    response = client.post('/api/export/character', json=_payload(sections=[]),
                           headers=_headers(token))
    assert response.status_code == 400


def test_unknown_section_is_named_in_the_error(app, client):
    token, _ = _login(app, 'a28_exporter')
    response = client.post('/api/export/character',
                           json=_payload(sections=['identity', 'galactic']),
                           headers=_headers(token))
    assert response.status_code == 400
    assert 'galactic' in response.get_json()['error']


def test_markdown_export_returns_a_file_with_transliterated_name(app, client):
    token, _ = _login(app, 'a28_exporter')
    response = client.post('/api/export/character', json=_payload(),
                           headers=_headers(token))

    assert response.status_code == 200, response.get_data(as_text=True)[:200]
    assert 'text/markdown' in response.headers['Content-Type']
    disposition = response.headers['Content-Disposition']
    assert 'attachment' in disposition
    assert 'Gimli' in disposition or 'gimli' in disposition.lower(), disposition
    assert 'Гимли' not in disposition, 'кириллица осталась в имени файла'
    assert response.get_data(as_text=True).strip(), 'файл пустой'


def test_html_export_has_html_content_type(app, client):
    token, _ = _login(app, 'a28_exporter')
    response = client.post('/api/export/character', json=_payload(format='html'),
                           headers=_headers(token))

    assert response.status_code == 200
    assert 'text/html' in response.headers['Content-Type']
    assert '<h1' in response.get_data(as_text=True)


def test_snapshot_of_another_user_is_forbidden(app, client):
    owner_token, owner_id = _login(app, 'a28_owner')
    other_token, _ = _login(app, 'a28_other')

    with app.app_context():
        snapshot = CharacterSnapshot(
            user_id=owner_id,
            nick='Гимли',
            name='Гимли',
            snapshot_data=json.dumps(_analysis(), ensure_ascii=False),
        )
        db.session.add(snapshot)
        db.session.commit()
        snapshot_id = snapshot.id

    try:
        response = client.post('/api/export/character',
                               json={'format': 'markdown', 'sections': ['identity'],
                                     'snapshot_id': snapshot_id},
                               headers=_headers(other_token))
        assert response.status_code == 403
    finally:
        # A28: слепки живут в общей тестовой БД (чистки между тестами нет),
        # поэтому за собой убираем — иначе падает test_snapshots_empty_list.
        with app.app_context():
            CharacterSnapshot.query.filter_by(id=snapshot_id).delete()
            db.session.commit()


def test_missing_snapshot_is_404(app, client):
    token, _ = _login(app, 'a28_exporter')
    response = client.post('/api/export/character',
                           json={'format': 'markdown', 'sections': ['identity'],
                                 'snapshot_id': 999999999},
                           headers=_headers(token))
    assert response.status_code == 404
