from flask import Blueprint, request, jsonify, g
from middleware.auth import require_auth
from services.parser import fetch_character_page, parse_character
from services.processor import process_character
from services.cache_service import get_cached_character, save_character_cache, create_snapshot, log_analysis
from utils.validators import validate_dwar_url
from urllib.parse import urlparse, parse_qs


analyze_bp = Blueprint('analyze', __name__)


@analyze_bp.route('/api/analyze', methods=['POST'])
@require_auth
def analyze():
    data = request.json
    url = data.get('url', '').strip()

    valid, error = validate_dwar_url(url)
    if not valid:
        return jsonify({'error': error}), 400

    if not url.startswith('http'):
        nick = url
        if 'nick=' in nick:
            nick = nick.split('nick=')[1].split('&')[0]
        url = f'https://w1.dwar.ru/user_info.php?nick={nick}'
    else:
        nick = parse_qs(urlparse(url).query).get('nick', [''])[0]

    cached = get_cached_character(nick)
    if cached:
        user_id = g.current_user.id if g.current_user else None
        log_analysis(user_id, nick, url)
        return jsonify(process_character(cached))

    try:
        html, session = fetch_character_page(url)
        raw = parse_character(html, session=session, nick=nick)

        save_character_cache(nick, raw)

        processed = process_character(raw)
        user_id = g.current_user.id if g.current_user else None
        snapshot_id = create_snapshot(processed, user_id=user_id)
        log_analysis(user_id, nick, url, snapshot_id=snapshot_id)

        return jsonify(processed)
    except Exception as e:
        error_msg = str(e)
        if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
            return jsonify({'error': 'Таймаут запроса к серверу dwar.ru'}), 504
        if 'request' in error_msg.lower():
            return jsonify({'error': f'Ошибка загрузки страницы: {error_msg}'}), 500
        return jsonify({'error': f'Ошибка обработки: {error_msg}'}), 500