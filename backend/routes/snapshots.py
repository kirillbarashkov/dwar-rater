import json
from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from models.character_snapshot import CharacterSnapshot
from models import db
from services.cache_service import create_named_snapshot, log_analysis


snapshots_bp = Blueprint('snapshots', __name__)


@snapshots_bp.route('/api/snapshots', methods=['GET'])
@require_auth
def list_snapshots():
    nick = request.args.get('nick', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    user = g.current_user

    query = CharacterSnapshot.query
    if user.role != 'admin':
        query = query.filter_by(user_id=user.id)
    if nick:
        query = query.filter(CharacterSnapshot.nick.ilike(f'%{nick}%'))

    query = query.order_by(CharacterSnapshot.analyzed_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
'snapshots': [{
            'id': s.id,
            'nick': s.nick,
            'name': s.name,
            'race': s.race,
            'rank': s.rank,
            'clan': s.clan,
            'snapshot_name': s.snapshot_name,
            'analyzed_at': s.analyzed_at.isoformat(),
        } for s in pagination.items]
    })


@snapshots_bp.route('/api/snapshots/<int:snapshot_id>', methods=['GET'])
@require_auth
def get_snapshot(snapshot_id):
    user = g.current_user
    snapshot = CharacterSnapshot.query.get_or_404(snapshot_id)
    if user.role != 'admin' and snapshot.user_id != user.id:
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = json.loads(snapshot.snapshot_data)
    data['snapshot_id'] = snapshot.id
    data['snapshot_name'] = snapshot.snapshot_name
    data['analyzed_at'] = snapshot.analyzed_at.isoformat()
    return jsonify(data)


@snapshots_bp.route('/api/snapshots/<int:snapshot_id>', methods=['DELETE'])
@require_auth
def delete_snapshot(snapshot_id):
    user = g.current_user
    snapshot = CharacterSnapshot.query.get_or_404(snapshot_id)
    if user.role != 'admin' and snapshot.user_id != user.id:
        return jsonify({'error': 'Доступ запрещён'}), 403
    db.session.delete(snapshot)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@snapshots_bp.route('/api/save-snapshot', methods=['POST'])
@require_auth
def save_snapshot_endpoint():
    data = request.json
    snapshot_data = data.get('snapshot_data')
    snapshot_name = data.get('snapshot_name', '')
    url = data.get('url', '')
    user = g.current_user

    if not snapshot_data:
        return jsonify({'error': 'Нет данных для сохранения'}), 400

    snapshot_id = create_named_snapshot(snapshot_data, snapshot_name, user.id, url)
    log_analysis(user.id, snapshot_data.get('name', ''), url, snapshot_id=snapshot_id)

    snapshot = CharacterSnapshot.query.get(snapshot_id)
    return jsonify({
        'status': 'saved',
        'snapshot_id': snapshot_id,
        'analyzed_at': snapshot.analyzed_at.isoformat() if snapshot else '',
    })
