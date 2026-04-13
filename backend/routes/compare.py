import json
from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from models.compare_character import CompareCharacter
from models import db


compare_bp = Blueprint('compare', __name__)


@compare_bp.route('/api/compare', methods=['GET'])
@require_auth
def list_compare():
    user = g.current_user
    characters = CompareCharacter.query.filter_by(user_id=user.id).order_by(CompareCharacter.sort_order).all()
    return jsonify({
        'characters': [c.to_dict() for c in characters]
    })


@compare_bp.route('/api/compare', methods=['POST'])
@require_auth
def add_compare():
    user = g.current_user
    data = request.get_json()
    
    try:
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        if 'character_name' not in data:
            return jsonify({'error': 'Missing character_name'}), 400
        if 'snapshot_data' not in data:
            return jsonify({'error': 'Missing snapshot_data'}), 400
        
        max_order = db.session.query(db.func.max(CompareCharacter.sort_order)).filter_by(user_id=user.id).scalar() or 0
        
        snapshot_str = json.dumps(data['snapshot_data'])
        
        character = CompareCharacter(
            user_id=user.id,
            character_name=data['character_name'],
            snapshot_data=snapshot_str,
            sort_order=max_order + 1
        )
        db.session.add(character)
        db.session.commit()
        
        return jsonify({'status': 'ok', 'character_id': character.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@compare_bp.route('/api/compare/<int:char_id>', methods=['DELETE'])
@require_auth
def delete_compare(char_id):
    user = g.current_user
    character = CompareCharacter.query.filter_by(id=char_id, user_id=user.id).first()
    
    if not character:
        return jsonify({'error': 'Character not found'}), 404
    
    db.session.delete(character)
    db.session.commit()
    
    return jsonify({'status': 'ok'})