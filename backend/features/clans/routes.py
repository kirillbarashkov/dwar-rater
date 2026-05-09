import json
from flask import Blueprint, request, jsonify, g
from shared.middleware.auth import require_auth
from shared.models import db
from shared.models.clan import Clan, ClanMember, ClanChatRoom, ClanChatMessage


clans_bp = Blueprint('clans', __name__)


def _is_clan_admin(user, clan_id):
    member = ClanMember.query.filter_by(clan_id=clan_id, user_id=user.id).first()
    return member and member.role in ('leader', 'officer')


def _is_clan_member(user, clan_id):
    return ClanMember.query.filter_by(clan_id=clan_id, user_id=user.id).first() is not None


@clans_bp.route('/api/clans', methods=['GET'])
@require_auth
def list_clans():
    user = g.current_user
    if user.role == 'admin':
        clans = Clan.query.all()
    else:
        memberships = ClanMember.query.filter_by(user_id=user.id).all()
        clan_ids = [m.clan_id for m in memberships]
        clans = Clan.query.filter(Clan.id.in_(clan_ids)).all() if clan_ids else []
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'created_at': c.created_at.isoformat(),
    } for c in clans])


@clans_bp.route('/api/clans', methods=['POST'])
@require_auth
def create_clan():
    user = g.current_user
    if user.role != 'admin':
        return jsonify({'error': 'Только админ может создавать кланы'}), 403
    data = request.json
    if not data.get('name'):
        return jsonify({'error': 'name обязателен'}), 400
    clan = Clan(name=data['name'], created_by=user.id)
    db.session.add(clan)
    db.session.flush()
    member = ClanMember(clan_id=clan.id, user_id=user.id, role='leader')
    db.session.add(member)
    db.session.commit()
    return jsonify({'id': clan.id, 'name': clan.name}), 201


@clans_bp.route('/api/clans/<int:clan_id>/members', methods=['GET'])
@require_auth
def list_members(clan_id):
    user = g.current_user
    if not _is_clan_member(user, clan_id) and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    members = ClanMember.query.filter_by(clan_id=clan_id).all()
    return jsonify([{
        'user_id': m.user_id,
        'username': m.user.username,
        'role': m.role,
        'joined_at': m.joined_at.isoformat(),
    } for m in members])


@clans_bp.route('/api/clans/<int:clan_id>/members', methods=['POST'])
@require_auth
def add_member(clan_id):
    user = g.current_user
    if not _is_clan_admin(user, clan_id) and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = request.json
    target_user_id = data.get('user_id')
    if not target_user_id:
        return jsonify({'error': 'user_id обязателен'}), 400
    existing = ClanMember.query.filter_by(clan_id=clan_id, user_id=target_user_id).first()
    if existing:
        return jsonify({'error': 'Уже участник'}), 400
    member = ClanMember(clan_id=clan_id, user_id=target_user_id, role=data.get('role', 'member'))
    db.session.add(member)
    db.session.commit()
    return jsonify({'status': 'added'})


@clans_bp.route('/api/clans/<int:clan_id>/members/<int:user_id>', methods=['DELETE'])
@require_auth
def remove_member(clan_id, user_id):
    user = g.current_user
    if not _is_clan_admin(user, clan_id) and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    member = ClanMember.query.filter_by(clan_id=clan_id, user_id=user_id).first()
    if not member:
        return jsonify({'error': 'Не найден'}), 404
    db.session.delete(member)
    db.session.commit()
    return jsonify({'status': 'removed'})


@clans_bp.route('/api/clans/<int:clan_id>/rooms', methods=['GET'])
@require_auth
def list_rooms(clan_id):
    user = g.current_user
    if not _is_clan_member(user, clan_id) and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    rooms = ClanChatRoom.query.filter_by(clan_id=clan_id).all()
    return jsonify([{
        'id': r.id,
        'name': r.name,
        'created_at': r.created_at.isoformat(),
    } for r in rooms])


@clans_bp.route('/api/clans/<int:clan_id>/rooms', methods=['POST'])
@require_auth
def create_room(clan_id):
    user = g.current_user
    if not _is_clan_admin(user, clan_id) and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = request.json
    if not data.get('name'):
        return jsonify({'error': 'name обязателен'}), 400
    room = ClanChatRoom(clan_id=clan_id, name=data['name'])
    db.session.add(room)
    db.session.commit()
    return jsonify({'id': room.id, 'name': room.name}), 201


@clans_bp.route('/api/clans/<int:clan_id>/rooms/<int:room_id>/messages', methods=['GET'])
@require_auth
def list_messages(clan_id, room_id):
    user = g.current_user
    if not _is_clan_member(user, clan_id) and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    limit = request.args.get('limit', 50, type=int)
    before = request.args.get('before', type=int)
    query = ClanChatMessage.query.filter_by(room_id=room_id, is_deleted=False)
    if before:
        query = query.filter(ClanChatMessage.id < before)
    messages = query.order_by(ClanChatMessage.created_at.desc()).limit(limit).all()
    messages.reverse()
    return jsonify([{
        'id': m.id,
        'user_id': m.user_id,
        'username': m.user.username,
        'content': m.content,
        'created_at': m.created_at.isoformat(),
        'is_deleted': m.is_deleted,
    } for m in messages])


@clans_bp.route('/api/clans/<int:clan_id>/rooms/<int:room_id>/messages', methods=['POST'])
@require_auth
def send_message(clan_id, room_id):
    user = g.current_user
    if not _is_clan_member(user, clan_id) and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = request.json
    if not data.get('content'):
        return jsonify({'error': 'content обязателен'}), 400
    msg = ClanChatMessage(room_id=room_id, user_id=user.id, content=data['content'])
    db.session.add(msg)
    db.session.commit()
    return jsonify({
        'id': msg.id,
        'user_id': msg.user_id,
        'username': msg.user.username,
        'content': msg.content,
        'created_at': msg.created_at.isoformat(),
    }), 201


@clans_bp.route('/api/clans/<int:clan_id>/rooms/<int:room_id>/messages/<int:msg_id>', methods=['DELETE'])
@require_auth
def delete_message(clan_id, room_id, msg_id):
    user = g.current_user
    msg = ClanChatMessage.query.get_or_404(msg_id)
    if msg.user_id != user.id and not _is_clan_admin(user, clan_id) and user.role != 'admin':
        return jsonify({'error': 'Доступ запрещён'}), 403
    msg.is_deleted = True
    db.session.commit()
    return jsonify({'status': 'deleted'})
