"""Export API endpoints."""

import json
from flask import Blueprint, request, jsonify, g, Response
from shared.rbac import require_permission, feature, Permission as PermDef
from shared.models.character_snapshot import CharacterSnapshot
from shared.services.exporter import export_to_html, export_to_markdown, export_to_pdf

export_bp = Blueprint('export', __name__)

VALID_FORMATS = {'html', 'markdown', 'pdf'}
VALID_SECTIONS = {
    'identity', 'combat_stats', 'characteristics', 'equipment',
    'effects', 'medals', 'records', 'professions', 'additional',
}

CONTENT_TYPES = {
    'html': 'text/html; charset=utf-8',
    'markdown': 'text/markdown; charset=utf-8',
    'pdf': 'application/pdf',
}

FILE_EXTENSIONS = {
    'html': 'html',
    'markdown': 'md',
    'pdf': 'pdf',
}


@feature('export', [
    PermDef('read', 'Экспорт аналитики', 'POST /api/export/character'),
])
@export_bp.route('/api/export/character', methods=['POST'])
@require_permission('analyze', 'read')
def export_character():
    """Export character analysis to HTML, Markdown, or PDF."""
    data = request.json
    if not data:
        return jsonify({'error': 'Тело запроса обязательно'}), 400

    fmt = data.get('format', 'html').lower()
    if fmt not in VALID_FORMATS:
        return jsonify({'error': f'Недопустимый формат. Доступные: {", ".join(VALID_FORMATS)}'}), 400

    sections = data.get('sections', [])
    if not sections:
        return jsonify({'error': 'Выберите хотя бы один раздел'}), 400

    invalid = set(sections) - VALID_SECTIONS
    if invalid:
        return jsonify({'error': f'Недопустимые разделы: {", ".join(invalid)}'}), 400

    # Get analysis data
    snapshot_id = data.get('snapshot_id')
    if snapshot_id:
        # Get from snapshot
        user = g.current_user
        snapshot = CharacterSnapshot.query.get(snapshot_id)
        if not snapshot:
            return jsonify({'error': 'Слепок не найден'}), 404
        if user.role != 'admin' and snapshot.user_id != user.id:
            return jsonify({'error': 'Доступ запрещён'}), 403
        analysis_data = json.loads(snapshot.snapshot_data)
    else:
        # Use last analysis from session/cache
        # For now, require snapshot_id — frontend should pass the current analysis data
        # Alternatively, we can accept the full data in the request
        raw_data = data.get('data')
        if not raw_data:
            return jsonify({'error': 'Укажите snapshot_id или передайте данные анализа в поле data'}), 400
        analysis_data = raw_data

    # Generate export
    page_format = data.get('page_format', 'landscape')
    try:
        if fmt == 'html':
            content = export_to_html(analysis_data, sections, page_format)
        elif fmt == 'markdown':
            content = export_to_markdown(analysis_data, sections, page_format)
        elif fmt == 'pdf':
            content = export_to_pdf(analysis_data, sections, page_format)
    except Exception as e:
        return jsonify({'error': f'Ошибка генерации: {str(e)}'}), 500

    # Determine filename
    name = analysis_data.get('name', 'character')
    # Sanitize filename - use ASCII only for Content-Disposition
    safe_name = ''.join(c for c in name if c.isascii() and (c.isalnum() or c in ' _-'))[:50] or 'character'
    safe_name = safe_name.replace(' ', '_')
    ext = FILE_EXTENSIONS[fmt]
    filename = f'{safe_name}_export.{ext}'

    # Return file
    return Response(content, mimetype=CONTENT_TYPES[fmt],
                   headers={'Content-Disposition': f'attachment; filename="{filename}"'})
