import json
from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from models import db
from models.leveling_scenario import LevelingScenario


scenarios_bp = Blueprint('scenarios', __name__)


@scenarios_bp.route('/api/scenarios', methods=['GET'])
@require_auth
def list_scenarios():
    user = g.current_user
    query = LevelingScenario.query.filter(
        (LevelingScenario.is_public == True) |
        (LevelingScenario.created_by == user.id)
    )
    query = query.order_by(LevelingScenario.created_at.desc())
    scenarios = query.all()

    return jsonify([{
        'id': s.id,
        'name': s.name,
        'description': s.description,
        'is_public': s.is_public,
        'created_by': s.created_by,
        'created_at': s.created_at.isoformat(),
    } for s in scenarios])


@scenarios_bp.route('/api/scenarios/<int:scenario_id>', methods=['GET'])
@require_auth
def get_scenario(scenario_id):
    scenario = LevelingScenario.query.get_or_404(scenario_id)
    data = json.loads(scenario.scenario_data)
    return jsonify({
        'id': scenario.id,
        'name': scenario.name,
        'description': scenario.description,
        'is_public': scenario.is_public,
        'created_by': scenario.created_by,
        'created_at': scenario.created_at.isoformat(),
        'data': data,
    })


@scenarios_bp.route('/api/scenarios', methods=['POST'])
@require_auth
def create_scenario():
    user = g.current_user
    if user.role != 'admin':
        return jsonify({'error': 'Только админ может создавать сценарии'}), 403

    data = request.json
    if not data.get('name') or not data.get('data'):
        return jsonify({'error': 'name и data обязательны'}), 400

    scenario = LevelingScenario(
        name=data['name'],
        description=data.get('description', ''),
        scenario_data=json.dumps(data['data'], ensure_ascii=False),
        created_by=user.id,
        is_public=data.get('is_public', False),
    )
    db.session.add(scenario)
    db.session.commit()

    return jsonify({
        'id': scenario.id,
        'name': scenario.name,
        'status': 'created',
    }), 201


@scenarios_bp.route('/api/scenarios/<int:scenario_id>', methods=['PUT'])
@require_auth
def update_scenario(scenario_id):
    user = g.current_user
    scenario = LevelingScenario.query.get_or_404(scenario_id)

    if user.role != 'admin' and scenario.created_by != user.id:
        return jsonify({'error': 'Доступ запрещён'}), 403

    data = request.json
    if 'name' in data:
        scenario.name = data['name']
    if 'description' in data:
        scenario.description = data['description']
    if 'data' in data:
        scenario.scenario_data = json.dumps(data['data'], ensure_ascii=False)
    if 'is_public' in data:
        scenario.is_public = data['is_public']

    db.session.commit()
    return jsonify({'status': 'updated'})


@scenarios_bp.route('/api/scenarios/<int:scenario_id>', methods=['DELETE'])
@require_auth
def delete_scenario(scenario_id):
    user = g.current_user
    scenario = LevelingScenario.query.get_or_404(scenario_id)

    if user.role != 'admin' and scenario.created_by != user.id:
        return jsonify({'error': 'Доступ запрещён'}), 403

    db.session.delete(scenario)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@scenarios_bp.route('/api/scenarios/<int:scenario_id>/compare', methods=['POST'])
@require_auth
def compare_scenario(scenario_id):
    scenario = LevelingScenario.query.get_or_404(scenario_id)
    scenario_data = json.loads(scenario.scenario_data)
    character_data = request.json

    if not character_data:
        return jsonify({'error': 'Нет данных персонажа'}), 400

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

    gaps = []
    for stat_name, target_val in target_stats.items():
        current_val = _parse_num(current_all.get(stat_name, 0))
        target_num = _parse_num(target_val)
        diff = target_num - current_val
        pct = round(current_val / target_num * 100, 1) if target_num > 0 else 100
        gaps.append({
            'stat': stat_name,
            'current': current_val,
            'target': target_num,
            'diff': diff,
            'progress_pct': min(pct, 100),
        })

    recommended = scenario_data.get('recommended_equipment', [])
    priority_medals = scenario_data.get('priority_medals', [])
    milestones = scenario_data.get('milestones', [])

    return jsonify({
        'scenario_name': scenario.name,
        'gaps': gaps,
        'recommended_equipment': recommended,
        'priority_medals': priority_medals,
        'milestones': milestones,
    })
