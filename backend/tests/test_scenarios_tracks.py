import json

import pytest

from shared.models import db
from shared.models.compare_character import CompareCharacter
from shared.models.leveling_scenario import LevelingScenario


SOURCE_CHAR = {
    'name': 'TestHero',
    'level': '10',
    'main_stats': {'Живучесть': '100', 'Защита': '50', 'Интуиция': '40', 'Ловкость': '30', 'Сила': '60'},
    'combat_stats': {'Инициатива': '20', 'Стойкость': '15'},
    'magic_stats': {'Воля': '10', 'Интеллект': '5', 'Концентрация': '8', 'Мудрость': '3', 'Подавление': '2'},
    'flashvars_extra': {'hpMax': '1000'},
    'equipment_by_kind': {},
    'medals': [],
}

TARGET_CHAR = {
    'name': 'TargetHero',
    'level': '12',
    'main_stats': {'Живучесть': '200', 'Защита': '100', 'Интуиция': '80', 'Ловкость': '60', 'Сила': '120'},
    'combat_stats': {'Инициатива': '40', 'Стойкость': '30'},
    'magic_stats': {},
    'flashvars_extra': {'hpMax': '2000'},
    'equipment_by_kind': {'Оружие': [{'title': 'Меч', 'quality': 'Синий', 'star_level': 3, 'level': 5}]},
    'medals': [{'num': 1, 'title': 'Заслон', 'quality': 'Синий', 'reputation': 'Гномы', 'description': ''}],
}

SCENARIO_DATA = {
    'target_stats': {'Живучесть': 300, 'Сила': 200},
    'recommended_equipment': [{'slot': 'Оружие', 'min_quality': 'Синий', 'stats': ['Сила']}],
    'priority_medals': ['Заслон'],
}


def _auth(token):
    return {'Authorization': f'Bearer {token}'}


def _make_scenario(app):
    with app.app_context():
        scenario = LevelingScenario(name='Gap Scenario', scenario_data=json.dumps(SCENARIO_DATA))
        db.session.add(scenario)
        db.session.commit()
        return scenario.id


def _make_snapshot(app, user_id, data=TARGET_CHAR, name='TargetHero'):
    with app.app_context():
        snap = CompareCharacter(user_id=user_id, character_name=name,
                                snapshot_data=json.dumps(data))
        db.session.add(snap)
        db.session.commit()
        return snap.id


# --- Legacy behavior kept intact -------------------------------------------

def test_scenarios_empty_list(client, admin_token):
    resp = client.get('/api/scenarios', headers={'Authorization': f'Bearer {admin_token}'})
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_scenarios_create_admin_only(client, user_token):
    resp = client.post('/api/scenarios', json={
        'name': 'Test', 'data': {'target_stats': {}}
    }, headers={'Authorization': f'Bearer {user_token}'})
    assert resp.status_code == 403


def test_scenarios_requires_auth(client):
    resp = client.get('/api/scenarios')
    assert resp.status_code == 401


def test_tracks_requires_auth(client):
    resp = client.get('/api/tracks')
    assert resp.status_code == 401


def test_tracks_generate_no_data(client, admin_token):
    resp = client.post('/api/tracks/generate', json={},
                       headers={'Authorization': f'Bearer {admin_token}'})
    assert resp.status_code == 400


# --- v2: generate per target_type ------------------------------------------

def test_generate_scenario_backcompat(client, app, admin_token):
    """Old {character_data, scenario_id} signature still works."""
    scenario_id = _make_scenario(app)
    resp = client.post('/api/tracks/generate', json={
        'character_data': SOURCE_CHAR,
        'scenario_id': scenario_id,
    }, headers=_auth(admin_token))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['target_type'] == 'scenario'
    assert body['steps'], 'scenario target must produce steps'
    assert body['target_summary']['name']


def test_generate_with_scenario_target(client, app, admin_token):
    scenario_id = _make_scenario(app)
    resp = client.post('/api/tracks/generate', json={
        'source': SOURCE_CHAR, 'target_type': 'scenario', 'target_ref': str(scenario_id),
    }, headers=_auth(admin_token))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['target_type'] == 'scenario'
    assert any(s['id'].startswith('stat:') for s in body['steps'])
    assert any(s['id'].startswith('medal:') for s in body['steps'])
    assert body['phases']


def test_generate_with_snapshot_target(client, app, admin_token, user_token):
    with app.app_context():
        from shared.models.user import User
        admin = User.query.filter_by(username='admin').first()
    snap_id = _make_snapshot(app, user_id=admin.id)
    resp = client.post('/api/tracks/generate', json={
        'source': SOURCE_CHAR, 'target_type': 'snapshot', 'target_ref': str(snap_id),
    }, headers=_auth(admin_token))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['target_type'] == 'snapshot'
    assert body['power_gap'] > 0


def test_generate_with_character_target(client, app, admin_token, monkeypatch):
    """Live URL target goes through analyze_service (mocked here)."""
    from shared.services import analyze_service
    monkeypatch.setattr(analyze_service, 'analyze_character_url',
                        lambda url, force_refresh=False, user=None: TARGET_CHAR)
    from features.tracks import routes as tracks_routes
    monkeypatch.setattr(tracks_routes, 'analyze_character_url',
                        analyze_service.analyze_character_url)
    resp = client.post('/api/tracks/generate', json={
        'source': SOURCE_CHAR, 'target_type': 'character',
        'target_ref': 'https://w1.dwar.ru/user_info.php?nick=TargetHero',
    }, headers=_auth(admin_token))
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['target_type'] == 'character'
    assert body['target_summary']['name'] == 'TargetHero'


def test_generate_snapshot_owner_403(client, app, admin_token, user_token):
    """A snapshot owned by admin must not be usable as target by a plain user."""
    with app.app_context():
        from shared.models.user import User
        admin = User.query.filter_by(username='admin').first()
    snap_id = _make_snapshot(app, user_id=admin.id)
    resp = client.post('/api/tracks/generate', json={
        'source': SOURCE_CHAR, 'target_type': 'snapshot', 'target_ref': str(snap_id),
    }, headers=_auth(user_token))
    assert resp.status_code == 403


def test_generate_bad_target_type(client, admin_token):
    resp = client.post('/api/tracks/generate', json={
        'source': SOURCE_CHAR, 'target_type': 'bogus', 'target_ref': 'x',
    }, headers=_auth(admin_token))
    assert resp.status_code == 400


def test_generate_force_refresh_requires_character_url(client, app, user_token):
    resp = client.post('/api/tracks/generate', json={
        'source': SOURCE_CHAR, 'target_type': 'scenario', 'target_ref': '1',
        'force_refresh': True,
    }, headers=_auth(user_token))
    assert resp.status_code == 400
    assert 'URL' in resp.get_json()['error'] or 'профиле' in resp.get_json()['error']


# --- v2: GET track + re-evaluate + step update ------------------------------

def _generate_track(client, app, token):
    scenario_id = _make_scenario(app)
    resp = client.post('/api/tracks/generate', json={
        'source': SOURCE_CHAR, 'target_type': 'scenario', 'target_ref': str(scenario_id),
    }, headers=_auth(token))
    assert resp.status_code == 201
    return resp.get_json()


def test_get_track_returns_v2_fields(client, app, admin_token):
    track = _generate_track(client, app, admin_token)
    resp = client.get(f"/api/tracks/{track['id']}", headers=_auth(admin_token))
    assert resp.status_code == 200
    body = resp.get_json()
    for field in ('phases', 'source_summary', 'target_summary', 'power_gap',
                  'target_type', 'target_ref', 'steps'):
        assert field in body


def test_re_evaluate_auto_completes(client, app, admin_token):
    track = _generate_track(client, app, admin_token)
    grown = dict(SOURCE_CHAR)
    grown['main_stats'] = {'Живучесть': '400', 'Защита': '250', 'Интуиция': '40',
                           'Ловкость': '30', 'Сила': '250'}
    resp = client.post(f"/api/tracks/{track['id']}/re-evaluate",
                       json={'character_data': grown}, headers=_auth(admin_token))
    assert resp.status_code == 200
    body = resp.get_json()
    by_id = {s['id']: s for s in body['steps']}
    assert by_id['stat:main:Живучесть']['completed'] is True
    assert by_id['stat:main:Живучесть']['completed_auto'] is True
    assert body['power_gap'] < track['power_gap']


def test_step_update_with_current(client, app, admin_token):
    track = _generate_track(client, app, admin_token)
    step_id = next(s['id'] for s in track['steps'] if s['id'].startswith('stat:'))
    resp = client.put(f"/api/tracks/{track['id']}/step/{step_id}",
                      json={'completed': True, 'current': 150},
                      headers=_auth(admin_token))
    assert resp.status_code == 200
    body = resp.get_json()
    step = next(s for s in body['steps'] if s['id'] == step_id)
    assert step['completed'] is True
    assert step['completed_auto'] is False
    assert step['current'] == 150


def test_re_evaluate_requires_write(client, app, user_token):
    """Plain users have tracks.write — verify endpoint auth is wired."""
    track = _generate_track(client, app, user_token)
    resp = client.post(f"/api/tracks/{track['id']}/re-evaluate",
                       json={'character_data': SOURCE_CHAR}, headers=_auth(user_token))
    assert resp.status_code == 200  # owner can re-evaluate own track


def test_re_evaluate_legacy_track_conflict(client, app, admin_token):
    """Track without target_snapshot (legacy) → 409 with clear message."""
    from shared.models.improvement_track import ImprovementTrack
    track = _generate_track(client, app, admin_token)
    with app.app_context():
        row = ImprovementTrack.query.get(track['id'])
        row.target_snapshot = None
        db.session.commit()
    resp = client.post(f"/api/tracks/{track['id']}/re-evaluate",
                       json={'character_data': SOURCE_CHAR}, headers=_auth(admin_token))
    assert resp.status_code == 409


def test_re_evaluate_rejects_wrong_character(client, app, admin_token):
    """Facts-win must not apply to a different character (review M3)."""
    track = _generate_track(client, app, admin_token)
    stranger = dict(SOURCE_CHAR)
    stranger['name'] = 'SomebodyElse'
    resp = client.post(f"/api/tracks/{track['id']}/re-evaluate",
                       json={'character_data': stranger}, headers=_auth(admin_token))
    assert resp.status_code == 409
    assert 'SomebodyElse' in resp.get_json()['error']


def test_generate_rejects_non_object_source(client, app, admin_token):
    """Review M2: source must be a dict (not string/list)."""
    scenario_id = _make_scenario(app)
    resp = client.post('/api/tracks/generate', json={
        'source': 'not-a-dict', 'target_type': 'scenario',
        'target_ref': str(scenario_id),
    }, headers=_auth(admin_token))
    assert resp.status_code == 400
