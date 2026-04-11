from flask import Blueprint, request, jsonify
from services.clan_parser import fetch_clan_page, parse_clan_info
from models import db
from models.clan_info import ClanInfo, ClanMemberInfo


clan_info_bp = Blueprint('clan_info', __name__)


@clan_info_bp.route('/api/clan/<int:clan_id>/info', methods=['GET'])
def get_clan_info(clan_id):
    cached = ClanInfo.query.filter_by(clan_id=clan_id).first()

    try:
        html, _ = fetch_clan_page(clan_id, mode='news')
        data = parse_clan_info(html, clan_id)

        if cached:
            cached.name = data['name']
            cached.logo_url = data.get('logo_url', '')
            cached.description = data.get('description', '')
            cached.leader_nick = data.get('leader_nick', '')
            cached.leader_rank = data.get('leader_rank', '')
            cached.clan_rank = data.get('clan_rank', '')
            cached.clan_level = data.get('clan_level', 0)
            cached.step = data.get('step', 0)
            cached.talents = data.get('talents', 0)
        else:
            cached = ClanInfo(
                clan_id=clan_id,
                name=data['name'],
                logo_url=data.get('logo_url', ''),
                description=data.get('description', ''),
                leader_nick=data.get('leader_nick', ''),
                leader_rank=data.get('leader_rank', ''),
                clan_rank=data.get('clan_rank', ''),
                clan_level=data.get('clan_level', 0),
                step=data.get('step', 0),
                talents=data.get('talents', 0),
            )
            db.session.add(cached)
        db.session.commit()
    except Exception as e:
        if cached:
            pass
        else:
            return jsonify({'error': str(e)}), 500

    return jsonify({
        'clan_id': cached.clan_id,
        'name': cached.name,
        'logo_url': cached.logo_url,
        'description': cached.description,
        'leader_nick': cached.leader_nick,
        'leader_rank': cached.leader_rank,
        'clan_rank': cached.clan_rank,
        'clan_level': cached.clan_level,
        'step': cached.step,
        'talents': cached.talents,
        'updated_at': cached.updated_at.isoformat() if cached.updated_at else '',
    })


# Import/reset endpoints removed - all member management now via UI


@clan_info_bp.route('/api/clan/<int:clan_id>/members', methods=['GET'])
def get_clan_members(clan_id):
    members = ClanMemberInfo.query.filter_by(clan_id=clan_id).all()
    return jsonify([{
        'id': m.id,
        'nick': m.nick,
        'icon': m.icon,
        'game_rank': m.game_rank,
        'level': m.level,
        'profession': m.profession,
        'profession_level': m.profession_level,
        'clan_role': m.clan_role,
        'join_date': m.join_date,
        'trial_until': m.trial_until,
    } for m in members])


@clan_info_bp.route('/api/clan/<int:clan_id>/members', methods=['POST'])
def add_clan_member(clan_id):
    data = request.json
    required = ['nick', 'level', 'clan_role']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} обязателен'}), 400

    member = ClanMemberInfo(
        clan_id=clan_id,
        nick=data['nick'],
        icon=data.get('icon', ''),
        game_rank=data.get('game_rank', ''),
        level=data['level'],
        profession=data.get('profession', ''),
        profession_level=data.get('profession_level', 0),
        clan_role=data['clan_role'],
        join_date=data.get('join_date', ''),
        trial_until=data.get('trial_until', ''),
    )
    db.session.add(member)
    db.session.commit()

    return jsonify({
        'id': member.id,
        'nick': member.nick,
        'icon': member.icon,
        'game_rank': member.game_rank,
        'level': member.level,
        'profession': member.profession,
        'profession_level': member.profession_level,
        'clan_role': member.clan_role,
        'join_date': member.join_date,
        'trial_until': member.trial_until,
    }), 201


@clan_info_bp.route('/api/clan/<int:clan_id>/members/<int:member_id>', methods=['DELETE'])
def delete_clan_member(clan_id, member_id):
    member = ClanMemberInfo.query.filter_by(id=member_id, clan_id=clan_id).first()
    if not member:
        return jsonify({'error': 'Участник не найден'}), 404
    db.session.delete(member)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@clan_info_bp.route('/api/clan/<int:clan_id>/members/<int:member_id>', methods=['PUT'])
def update_clan_member(clan_id, member_id):
    member = ClanMemberInfo.query.filter_by(id=member_id, clan_id=clan_id).first()
    if not member:
        return jsonify({'error': 'Участник не найден'}), 404

    data = request.json
    if 'nick' in data:
        member.nick = data['nick']
    if 'icon' in data:
        member.icon = data['icon']
    if 'game_rank' in data:
        member.game_rank = data['game_rank']
    if 'level' in data:
        member.level = data['level']
    if 'profession' in data:
        member.profession = data['profession']
    if 'profession_level' in data:
        member.profession_level = data['profession_level']
    if 'clan_role' in data:
        member.clan_role = data['clan_role']
    if 'join_date' in data:
        member.join_date = data['join_date']
    if 'trial_until' in data:
        member.trial_until = data['trial_until']

    db.session.commit()
    return jsonify({
        'id': member.id,
        'nick': member.nick,
        'icon': member.icon,
        'game_rank': member.game_rank,
        'level': member.level,
        'profession': member.profession,
        'profession_level': member.profession_level,
        'clan_role': member.clan_role,
        'join_date': member.join_date,
        'trial_until': member.trial_until,
    })
