from flask import Blueprint, request, jsonify, g
from shared.rbac import require_permission, feature, Permission as PermDef
from shared.services.analyze_service import analyze_character_url, AnalyzeError


analyze_bp = Blueprint('analyze', __name__)

from shared.rbac import register_feature
register_feature('analyze', [
    PermDef('read', 'Анализ персонажа', 'POST /api/analyze — парсинг персонажа'),
    PermDef('write', 'Принудительное обновление', 'force_refresh=true в POST /api/analyze'),
])


@analyze_bp.route('/api/analyze', methods=['POST'])
@require_permission('analyze', 'read')
def analyze():
    data = request.json
    url = data.get('url', '').strip()
    force_refresh = data.get('force_refresh', False)

    if force_refresh:
        from shared.rbac import get_user_permission
        level = get_user_permission(g.current_user, 'analyze', 'write')
        if level == 'none':
            return jsonify({'error': 'Недостаточно прав'}), 403

    try:
        processed = analyze_character_url(url, force_refresh=force_refresh,
                                          user=g.current_user)
        return jsonify(processed)
    except AnalyzeError as e:
        return jsonify({'error': str(e)}), e.status_code
