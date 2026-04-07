import json
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from models import db
from models.improvement_track import ImprovementTrack
from models.leveling_scenario import LevelingScenario


tracks_bp = Blueprint('tracks', __name__)


def _generate_steps(character_data, scenario_data):
    steps = []
    target_stats = scenario_data.get('target_stats', {})
    main_stats = character_data.get('main_stats', {})
    combat_stats = character_data.get('combat_stats', {})
    magic_stats = character_data.get('magic_stats', {})
    current_all = {**main_stats, **combat_stats, **magic_stats}

    def _parse_num(val):
        try:
            return int(str(val).replace(' ', '').replace(',', ''))
        except (ValueError, TypeError):
            return 0

    for stat_name, target_val in target_stats.items():
        current_val = _parse_num(current_all.get(stat_name, 0))
        target_num = _parse_num(target_val)
        diff = target_num - current_val
        if diff <= 0:
            continue
        impact = diff * 1.0
        priority = 'high' if diff > target_num * 0.5 else ('medium' if diff > target_num * 0.2 else 'low')
        steps.append({
            'id': f'stat_{stat_name}',
            'type': 'stat',
            'title': f'Прокачать {stat_name}',
            'description': f'Увеличить {stat_name} с {current_val} до {target_num} (разница: {diff})',
            'priority': priority,
            'impact': impact,
            'current': current_val,
            'target': target_num,
            'completed': False,
        })

    for eq in scenario_data.get('recommended_equipment', []):
        steps.append({
            'id': f'eq_{eq["slot"]}',
            'type': 'equipment',
            'title': f'Экипировка: {eq["slot"]}',
            'description': f'Найти предмет для слота {eq["slot"]} (мин. качество: {eq["min_quality"]}, статы: {", ".join(eq["stats"])})',
            'priority': 'high',
            'impact': 100.0,
            'current': None,
            'target': eq,
            'completed': False,
        })

    for medal in scenario_data.get('priority_medals', []):
        steps.append({
            'id': f'medal_{medal}',
            'type': 'medal',
            'title': f'Получить медаль: {medal}',
            'description': f'Повысить репутацию и получить медаль "{medal}"',
            'priority': 'medium',
            'impact': 50.0,
            'current': None,
            'target': medal,
            'completed': False,
        })

    steps.sort(key=lambda s: (0 if s['priority'] == 'high' else 1 if s['priority'] == 'medium' else 2, -s['impact']))
    return steps


@tracks_bp.route('/api/tracks', methods=['GET'])
@require_auth
def list_tracks():
    user = g.current_user
    tracks = ImprovementTrack.query.filter_by(user_id=user.id).order_by(ImprovementTrack.updated_at.desc()).all()
    return jsonify([{
        'id': t.id,
        'character_nick': t.character_nick,
        'scenario_id': t.scenario_id,
        'total_progress': t.total_progress,
        'created_at': t.created_at.isoformat(),
        'updated_at': t.updated_at.isoformat(),
    } for t in tracks])


@tracks_bp.route('/api/tracks/generate', methods=['POST'])
@require_auth
def generate_track():
    user = g.current_user
    data = request.json
    character_data = data.get('character_data')
    scenario_id = data.get('scenario_id')

    if not character_data or not scenario_id:
        return jsonify({'error': 'character_data и scenario_id обязательны'}), 400

    scenario = LevelingScenario.query.get(scenario_id)
    if not scenario:
        return jsonify({'error': 'Сценарий не найден'}), 404

    scenario_data = json.loads(scenario.scenario_data)
    steps = _generate_steps(character_data, scenario_data)
    total_progress = 0.0

    track = ImprovementTrack(
        user_id=user.id,
        character_nick=character_data.get('name', ''),
        scenario_id=scenario_id,
        track_data=json.dumps(steps, ensure_ascii=False),
        total_progress=total_progress,
    )
    db.session.add(track)
    db.session.commit()

    return jsonify({
        'id': track.id,
        'steps': steps,
        'total_progress': total_progress,
    }), 201


@tracks_bp.route('/api/tracks/<int:track_id>', methods=['GET'])
@require_auth
def get_track(track_id):
    user = g.current_user
    track = ImprovementTrack.query.get_or_404(track_id)
    if track.user_id != user.id and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    steps = json.loads(track.track_data)
    return jsonify({
        'id': track.id,
        'character_nick': track.character_nick,
        'scenario_id': track.scenario_id,
        'steps': steps,
        'total_progress': track.total_progress,
        'updated_at': track.updated_at.isoformat(),
    })


@tracks_bp.route('/api/tracks/<int:track_id>/step/<step_id>', methods=['PUT'])
@require_auth
def update_step(track_id, step_id):
    user = g.current_user
    track = ImprovementTrack.query.get_or_404(track_id)
    if track.user_id != user.id and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403

    data = request.json
    steps = json.loads(track.track_data)
    for step in steps:
        if step['id'] == step_id:
            if 'completed' in data:
                step['completed'] = data['completed']
            break

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
@require_auth
def delete_track(track_id):
    user = g.current_user
    track = ImprovementTrack.query.get_or_404(track_id)
    if track.user_id != user.id and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    db.session.delete(track)
    db.session.commit()
    return jsonify({'status': 'deleted'})
