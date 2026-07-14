"""RBAC auto-sync: register permissions via @feature() decorator,
sync at startup, deprecate orphaned permissions.
"""

import json
from functools import wraps
from flask import request, jsonify, g

_registered_permissions = {}


class Permission:
    """Declarative permission definition for @feature() decorator."""

    def __init__(self, action: str, label: str, description: str = ''):
        self.action = action
        self.label = label
        self.description = description


def feature(feature_name: str, permissions: list[Permission]):
    """Decorator to register permissions for a feature.

    Usage:
        @feature('analyze', [
            Permission('read', 'Анализ персонажа', 'POST /api/analyze'),
            Permission('write', 'Принудительное обновление', 'force_refresh=true'),
        ])
        @analyze_bp.route('/api/analyze', methods=['POST'])
        def analyze():
            ...
    """
    def decorator(f):
        for perm in permissions:
            key = (feature_name, perm.action)
            _registered_permissions[key] = {
                'feature': feature_name,
                'action': perm.action,
                'label': perm.label,
                'description': perm.description,
            }
        return f
    return decorator


def register_feature(feature_name: str, permissions: list[Permission]):
    """Register permissions for a feature without using a decorator.

    Usage:
        analyze_bp = Blueprint('analyze', __name__)
        register_feature('analyze', [
            Permission('read', 'Анализ персонажа', 'POST /api/analyze'),
            Permission('write', 'Принудительное обновление', 'force_refresh=true'),
        ])
    """
    for perm in permissions:
        key = (feature_name, perm.action)
        _registered_permissions[key] = {
            'feature': feature_name,
            'action': perm.action,
            'label': perm.label,
            'description': perm.description,
        }


def get_registered_permissions():
    """Return all permissions registered via @feature() decorators."""
    return dict(_registered_permissions)


def sync_permissions(db):
    """Sync registered permissions with DB. Called at app startup.

    - Adds new permissions
    - Deprecates orphaned permissions (in DB but not registered)
    - Assigns default role_permissions for new permissions
    """
    from shared.rbac.models import Permission as PermModel, Role, RolePermission, AuditLog
    from shared.rbac.seed import DEFAULT_ROLE_PERMISSIONS

    registered = get_registered_permissions()
    in_db = {
        (p.feature, p.action): p
        for p in PermModel.query.all()
    }

    new_perms = set(registered.keys()) - set(in_db.keys())
    orphaned = set(in_db.keys()) - set(registered.keys())

    # Add new permissions
    for key in new_perms:
        data = registered[key]
        perm = PermModel(**data)
        db.session.add(perm)

    # Handle orphaned permissions (in DB but not registered via @feature)
    # Always deprecate — orphaned means the code no longer declares this permission.
    # Admin can delete deprecated permissions via DELETE /api/admin/permissions/deprecated.
    for key in orphaned:
        perm = in_db[key]
        if not perm.is_deprecated:
            perm.is_deprecated = True

    # Assign default role_permissions for new permissions
    # Use 'user' role defaults as template
    user_defaults = {
        (feat, act): lvl
        for role_name, feat, act, lvl in DEFAULT_ROLE_PERMISSIONS
        if role_name == 'user'
    }

    # Get role IDs
    roles = {r.name: r.id for r in Role.query.all()}

    for key in new_perms:
        feature_name, action = key
        perm = PermModel.query.filter_by(feature=feature_name, action=action).first()
        if not perm:
            continue

        default_level = user_defaults.get((feature_name, action), 'none')

        for role_name in ['admin', 'superuser', 'user', 'custom']:
            role_id = roles.get(role_name)
            if role_id is None:
                continue

            # Admin always gets full
            if role_name == 'admin':
                level = 'full'
            elif role_name == 'custom':
                level = 'none'
            else:
                level = default_level

            existing = RolePermission.query.filter_by(
                role_id=role_id, permission_id=perm.id
            ).first()
            if not existing:
                rp = RolePermission(role_id=role_id, permission_id=perm.id, level=level)
                db.session.add(rp)

    if new_perms or orphaned:
        db.session.flush()


def load_user_permissions(user) -> dict:
    """Load all permissions for a user into a flat dict.

    Uses 2 queries total (role perms + user overrides) instead of
    3 queries per permission check. Called once per request in session_auth.

    Returns: {f"{feature}:{action}": "full"|"read"|"none"}
    """
    from shared.models import db
    from shared.rbac.models import Permission as PermModel, UserPermission, RolePermission

    role_id = user.role_obj.id if user.role_obj else None

    # Query 1: all non-deprecated permissions with role level (LEFT JOIN)
    role_perms = (
        db.session.query(
            PermModel.id, PermModel.feature, PermModel.action, RolePermission.level
        )
        .outerjoin(RolePermission,
                   (RolePermission.permission_id == PermModel.id) &
                   (RolePermission.role_id == role_id))
        .filter(PermModel.is_deprecated == False)
        .all()
    )

    result = {}
    perm_id_to_key = {}
    for perm_id, feature, action, level in role_perms:
        key = f"{feature}:{action}"
        result[key] = level or 'none'
        perm_id_to_key[perm_id] = key

    # Query 2: individual user overrides (take precedence over role)
    user_overrides = (
        db.session.query(UserPermission.permission_id, UserPermission.level)
        .filter(UserPermission.user_id == user.id)
        .all()
    )
    for perm_id, level in user_overrides:
        key = perm_id_to_key.get(perm_id)
        if key:
            result[key] = level

    return result


def require_permission(feature: str, action: str):
    """Decorator to require a specific permission.

    Checks:
    1. If user is not active → 403
    2. user_permission override → use that level
    3. role_permission → use that level
    4. none → 403

    Note: admin role gets 'full' on all permissions via seed data,
    so it passes checks naturally — no hardcoded bypass needed.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = g.get('current_user')
            if not user:
                return jsonify({'error': 'Требуется авторизация'}), 401

            if not user.is_active:
                return jsonify({'error': 'Аккаунт деактивирован'}), 403

            level = get_user_permission(user, feature, action)
            if level == 'none':
                return jsonify({'error': 'Доступ запрещён'}), 403

            # 'read' level blocks write/delete/admin actions
            if level == 'read' and action in ('write', 'delete', 'admin'):
                return jsonify({'error': 'Недостаточно прав'}), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def get_user_permission(user, feature: str, action: str) -> str:
    """Get effective permission level for a user.

    Returns: 'full' | 'read' | 'none'

    Reads from g.user_perms cache (populated in session_auth before_request).
    Falls back to DB queries if cache not available (CLI / non-request context).
    """
    from flask import g

    cached = getattr(g, 'user_perms', None)
    if cached is not None:
        return cached.get(f"{feature}:{action}", 'none')

    # CLI / non-request context: query DB directly
    from shared.rbac.models import UserPermission, RolePermission, Permission as PermModel

    perm = PermModel.query.filter_by(feature=feature, action=action).first()
    if not perm:
        return 'none'

    user_perm = UserPermission.query.filter_by(
        user_id=user.id, permission_id=perm.id
    ).first()
    if user_perm:
        return user_perm.level

    role_perm = RolePermission.query.filter_by(
        role_id=user.role_obj.id if user.role_obj else None,
        permission_id=perm.id
    ).first()
    if role_perm:
        return role_perm.level

    return 'none'
