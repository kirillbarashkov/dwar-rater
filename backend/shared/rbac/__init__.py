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

    # Deprecate orphaned permissions
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


def require_permission(feature: str, action: str):
    """Decorator to require a specific permission.

    Checks:
    1. If user.role == 'admin' → allowed
    2. user_permission override → use that level
    3. role_permission → use that level
    4. none → 403
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = g.get('current_user')
            if not user:
                return jsonify({'error': 'Требуется авторизация'}), 401

            if not user.is_active:
                return jsonify({'error': 'Аккаунт деактивирован'}), 403

            # Admin bypass
            if user.role == 'admin':
                return f(*args, **kwargs)

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
    """
    from shared.rbac.models import UserPermission, RolePermission, Permission as PermModel

    # Check individual override first
    perm = PermModel.query.filter_by(feature=feature, action=action).first()
    if not perm:
        return 'none'

    user_perm = UserPermission.query.filter_by(
        user_id=user.id, permission_id=perm.id
    ).first()
    if user_perm:
        return user_perm.level

    # Fall back to role permission
    role_perm = RolePermission.query.filter_by(
        role_id=user.role_obj.id if user.role_obj else None,
        permission_id=perm.id
    ).first()
    if role_perm:
        return role_perm.level

    return 'none'
