from flask import Blueprint, request, jsonify, g
from urllib.parse import urlparse, parse_qs

from shared.rbac import require_permission, register_feature, Permission as PermDef
from shared.services.parser import fetch_character_page, parse_character
from shared.services.processor import process_character
from shared.services.cache_service import get_cached_character, save_character_cache, log_analysis

character_bp = Blueprint('character', __name__)

register_feature('character', [
    PermDef('read', 'Доступ к своему персонажу', 'GET /api/auth/me/character — вкладка Персонаж'),
    PermDef('write', 'Обновление своего персонажа', 'PUT /api/auth/profile, POST /api/auth/me/character/refresh'),
])


def _fetch_and_process(user, force=False):
    """Общая логика получения данных своего персонажа.

    Возвращает (response, status_code) — tuple как требует Flask.
    """
    nick = user.character_nick
    url = user.character_url

    if not force:
        cached = get_cached_character(nick)
        if cached:
            log_analysis(user.id, nick, url)
            return process_character(cached), 200

    try:
        html, session = fetch_character_page(url)
        raw = parse_character(html, session=session, nick=nick)
        save_character_cache(nick, raw)
        processed = process_character(raw)
        log_analysis(user.id, nick, url)
        return processed, 200
    except Exception as e:
        error_msg = str(e)
        if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
            return {'error': 'Таймаут запроса к серверу dwar.ru'}, 504
        if 'request' in error_msg.lower():
            return {'error': f'Ошибка загрузки страницы: {error_msg}'}, 500
        return {'error': f'Ошибка обработки: {error_msg}'}, 500


@character_bp.route('/api/auth/me/character', methods=['GET'])
@require_permission('character', 'read')
def get_my_character():
    user = g.current_user
    if not user.character_url:
        return jsonify({'error': 'character_url_not_set', 'message': 'Персонаж не привязан к аккаунту'}), 404

    data, status = _fetch_and_process(user, force=False)
    return jsonify(data), status


@character_bp.route('/api/auth/me/character/refresh', methods=['POST'])
@require_permission('character', 'write')
def refresh_my_character():
    user = g.current_user
    if not user.character_url:
        return jsonify({'error': 'character_url_not_set', 'message': 'Персонаж не привязан к аккаунту'}), 404

    data, status = _fetch_and_process(user, force=True)
    return jsonify(data), status
