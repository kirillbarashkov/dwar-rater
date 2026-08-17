from flask import Blueprint, jsonify

from shared.utils.version import get_version_info, read_release_notes

version_bp = Blueprint('version', __name__)


@version_bp.route('/api/version', methods=['GET'])
def version_info():
    """Public endpoint — version info (env-first) + release notes."""
    info = get_version_info()
    info['release_notes'] = read_release_notes()
    return jsonify(info)
