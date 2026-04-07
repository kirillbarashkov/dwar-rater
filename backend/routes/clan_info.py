from flask import Blueprint, request, jsonify
from services.clan_parser import fetch_clan_page, parse_clan_info, parse_clan_members
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


@clan_info_bp.route('/api/clan/<int:clan_id>/members', methods=['GET'])
def get_clan_members(clan_id):
    try:
        html, _ = fetch_clan_page(clan_id, mode='members')
        raw_members = parse_clan_members(html, clan_id)

        if len(raw_members) > 0:
            ClanMemberInfo.query.filter_by(clan_id=clan_id).delete()
            for m in raw_members:
                member = ClanMemberInfo(
                    clan_id=clan_id,
                    nick=m['nick'],
                    game_rank=m.get('game_rank', ''),
                    level=m.get('level', 0),
                    profession=m.get('profession', ''),
                    profession_level=m.get('profession_level', 0),
                    clan_role=m.get('clan_role', ''),
                    join_date=m.get('join_date', ''),
                    trial_until=m.get('trial_until', ''),
                )
                db.session.add(member)
            db.session.commit()
    except Exception:
        pass

    members = ClanMemberInfo.query.filter_by(clan_id=clan_id).all()
    return jsonify([{
        'nick': m.nick,
        'game_rank': m.game_rank,
        'level': m.level,
        'profession': m.profession,
        'profession_level': m.profession_level,
        'clan_role': m.clan_role,
        'join_date': m.join_date,
        'trial_until': m.trial_until,
    } for m in members])
