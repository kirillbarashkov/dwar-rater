from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from shared.services.parser import fetch_character_page, parse_character
from shared.services.processor import process_character
from shared.services.cache_service import save_character_cache
from models import db
from shared.models.closed_profile import ClosedProfile
from shared.models.character_snapshot import CharacterSnapshot
from shared.middleware.auth import require_auth


closed_profiles_bp = Blueprint('closed_profiles', __name__)


@closed_profiles_bp.route('/api/closed-profiles', methods=['GET'])
@require_auth
def get_closed_profiles():
    profiles = ClosedProfile.query.order_by(ClosedProfile.last_checked.asc().nullsfirst()).all()
    return jsonify([p.to_dict() for p in profiles])


@closed_profiles_bp.route('/api/closed-profiles', methods=['POST'])
@require_auth
def add_closed_profile():
    data = request.json
    nick = data.get('nick', '').strip()
    if not nick:
        return jsonify({'error': 'Ник не указан'}), 400

    existing = ClosedProfile.query.filter_by(nick=nick).first()
    if existing:
        return jsonify({
            'exists': True,
            'is_scanned_open': existing.is_scanned_open,
            'scanned_open_at': existing.scanned_open_at.isoformat() if existing.scanned_open_at else None,
        }), 200

    profile = ClosedProfile(nick=nick)
    db.session.add(profile)
    db.session.commit()
    return jsonify(profile.to_dict()), 201


@closed_profiles_bp.route('/api/closed-profiles/<int:profile_id>', methods=['PUT'])
@require_auth
def update_closed_profile(profile_id):
    profile = ClosedProfile.query.get_or_404(profile_id)
    data = request.json
    if 'notes' in data:
        profile.notes = data['notes']
    db.session.commit()
    return jsonify(profile.to_dict())


@closed_profiles_bp.route('/api/closed-profiles/<int:profile_id>', methods=['DELETE'])
@require_auth
def delete_closed_profile(profile_id):
    profile = ClosedProfile.query.get_or_404(profile_id)
    db.session.delete(profile)
    db.session.commit()
    return jsonify({'success': True})


@closed_profiles_bp.route('/api/closed-profiles/<nick>/check', methods=['POST'])
@require_auth
def check_profile(nick):
    profile = ClosedProfile.query.filter_by(nick=nick).first()
    if not profile:
        return jsonify({'error': 'Персонаж не найден в списке'}), 404

    profile.check_count += 1
    profile.last_checked = datetime.now(timezone.utc)

    try:
        url = f'https://w1.dwar.ru/user_info.php?nick={nick}'
        html, session = fetch_character_page(url)
        raw = parse_character(html, session=session, nick=nick)

        has_stats = len(raw.get('stats', {})) > 0
        has_equipment = len(raw.get('equipment_raw', [])) > 0

        if has_stats or has_equipment:
            save_character_cache(nick, raw)
            processed = process_character(raw)

            profile.status = 'opened'
            profile.is_scanned_open = True
            profile.scanned_open_at = datetime.now(timezone.utc)
            profile.level = raw.get('stats', {}).get('Уровень', '')
            profile.rank = raw.get('stats', {}).get('Звание', '')
            profile.clan = raw.get('stats', {}).get('Клан', '')
            db.session.commit()

            return jsonify({
                'status': 'opened',
                'data': processed,
                'profile': profile.to_dict(),
            })
        else:
            profile.status = 'closed'
            closed_info = raw.get('closed_info', {})
            if closed_info:
                profile.level = closed_info.get('level', profile.level)
                profile.rank = closed_info.get('rank', profile.rank)
                profile.clan = closed_info.get('clan', profile.clan)
            db.session.commit()

            return jsonify({
                'status': 'closed',
                'profile': profile.to_dict(),
            })

    except Exception as e:
        db.session.commit()
        return jsonify({
            'status': 'error',
            'error': str(e),
            'profile': profile.to_dict(),
        })


@closed_profiles_bp.route('/api/closed-profiles/batch-scan', methods=['POST'])
@require_auth
def batch_scan():
    data = request.json
    nicks = data.get('nicks', [])
    if not nicks:
        return jsonify({'error': 'Список ников пуст'}), 400

    results = []
    for nick in nicks:
        profile = ClosedProfile.query.filter_by(nick=nick).first()
        if not profile:
            results.append({'nick': nick, 'status': 'not_found'})
            continue

        profile.check_count += 1
        profile.last_checked = datetime.now(timezone.utc)

        try:
            url = f'https://w1.dwar.ru/user_info.php?nick={nick}'
            html, session = fetch_character_page(url)
            raw = parse_character(html, session=session, nick=nick)

            has_stats = len(raw.get('stats', {})) > 0
            has_equipment = len(raw.get('equipment_raw', [])) > 0

            if has_stats or has_equipment:
                save_character_cache(nick, raw)
                processed = process_character(raw)

                profile.status = 'opened'
                profile.is_scanned_open = True
                profile.scanned_open_at = datetime.now(timezone.utc)
                profile.level = raw.get('stats', {}).get('Уровень', '')
                profile.rank = raw.get('stats', {}).get('Звание', '')
                profile.clan = raw.get('stats', {}).get('Клан', '')
                db.session.commit()

                results.append({
                    'nick': nick,
                    'status': 'opened',
                    'data': processed,
                })
            else:
                profile.status = 'closed'
                closed_info = raw.get('closed_info', {})
                if closed_info:
                    profile.level = closed_info.get('level', profile.level)
                    profile.rank = closed_info.get('rank', profile.rank)
                db.session.commit()

                results.append({'nick': nick, 'status': 'closed'})

        except Exception:
            db.session.commit()
            results.append({'nick': nick, 'status': 'error'})

    return jsonify({'results': results})


@closed_profiles_bp.route('/api/closed-profiles/batch-delete', methods=['POST'])
@require_auth
def batch_delete():
    data = request.json
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'error': 'Список ID пуст'}), 400

    ClosedProfile.query.filter(ClosedProfile.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'deleted': len(ids)})


@closed_profiles_bp.route('/api/closed-profiles/delete-all', methods=['POST'])
@require_auth
def delete_all():
    count = ClosedProfile.query.count()
    ClosedProfile.query.delete()
    db.session.commit()
    return jsonify({'success': True, 'deleted': count})


@closed_profiles_bp.route('/api/closed-profiles/<nick>/save-snapshot', methods=['POST'])
@require_auth
def save_snapshot_for_profile(nick):
    profile = ClosedProfile.query.filter_by(nick=nick).first()
    if not profile:
        return jsonify({'error': 'Персонаж не найден'}), 404

    data = request.json
    snapshot_data = data.get('snapshot_data')
    if not snapshot_data:
        return jsonify({'error': 'Нет данных для сохранения'}), 400

    snapshot = CharacterSnapshot(
        nick=nick,
        name=snapshot_data.get('name', nick),
        race=snapshot_data.get('race', ''),
        rank=snapshot_data.get('rank', ''),
        clan=snapshot_data.get('clan', ''),
        snapshot_name=data.get('snapshot_name', f'{nick} - открытый профиль'),
        snapshot_data=str(snapshot_data),
    )
    db.session.add(snapshot)
    db.session.flush()

    profile.snapshot_id = snapshot.id
    db.session.commit()

    return jsonify({'success': True, 'snapshot_id': snapshot.id})
