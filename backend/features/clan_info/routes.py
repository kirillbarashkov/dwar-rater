from flask import Blueprint, request, jsonify
from datetime import datetime
from shared.services.clan_parser import fetch_clan_page, parse_clan_info, fetch_clan_treasury_report, parse_clan_treasury_operations
from shared.services.data_logger import data_logger
from shared.models import db
from shared.models.clan_info import ClanInfo, ClanMemberInfo, TreasuryOperation
from shared.rbac import require_permission, feature, Permission as PermDef


clan_info_bp = Blueprint('clan_info', __name__)

from shared.rbac import register_feature
register_feature('clan_info', [
    PermDef('read', 'Просмотр инфо/состава/казны', 'GET /api/clan/*'),
    PermDef('write', 'Редактирование участников', 'POST/PUT/DELETE /api/clan/*/members/*'),
    PermDef('admin', 'Импорт/экспорт казны, бэкапы', 'Treasury import/export/backup admin'),
])


LEADER_ROLE = 'Глава Ордена'
DEPUTY_ROLE = 'Зам. Главы'
COUNCIL_ROLE = 'Совесть'
COMMANDER_ROLE = 'Воевода'

DEFAULT_COUNCIL_SLOTS = 4


def build_clan_structure_from_members(clan_id, existing_structure=None):
    members = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).all()

    leaders = [m for m in members if m.clan_role == LEADER_ROLE]
    deputies = [m for m in members if m.clan_role == DEPUTY_ROLE]

    if len(leaders) > 1:
        leader_nicks = [m.nick for m in leaders]
        return None, f"Несколько глав клана: {', '.join(leader_nicks)}. Оставьте одного."

    structure = {}

    if leaders:
        structure['leader'] = {
            'nick': leaders[0].nick,
            'description': '',
        }

    if deputies:
        structure['deputies'] = [
            {'nick': d.nick, 'description': ''} for d in deputies
        ]

    if existing_structure:
        if 'council' in existing_structure:
            valid_council = []
            for c in existing_structure['council']:
                nick = c.get('nick', '')
                if any(m.nick == nick for m in members):
                    valid_council.append(c)
            if valid_council:
                structure['council'] = valid_council

        if 'commander' in existing_structure:
            cmd_nick = existing_structure['commander'].get('nick', '')
            if cmd_nick and any(m.nick == cmd_nick for m in members):
                structure['commander'] = existing_structure['commander']

        if 'council_slots' in existing_structure:
            structure['council_slots'] = existing_structure['council_slots']

    other_count = len([m for m in members if m.clan_role not in (LEADER_ROLE, DEPUTY_ROLE, COUNCIL_ROLE, COMMANDER_ROLE)])
    structure['has_members'] = other_count > 0

    if 'council_slots' not in structure:
        structure['council_slots'] = DEFAULT_COUNCIL_SLOTS

    return structure, None


@clan_info_bp.route('/api/clan/<int:clan_id>/info', methods=['GET'])
@require_permission('clan_info', 'read')
def get_clan_info(clan_id):
    cached = ClanInfo.query.filter_by(clan_id=clan_id).first()

    structure_warning = None
    structure_error = None
    try:
        html, _ = fetch_clan_page(clan_id, mode='news')
        data = parse_clan_info(html, clan_id)

        actual_member_count = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).count()

        existing_structure = cached.get_clan_structure() if cached else None
        structure, structure_error = build_clan_structure_from_members(clan_id, existing_structure)

        if cached:
            cached.name = data['name']
            if not cached.logo_big and data.get('logo_url'):
                cached.logo_url = data.get('logo_url', '')
                cached.logo_big = data.get('logo_big', '')
                cached.logo_small = data.get('logo_small', '')
            cached.description = data.get('description', '')
            cached.leader_nick = data.get('leader_nick', '')
            cached.leader_rank = data.get('leader_rank', '')
            cached.clan_rank = data.get('clan_rank', '')
            cached.clan_level = data.get('clan_level', 0)
            cached.step = data.get('step', 0)
            cached.talents = data.get('talents', 0)
            cached.current_players = actual_member_count

            if structure is not None:
                cached.set_clan_structure(structure)
        else:
            cached = ClanInfo(
                clan_id=clan_id,
                name=data['name'],
                logo_url=data.get('logo_url', ''),
                logo_big=data.get('logo_big', ''),
                logo_small=data.get('logo_small', ''),
                description=data.get('description', ''),
                leader_nick=data.get('leader_nick', ''),
                leader_rank=data.get('leader_rank', ''),
                clan_rank=data.get('clan_rank', ''),
                clan_level=data.get('clan_level', 0),
                step=data.get('step', 0),
                talents=data.get('talents', 0),
                current_players=actual_member_count,
            )
            if structure is not None:
                cached.set_clan_structure(structure)
            db.session.add(cached)
        db.session.commit()
    except Exception as e:
        if cached:
            pass
        else:
            return jsonify({'error': str(e)}), 500

    if structure_error:
        structure_warning = structure_error

    return jsonify({
        'clan_id': cached.clan_id,
        'name': cached.name,
        'logo_url': cached.logo_url,
        'logo_big': cached.logo_big,
        'logo_small': cached.logo_small,
        'description': cached.description,
        'leader_nick': cached.leader_nick,
        'leader_rank': cached.leader_rank,
        'clan_rank': cached.clan_rank,
        'clan_level': cached.clan_level,
        'step': cached.step,
        'talents': cached.talents,
        'total_players': cached.total_players,
        'current_players': cached.current_players,
        'council': cached.get_council(),
        'clan_structure': cached.get_clan_structure(),
        'structure_warning': structure_warning,
        'updated_at': cached.updated_at.isoformat() if cached.updated_at else '',
    })


@clan_info_bp.route('/api/clan/<int:clan_id>/info', methods=['PUT'])
@require_permission('clan_info', 'write')
def update_clan_info(clan_id):
    cached = ClanInfo.query.filter_by(clan_id=clan_id).first()
    if not cached:
        return jsonify({'error': 'Клан не найден'}), 404

    data = request.json

    if 'name' in data:
        cached.name = data['name']
    if 'logo_url' in data:
        cached.logo_url = data['logo_url']
    if 'logo_big' in data:
        cached.logo_big = data['logo_big']
    if 'logo_small' in data:
        cached.logo_small = data['logo_small']
    if 'description' in data:
        cached.description = data['description']
    if 'leader_nick' in data:
        cached.leader_nick = data['leader_nick']
    if 'leader_rank' in data:
        cached.leader_rank = data['leader_rank']
    if 'clan_rank' in data:
        cached.clan_rank = data['clan_rank']
    if 'clan_level' in data:
        cached.clan_level = data['clan_level']
    if 'step' in data:
        cached.step = data['step']
    if 'talents' in data:
        cached.talents = data['talents']
    if 'total_players' in data:
        cached.total_players = data['total_players']
    if 'current_players' in data:
        cached.current_players = data['current_players']
    if 'council' in data:
        cached.set_council(data['council'])
    if 'clan_structure' in data:
        cached.set_clan_structure(data['clan_structure'])

    db.session.commit()

    return jsonify({
        'clan_id': cached.clan_id,
        'name': cached.name,
        'logo_url': cached.logo_url,
        'logo_big': cached.logo_big,
        'logo_small': cached.logo_small,
        'description': cached.description,
        'leader_nick': cached.leader_nick,
        'leader_rank': cached.leader_rank,
        'clan_rank': cached.clan_rank,
        'clan_level': cached.clan_level,
        'step': cached.step,
'talents': cached.talents,
        'total_players': cached.total_players,
        'current_players': cached.current_players,
        'council': cached.get_council(),
        'clan_structure': cached.get_clan_structure(),
        'updated_at': cached.updated_at.isoformat() if cached.updated_at else '',
    })


# Import/reset endpoints removed - all member management now via UI


@clan_info_bp.route('/api/clan/<int:clan_id>/members', methods=['GET'])
@require_permission('clan_info', 'read')
def get_clan_members(clan_id):
    members = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).all()
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


@clan_info_bp.route('/api/clan/<int:clan_id>/members/left', methods=['GET'])
@require_permission('clan_info', 'read')
def get_left_members(clan_id):
    members = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=True).all()
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
        'left_date': m.left_date,
        'leave_reason': m.leave_reason,
    } for m in members])


@clan_info_bp.route('/api/clan/<int:clan_id>/members', methods=['POST'])
@require_permission('clan_info', 'write')
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


@clan_info_bp.route('/api/clan/<int:clan_id>/members/import', methods=['POST'])
@require_permission('clan_info', 'admin')
def import_clan_members(clan_id):
    from flask import g
    
    if not g.current_user or g.current_user.role != 'admin':
        data_logger.warning(f'[IMPORT] Unauthorized import attempt for clan {clan_id}')
        return jsonify({'error': 'Только администратор может импортировать участников'}), 403
    
    data = request.json
    members_data = data.get('members', [])
    clan_info_data = data.get('clanInfo')
    overwrite = data.get('overwrite', False)
    
    data_logger.info(f'[IMPORT] Starting import for clan {clan_id}, members count: {len(members_data)}, overwrite: {overwrite}, hasClanInfo: {clan_info_data is not None}')
    
    if not isinstance(members_data, list):
        data_logger.warning(f'[IMPORT] Invalid data format for clan {clan_id}')
        return jsonify({'error': 'members должен быть массивом'}), 400
    
    if clan_info_data:
        clan = ClanInfo.query.filter_by(clan_id=clan_id).first()
        if not clan:
            clan = ClanInfo(clan_id=clan_id, name='Орден Чести')
            db.session.add(clan)
        
        if clan_info_data.get('logo_big'):
            clan.logo_big = clan_info_data['logo_big']
        if clan_info_data.get('logo_small'):
            clan.logo_small = clan_info_data['logo_small']
        if clan_info_data.get('clan_rank'):
            clan.clan_rank = clan_info_data['clan_rank']
        if clan_info_data.get('clan_level'):
            clan.clan_level = clan_info_data['clan_level']
        if clan_info_data.get('step'):
            clan.step = clan_info_data['step']
        if clan_info_data.get('talents'):
            clan.talents = clan_info_data['talents']
        if clan_info_data.get('total_players'):
            clan.total_players = clan_info_data['total_players']
        if clan_info_data.get('current_players'):
            clan.current_players = clan_info_data['current_players']
        if clan_info_data.get('clan_structure'):
            data_logger.info(f'[IMPORT] Setting clan structure')
            clan.set_clan_structure(clan_info_data['clan_structure'])
        else:
            data_logger.warning(f'[IMPORT] No clan_structure in clanInfo: {list(clan_info_data.keys())}')
        
        data_logger.info(f'[IMPORT] Updated clan info for clan {clan_id}')
    
    if overwrite:
        old_count = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).count()
        ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).update({'is_deleted': True})
        data_logger.info(f'[IMPORT] Soft-deleted {old_count} existing members for clan {clan_id}')
    
    success = 0
    failed = 0
    errors = []
    skipped = 0
    
    for i, member_data in enumerate(members_data):
        try:
            nick = member_data.get('nick', '').strip()
            if not nick:
                errors.append(f'Строка {i + 1}: пустой ник')
                failed += 1
                continue
            
            level = member_data.get('level', 1)
            if isinstance(level, str):
                try:
                    level = int(level)
                except ValueError:
                    level = 1
            
            clan_role = member_data.get('clan_role', 'Рыцарь Ордена')
            
            existing = ClanMemberInfo.query.filter_by(clan_id=clan_id, nick=nick, is_deleted=False).first()
            
            if existing:
                if overwrite:
                    existing.is_deleted = False
                    existing.game_rank = member_data.get('game_rank', '')
                    existing.level = level
                    existing.profession = member_data.get('profession', '')
                    existing.profession_level = member_data.get('profession_level', 0)
                    existing.clan_role = clan_role
                    existing.join_date = member_data.get('join_date', '')
                    existing.trial_until = member_data.get('trial_until', '')
                    success += 1
                    data_logger.debug(f'[IMPORT] Updated member: {nick} (level {level})')
                else:
                    skipped += 1
            else:
                member = ClanMemberInfo(
                    clan_id=clan_id,
                    nick=nick,
                    icon=member_data.get('icon', ''),
                    game_rank=member_data.get('game_rank', ''),
                    level=level,
                    profession=member_data.get('profession', ''),
                    profession_level=member_data.get('profession_level', 0),
                    clan_role=clan_role,
                    join_date=member_data.get('join_date', ''),
                    trial_until=member_data.get('trial_until', ''),
                )
                db.session.add(member)
                success += 1
                data_logger.debug(f'[IMPORT] Added new member: {nick} (level {level})')
        except Exception as e:
            errors.append(f'Строка {i + 1}: {str(e)}')
            failed += 1
            data_logger.error(f'[IMPORT] Error on member {i + 1}: {str(e)}')
    
    db.session.commit()
    
    final_count = ClanMemberInfo.query.filter_by(clan_id=clan_id, is_deleted=False).count()
    data_logger.info(f'[IMPORT] Completed for clan {clan_id}: success={success}, skipped={skipped}, failed={failed}, final_count={final_count}')
    
    return jsonify({
        'success': success,
        'skipped': skipped,
        'failed': failed,
        'errors': errors,
    })


@clan_info_bp.route('/api/clan/<int:clan_id>/members/<int:member_id>', methods=['DELETE'])
@require_permission('clan_info', 'write')
def delete_clan_member(clan_id, member_id):
    member = ClanMemberInfo.query.filter_by(id=member_id, clan_id=clan_id).first()
    if not member:
        data_logger.warning(f'[DELETE] Member {member_id} not found in clan {clan_id}')
        return jsonify({'error': 'Участник не найден'}), 404
    
    data = request.json or {}
    member_nick = member.nick
    member.is_deleted = True
    member.left_date = data.get('left_date', '')
    member.leave_reason = data.get('leave_reason', '')
    db.session.commit()
    data_logger.info(f'[DELETE] Soft-deleted member {member_nick} (id={member_id}) from clan {clan_id}, reason={member.leave_reason}')
    return jsonify({'status': 'deleted'})


@clan_info_bp.route('/api/clan/<int:clan_id>/members/<int:member_id>', methods=['PUT'])
@require_permission('clan_info', 'write')
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


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury/export', methods=['GET'])
@require_permission('clan_info', 'read')
def export_treasury_operations(clan_id):
    operations = TreasuryOperation.query.filter_by(clan_id=clan_id).order_by(TreasuryOperation.id.desc()).all()
    
    export_data = {
        'version': 1,
        'exported_at': datetime.utcnow().isoformat(),
        'clan_id': clan_id,
        'operations_count': len(operations),
        'operations': [
            {
                'id': op.id,
                'date': op.date,
                'nick': op.nick,
                'operation_type': op.operation_type,
                'object_name': op.object_name,
                'quantity': op.quantity,
                'compensation_flag': op.compensation_flag,
                'compensation_comment': op.compensation_comment,
                'created_at': op.created_at.isoformat() if op.created_at else None,
            }
            for op in operations
        ]
    }
    
    data_logger.info(f'[TREASURY] Exported {len(operations)} operations for clan {clan_id}')
    
    return jsonify(export_data)


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury/backup', methods=['POST'])
@require_permission('clan_info', 'write')
def save_treasury_backup(clan_id):
    import os
    from flask import current_app
    
    operations = TreasuryOperation.query.filter_by(clan_id=clan_id).order_by(TreasuryOperation.id.desc()).all()
    
    export_data = {
        'version': 1,
        'exported_at': datetime.utcnow().isoformat(),
        'clan_id': clan_id,
        'operations_count': len(operations),
        'operations': [
            {
                'id': op.id,
                'date': op.date,
                'nick': op.nick,
                'operation_type': op.operation_type,
                'object_name': op.object_name,
                'quantity': op.quantity,
                'compensation_flag': op.compensation_flag,
                'compensation_comment': op.compensation_comment,
                'created_at': op.created_at.isoformat() if op.created_at else None,
            }
            for op in operations
        ]
    }
    
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    
    filename = f'treasury-{clan_id}-{datetime.utcnow().strftime("%Y%m%d-%H%M%S")}.json'
    filepath = os.path.join(backup_dir, filename)
    
    import json
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    data_logger.info(f'[TREASURY] Backup saved to {filepath}')
    
    return jsonify({
        'success': True,
        'filename': filename,
        'operations_count': len(operations),
        'message': f'Бэкап сохранён: {filename}',
    })


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury/backups', methods=['GET'])
@require_permission('clan_info', 'read')
def list_treasury_backups(clan_id):
    import os
    import glob
    
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backup')
    pattern = os.path.join(backup_dir, f'treasury-{clan_id}-*.json')
    files = glob.glob(pattern)
    
    backups = []
    for filepath in sorted(files, key=os.path.getmtime, reverse=True):
        filename = os.path.basename(filepath)
        stat = os.stat(filepath)
        backups.append({
            'filename': filename,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    
    return jsonify({'backups': backups})


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury/backup/<filename>', methods=['GET'])
@require_permission('clan_info', 'read')
def get_treasury_backup(clan_id, filename):
    import os
    import re
    
    if not re.match(r'^treasury-\d+-\d{8}-\d{6}\.json$', filename):
        return jsonify({'error': 'Invalid filename'}), 400
    
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backup')
    filepath = os.path.join(backup_dir, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'Backup not found'}), 404
    
    import json
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return jsonify(data)


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury/backup/restore', methods=['POST'])
@require_permission('clan_info', 'admin')
def restore_treasury_backup(clan_id):
    from flask import g
    
    if not g.current_user or g.current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может восстанавливать бэкапы'}), 403
    
    data = request.json
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'error': 'Filename required'}), 400
    
    import os
    import re
    
    if not re.match(r'^treasury-\d+-\d{8}-\d{6}\.json$', filename):
        return jsonify({'error': 'Invalid filename'}), 400
    
    backup_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backup')
    filepath = os.path.join(backup_dir, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'Backup not found'}), 404
    
    import json
    with open(filepath, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    TreasuryOperation.query.filter_by(clan_id=clan_id).delete()
    
    imported = 0
    for op in backup_data.get('operations', []):
        treasury_op = TreasuryOperation(
            clan_id=clan_id,
            date=op.get('date', ''),
            nick=op.get('nick', ''),
            operation_type=op.get('operation_type', ''),
            object_name=op.get('object_name', ''),
            quantity=op.get('quantity', 0),
            compensation_flag=op.get('compensation_flag', False),
            compensation_comment=op.get('compensation_comment', ''),
        )
        db.session.add(treasury_op)
        imported += 1
    
    db.session.commit()
    
    data_logger.info(f'[TREASURY] Restored {imported} operations from {filename}')
    
    return jsonify({
        'success': True,
        'imported': imported,
        'message': f'Восстановлено {imported} операций из {filename}',
    })


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury', methods=['GET'])
@require_permission('clan_info', 'read')
def get_treasury_operations(clan_id):
    operations = TreasuryOperation.query.filter_by(clan_id=clan_id).order_by(TreasuryOperation.id.desc()).all()
    return jsonify([{
        'id': op.id,
        'date': op.date,
        'nick': op.nick,
        'operation_type': op.operation_type,
        'object_name': op.object_name,
        'quantity': op.quantity,
        'compensation_flag': op.compensation_flag,
        'compensation_comment': op.compensation_comment,
    } for op in operations])


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury/<int:operation_id>', methods=['PUT'])
@require_permission('clan_info', 'admin')
def update_treasury_operation(clan_id, operation_id):
    from flask import g
    
    if not g.current_user or g.current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может изменять операции'}), 403
    
    operation = TreasuryOperation.query.filter_by(id=operation_id, clan_id=clan_id).first()
    if not operation:
        return jsonify({'error': 'Операция не найдена'}), 404
    
    data = request.json
    
    if 'quantity' in data:
        operation.quantity = int(data['quantity'])
    if 'compensation_flag' in data:
        operation.compensation_flag = bool(data['compensation_flag'])
    if 'compensation_comment' in data:
        operation.compensation_comment = data['compensation_comment']
    
    db.session.commit()
    
    data_logger.info(f'[TREASURY] Updated operation {operation_id}: qty={operation.quantity}, comp={operation.compensation_flag}, comment={operation.compensation_comment}')
    
    return jsonify({
        'id': operation.id,
        'date': operation.date,
        'nick': operation.nick,
        'operation_type': operation.operation_type,
        'object_name': operation.object_name,
        'quantity': operation.quantity,
        'compensation_flag': operation.compensation_flag,
        'compensation_comment': operation.compensation_comment,
    })


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury/compensation', methods=['POST'])
@require_permission('clan_info', 'admin')
def create_treasury_compensation(clan_id):
    from flask import g
    
    if not g.current_user or g.current_user.role != 'admin':
        return jsonify({'error': 'Только администратор может создавать компенсации'}), 403
    
    data = request.json
    nick = data.get('nick')
    norm_amount = data.get('norm_amount', 0)
    comment = data.get('comment', '')
    months = data.get('months', [])
    year = data.get('year', datetime.now().year)
    
    if not nick:
        return jsonify({'error': 'nick обязателен'}), 400
    
    if not months:
        return jsonify({'error': 'months обязателен'}), 400
    
    created = []
    for month in months:
        date_str = f'15.{month:02d}.{year} 00:00'
        
        treasury_op = TreasuryOperation(
            clan_id=clan_id,
            date=date_str,
            nick=nick,
            operation_type='Деньги',
            object_name='Монеты',
            quantity=norm_amount,
            compensation_flag=True,
            compensation_comment=comment,
        )
        db.session.add(treasury_op)
        created.append(treasury_op)
    
    db.session.commit()
    
    data_logger.info(f'[TREASURY] Created {len(created)} compensations for {nick}: amount={norm_amount}, months={months}, comment={comment}')
    
    return jsonify({
        'created': len(created),
        'operations': [{
            'id': op.id,
            'date': op.date,
            'nick': op.nick,
            'quantity': op.quantity,
            'compensation_flag': op.compensation_flag,
            'compensation_comment': op.compensation_comment,
        } for op in created],
    }), 201


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury/import', methods=['POST'])
@require_permission('clan_info', 'admin')
def import_treasury_operations(clan_id):
    from flask import g
    
    if not g.current_user or g.current_user.role != 'admin':
        data_logger.warning(f'[TREASURY] Unauthorized import attempt for clan {clan_id}')
        return jsonify({'error': 'Только администратор может импортировать казну'}), 403
    
    data = request.json
    operations_data = data.get('operations', [])
    replace = data.get('replace', False)
    
    data_logger.info(f'[TREASURY] Importing {len(operations_data)} operations for clan {clan_id} (replace={replace})')
    
    if replace:
        TreasuryOperation.query.filter_by(clan_id=clan_id).delete()
        data_logger.info(f'[TREASURY] Cleared existing operations for clan {clan_id}')
    
    imported = 0
    updated = 0
    skipped = 0
    skip_reasons = []
    
    data_logger.info(f'[TREASURY] Processing {len(operations_data)} operations from frontend')
    
    for i, op in enumerate(operations_data):
        try:
            date = op.get('date', '')
            nick = op.get('nick', '')
            operation_type = op.get('operation_type', '')
            object_name = op.get('object_name', '')
            quantity = op.get('quantity', 0)
            compensation_flag = op.get('compensation_flag', False)
            compensation_comment = op.get('compensation_comment', '')
            
            if not date or not nick:
                skip_reasons.append(f'op {i}: empty date or nick')
                skipped += 1
                continue
            
            existing = TreasuryOperation.query.filter_by(
                clan_id=clan_id,
                date=date,
                nick=nick,
                operation_type=operation_type,
                object_name=object_name,
            ).first()
            
            if existing:
                if existing.quantity == quantity:
                    data_logger.debug(f'[TREASURY] Op {i} will update: {date}|{nick}|{operation_type}|{object_name}|{quantity}')
                    existing.quantity = quantity
                    existing.compensation_flag = compensation_flag
                    existing.compensation_comment = compensation_comment
                    updated += 1
                else:
                    data_logger.debug(f'[TREASURY] Op {i} will insert NEW (different qty): {date}|{nick}|{operation_type}|{object_name}|{quantity} (existing qty={existing.quantity})')
                    treasury_op = TreasuryOperation(
                        clan_id=clan_id,
                        date=date,
                        nick=nick,
                        operation_type=operation_type,
                        object_name=object_name,
                        quantity=quantity,
                        compensation_flag=compensation_flag,
                        compensation_comment=compensation_comment,
                    )
                    db.session.add(treasury_op)
                    imported += 1
            else:
                data_logger.debug(f'[TREASURY] Op {i} will insert: {date}|{nick}|{operation_type}|{object_name}|{quantity}')
                treasury_op = TreasuryOperation(
                    clan_id=clan_id,
                    date=date,
                    nick=nick,
                    operation_type=operation_type,
                    object_name=object_name,
                    quantity=quantity,
                    compensation_flag=compensation_flag,
                    compensation_comment=compensation_comment,
                )
                db.session.add(treasury_op)
                imported += 1
        except Exception as e:
            data_logger.error(f'[TREASURY] Error importing operation {i}: {str(e)}')
            skip_reasons.append(f'op {i}: exception {str(e)}')
            skipped += 1
    
    if skip_reasons:
        data_logger.warning(f'[TREASURY] Skipped operations: {skip_reasons}')
    
    db.session.commit()
    
    final_count = TreasuryOperation.query.filter_by(clan_id=clan_id).count()
    data_logger.info(f'[TREASURY] Import completed for clan {clan_id}: added={imported}, updated={updated}, skipped={skipped}, total={final_count}')
    
    return jsonify({
        'success': True,
        'imported': imported,
        'updated': updated,
        'skipped': skipped,
        'message': f'Импортировано {imported}, обновлено {updated}',
    })


@clan_info_bp.route('/api/clan/<int:clan_id>/treasury', methods=['POST'])
@require_permission('clan_info', 'admin')
def fetch_treasury_operations(clan_id):
    from flask import g
    
    if not g.current_user or g.current_user.role != 'admin':
        data_logger.warning(f'[TREASURY] Unauthorized fetch attempt for clan {clan_id}')
        return jsonify({'error': 'Только администратор может обновлять казну'}), 403
    
    data_logger.info(f'[TREASURY] Starting treasury fetch for clan {clan_id}')
    
    try:
        html, _ = fetch_clan_treasury_report()
        
        data_logger.info(f'[TREASURY] Received HTML length: {len(html)}')
        
        if 'single_top_redirect' in html or 'index.php' in html:
            data_logger.warning(f'[TREASURY] Site requires authentication, got redirect page')
            return jsonify({
                'success': False,
                'error': 'Требуется авторизация на w1.dwar.ru',
                'message': 'Для импорта казны необходимо войти в игру через браузер и предоставить cookies сессии.',
            }), 200
        
        operations = parse_clan_treasury_operations(html)
        
        data_logger.info(f'[TREASURY] Parsed {len(operations)} operations from page')
        
        old_count = TreasuryOperation.query.filter_by(clan_id=clan_id).count()
        TreasuryOperation.query.filter_by(clan_id=clan_id).delete()
        
        for op in operations:
            treasury_op = TreasuryOperation(
                clan_id=clan_id,
                date=op.get('date', ''),
                nick=op.get('nick', ''),
                operation_type=op.get('type', ''),
                object_name=op.get('object', ''),
                quantity=op.get('quantity', 0),
            )
            db.session.add(treasury_op)
        
        db.session.commit()
        
        final_count = TreasuryOperation.query.filter_by(clan_id=clan_id).count()
        data_logger.info(f'[TREASURY] Completed for clan {clan_id}: old={old_count}, new={final_count}')
        
        return jsonify({
            'success': True,
            'imported': final_count,
            'message': f'Импортировано {final_count} операций',
        })
    except Exception as e:
        data_logger.error(f'[TREASURY] Error fetching treasury for clan {clan_id}: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Ошибка при импорте. Возможно, требуется авторизация на сайте.',
        }), 500
