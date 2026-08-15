from flask import Blueprint, jsonify

from shared.utils.version import get_version_info

version_bp = Blueprint('version', __name__)


@version_bp.route('/api/version', methods=['GET'])
def version_info():
    """Public endpoint — returns current version info (env-first)."""
    return jsonify(get_version_info())
