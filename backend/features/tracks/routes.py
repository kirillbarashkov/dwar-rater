import json
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from shared.rbac import require_permission, feature, Permission as PermDef
from shared.models import db
from shared.models.improvement_track import ImprovementTrack
from shared.models.leveling_scenario import LevelingScenario
from shared.models.compare_character import CompareCharacter
from shared.services.track_engine import (
    generate_steps, resync_progress, normalize_scenario,
)
from shared.services.analyze_service import analyze_character_url, AnalyzeError
from shared.config import Config


tracks_bp = Blueprint('tracks', __name__)

from shared.rbac import register_feature
register_feature('tracks', [
    PermDef('read', 'Просмотр треков', 'GET /api/tracks'),
    PermDef('write', 'Генерация/обновление треков', 'POST/PUT/DELETE /api/tracks/*'),
])


def _load_user_track(track_id):
    """Fetch a track owned by the current user (admin sees any). 404/403 aware."""
    user = g.current_user
    track = ImprovementTrack.query.get_or_404(track_id)
    if track.user_id != user.id and user.role != 'admin':
        return None, (jsonify({'error': 'Доступ запрещён'}), 403)
    return track, None


def _normalize_target(target_type, target_ref, user):
    """Resolve the target into a processed-character dict.

    Returns (target_dict, error_response). error_response is None on success.
    """
    if target_type == 'character':
        # Live URL: reuse the analyze pipeline (cache-first)
        try:
            return analyze_character_url(target_ref, user=user), None
        except AnalyzeError as e:
            return None, (jsonify({'error': str(e)}), e.status_code)
    if target_type == 'snapshot':
        try:
            snapshot_id = int(target_ref)
        except (TypeError, ValueError):
            return None, (jsonify({'error': 'target_ref должен быть ID снапшота'}), 400)
        snapshot = CompareCharacter.query.get(snapshot_id)
        if not snapshot:
            return None, (jsonify({'error': 'Снапшот не найден'}), 404)
        if snapshot.user_id != user.id and user.role != 'admin':
            return None, (jsonify({'error': 'Доступ запрещён к чужому снапшоту'}), 403)
        data = json.loads(snapshot.snapshot_data) if isinstance(snapshot.snapshot_data, str) \
            else snapshot.snapshot_data
        return data, None
    if target_type == 'scenario':
        try:
            scenario_id = int(target_ref)
        except (TypeError, ValueError):
            return None, (jsonify({'error': 'target_ref должен быть ID сценария'}), 400)
        scenario = LevelingScenario.query.get(scenario_id)
        if not scenario:
            return None, (jsonify({'error': 'Сценарий не найден'}), 404)
        scenario_data = json.loads(scenario.scenario_data)
        return normalize_scenario(scenario_data), None
    return None, (jsonify({'error': "target_type должен быть 'character' | 'snapshot' | 'scenario'"}), 400)


@tracks_bp.route('/api/tracks', methods=['GET'])
@require_permission('tracks', 'read')
def list_tracks():
    user = g.current_user
    tracks = ImprovementTrack.query.filter_by(user_id=user.id).order_by(ImprovementTrack.updated_at.desc()).all()
    return jsonify([{
        'id': t.id,
        'character_nick': t.character_nick,
        'scenario_id': t.scenario_id,
        'target_type': t.target_type,
        'target_ref': t.target_ref,
        'total_progress': t.total_progress,
        'power_gap': t.power_gap or 0.0,
        'created_at': t.created_at.isoformat() if t.created_at else None,
        'updated_at': t.updated_at.isoformat() if t.updated_at else None,
    } for t in tracks])


@tracks_bp.route('/api/tracks/generate', methods=['POST'])
@require_permission('tracks', 'write')
def generate_track():
    user = g.current_user
    data = request.json or {}

    # Back-compat: legacy {character_data, scenario_id} signature
    if 'character_data' in data and 'target_type' not in data:
        data = {
            'source': data.get('character_data'),
            'target_type': 'scenario',
            'target_ref': str(data.get('scenario_id') or ''),
        }

    source = data.get('source')
    target_type = data.get('target_type')
    target_ref = (data.get('target_ref') or '').strip() if data.get('target_ref') is not None else ''
    force_refresh = bool(data.get('force_refresh', False))

    if force_refresh:
        from shared.rbac import get_user_permission
        if get_user_permission(user, 'analyze', 'write') == 'none':
            return jsonify({'error': 'Недостаточно прав для force_refresh'}), 403
        char_url = user.character_url if hasattr(user, 'character_url') else None
        if not char_url:
            return jsonify({'error': 'Не задан URL вашего персонажа в профиле'}), 400
        try:
            source = analyze_character_url(char_url, force_refresh=True, user=user)
        except AnalyzeError as e:
            return jsonify({'error': str(e)}), e.status_code

    if not isinstance(source, dict) or not target_type or not target_ref:
        return jsonify({'error': 'source (object), target_type и target_ref обязательны'}), 400

    target, error = _normalize_target(target_type, target_ref, user)
    if error:
        return error

    steps, phases, power_gap = generate_steps(source, target, Config.POWER_WEIGHTS)
    completed = sum(1 for s in steps if s['completed'])
    total_progress = round(completed / len(steps) * 100, 1) if steps else 0.0

    track = ImprovementTrack(
        user_id=user.id,
        character_nick=source.get('name', ''),
        scenario_id=int(target_ref) if target_type == 'scenario' and str(target_ref).isdigit() else None,
        track_data=json.dumps(steps, ensure_ascii=False),
        phases_data=json.dumps(phases, ensure_ascii=False),
        total_progress=total_progress,
        target_type=target_type,
        target_ref=str(target_ref)[:512],
        source_snapshot=json.dumps(source, ensure_ascii=False),
        target_snapshot=json.dumps(target, ensure_ascii=False),
        power_gap=power_gap,
    )
    db.session.add(track)
    db.session.commit()

    return jsonify(track.to_dict()), 201


@tracks_bp.route('/api/tracks/<int:track_id>', methods=['GET'])
@require_permission('tracks', 'read')
def get_track(track_id):
    track, error = _load_user_track(track_id)
    if error:
        return error
    return jsonify(track.to_dict())


@tracks_bp.route('/api/tracks/<int:track_id>/re-evaluate', methods=['POST'])
@require_permission('tracks', 'write')
def re_evaluate_track(track_id):
    """Authoritative re-sync: fresh source vs the FROZEN target snapshot."""
    track, error = _load_user_track(track_id)
    if error:
        return error

    data = request.json or {}
    new_source = data.get('character_data') or data.get('source')
    force_refresh = bool(data.get('force_refresh', False))

    if force_refresh:
        from shared.rbac import get_user_permission
        if get_user_permission(g.current_user, 'analyze', 'write') == 'none':
            return jsonify({'error': 'Недостаточно прав для force_refresh'}), 403
        char_url = g.current_user.character_url if hasattr(g.current_user, 'character_url') else None
        if not char_url:
            return jsonify({'error': 'Не задан URL вашего персонажа в профиле'}), 400
        try:
            new_source = analyze_character_url(char_url, force_refresh=True, user=g.current_user)
        except AnalyzeError as e:
            return jsonify({'error': str(e)}), e.status_code
        # Same-character guard for the auto-parsed source
        incoming_nick = str(new_source.get('name', '')).strip()
        if incoming_nick and track.character_nick and incoming_nick != track.character_nick:
            return jsonify({'error': f"Трек создан для «{track.character_nick}», профиль указывает на «{incoming_nick}»"}), 409
    else:
        if not isinstance(new_source, dict):
            return jsonify({'error': 'character_data обязан быть объектом'}), 400

    # Facts-win applies only to the SAME character the track was created for;
    # a mismatched character must not auto-complete/uncomplete steps.
    incoming_nick = str(new_source.get('name', '')).strip()
    if incoming_nick and track.character_nick and incoming_nick != track.character_nick:
        return jsonify({'error': f"Трек создан для «{track.character_nick}», передан «{incoming_nick}»"}), 409

    if not track.target_snapshot:
        return jsonify({'error': 'Трек не содержит замороженного таргета (legacy) — пересоздайте трек'}), 409

    target = json.loads(track.target_snapshot)
    steps = json.loads(track.track_data)

    # Re-sync keeps target frozen: only source facts are re-read
    new_steps, phases, power_gap = resync_progress(steps, new_source)
    completed = sum(1 for s in new_steps if s['completed'])
    track.track_data = json.dumps(new_steps, ensure_ascii=False)
    track.phases_data = json.dumps(phases, ensure_ascii=False)
    track.source_snapshot = json.dumps(new_source, ensure_ascii=False)
    track.power_gap = power_gap
    track.total_progress = round(completed / len(new_steps) * 100, 1) if new_steps else 0.0
    track.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'id': track.id,
        'steps': new_steps,
        'phases': phases,
        'power_gap': power_gap,
        'total_progress': track.total_progress,
    })


@tracks_bp.route('/api/tracks/<int:track_id>/step/<step_id>', methods=['PUT'])
@require_permission('tracks', 'write')
def update_step(track_id, step_id):
    track, error = _load_user_track(track_id)
    if error:
        return error

    data = request.json or {}
    steps = json.loads(track.track_data)
    found = False
    for step in steps:
        if step['id'] == step_id:
            found = True
            if 'completed' in data:
                step['completed'] = bool(data['completed'])
                step['completed_auto'] = False  # manual override
            if 'current' in data and data['current'] is not None:
                # Partial progress: recalc delta/pct without auto-complete
                from shared.services.track_engine import parse_num
                current = parse_num(data['current'])
                target = parse_num(step.get('target', 0)) if not isinstance(step.get('target'), dict) else 0
                step['current'] = current
                if target:
                    step['delta'] = max(target - current, 0)
                    step['pct'] = round(current / target * 100, 1)
            break

    if not found:
        return jsonify({'error': 'Шаг не найден'}), 404

    completed_count = sum(1 for s in steps if s['completed'])
    track.total_progress = round(completed_count / len(steps) * 100, 1) if steps else 0
    track.track_data = json.dumps(steps, ensure_ascii=False)
    track.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'steps': steps,
        'total_progress': track.total_progress,
    })


@tracks_bp.route('/api/tracks/<int:track_id>', methods=['DELETE'])
@require_permission('tracks', 'write')
def delete_track(track_id):
    track, error = _load_user_track(track_id)
    if error:
        return error
    db.session.delete(track)
    db.session.commit()
    return jsonify({'status': 'deleted'})
