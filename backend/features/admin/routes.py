"""Admin API endpoints for user management, permissions, and audit log."""

import bcrypt
import os
import subprocess
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g, send_file
from shared.models import db
from shared.models.user import User
from shared.models.clan_info import ClanMemberInfo
from shared.rbac.models import Role, Permission, RolePermission, UserPermission, AuditLog
from shared.rbac import require_permission, feature, Permission as PermDef
from shared.utils.transliterate import ensure_unique_username

DEFAULT_PASSWORD = 'ChangeMe123!'
BACKUP_DIR = os.environ.get('BACKUP_DIR', '/backups')

admin_bp = Blueprint('admin', __name__)

from shared.rbac import register_feature
register_feature('admin', [
    PermDef('read', 'Просмотр админки', 'GET /api/admin/*'),
    PermDef('write', 'Управление пользователями и ролями', 'POST/PUT/DELETE /api/admin/*'),
    PermDef('admin', 'Просмотр audit log', 'GET /api/admin/audit'),
])



def _audit(action, target_type=None, target_id=None, old=None, new=None):
    """Log an audit entry for the current admin user."""
    entry = AuditLog(
        user_id=g.current_user.id if g.current_user else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        old_value=old if old is None else (old if isinstance(old, str) else str(old)),
        new_value=new if new is None else (new if isinstance(new, str) else str(new)),
        ip_address=request.remote_addr,
    )
    db.session.add(entry)


# ── Users ───────────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/users', methods=['GET'])
@require_permission('admin', 'read')
def list_users():
    role_filter = request.args.get('role')
    active_filter = request.args.get('active')

    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    if active_filter is not None:
        query = query.filter_by(is_active=active_filter.lower() == 'true')

    users = query.order_by(User.username).all()

    return jsonify({
        'users': [u.to_dict() for u in users],
        'total': len(users),
    })


@admin_bp.route('/api/admin/users', methods=['POST'])
@require_permission('admin', 'write')
def create_user():
    data = request.json
    if not data or 'username' not in data:
        return jsonify({'error': 'username обязателен'}), 400

    password = data.get('password', DEFAULT_PASSWORD)
    if len(password) < 8:
        return jsonify({'error': 'Пароль должен быть не менее 8 символов'}), 400

    role = data.get('role', 'user')
    if role not in ('admin', 'superuser', 'user', 'custom'):
        return jsonify({'error': 'Недопустимая роль'}), 400

    existing = User.query.filter_by(username=data['username']).first()
    if existing:
        return jsonify({'error': 'Пользователь уже существует'}), 400

    user = User(
        username=data['username'],
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        role=role,
        must_change_password=True,
    )
    db.session.add(user)
    db.session.flush()

    _audit('user_create', target_type='user', target_id=user.id, new={'username': user.username, 'role': role})
    db.session.commit()

    return jsonify(user.to_dict()), 201


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@require_permission('admin', 'write')
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json

    old_role = user.role
    old_active = user.is_active

    if 'role' in data:
        if data['role'] not in ('admin', 'superuser', 'user', 'custom'):
            return jsonify({'error': 'Недопустимая роль'}), 400
        user.role = data['role']

    if 'is_active' in data:
        user.is_active = bool(data['is_active'])

    if 'password' in data:
        if len(data['password']) < 8:
            return jsonify({'error': 'Пароль должен быть не менее 8 символов'}), 400
        user.password_hash = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
        user.must_change_password = True

    db.session.commit()

    changes = {}
    if old_role != user.role:
        changes['role'] = {'old': old_role, 'new': user.role}
    if old_active != user.is_active:
        changes['is_active'] = {'old': old_active, 'new': user.is_active}

    if changes:
        _audit('user_update', target_type='user', target_id=user.id, old=old_role, new=user.role)

    return jsonify(user.to_dict())


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_permission('admin', 'write')
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin' and User.query.filter_by(role='admin', is_active=True).count() <= 1:
        return jsonify({'error': 'Нельзя деактивировать последнего админа'}), 400

    user.is_active = False
    db.session.commit()

    _audit('user_deactivate', target_type='user', target_id=user.id, old='active', new='inactive')

    return jsonify({'status': 'deactivated', 'user': user.to_dict()})


# ── Sync from clan ──────────────────────────────────────────────────────

@admin_bp.route('/api/admin/users/sync', methods=['POST'])
@require_permission('admin', 'write')
def sync_users_from_clan():
    """Sync users from ClanMemberInfo. Creates new users for active members."""
    members = ClanMemberInfo.query.filter_by(is_deleted=False).all()

    existing_usernames = {u.username for u in User.query.all()}
    created = 0
    updated = 0
    skipped = 0
    errors = []

    for member in members:
        try:
            username = ensure_unique_username(member.nick, existing_usernames)

            user = User.query.filter_by(username=username).first()
            if user:
                # Update existing user
                if not user.is_active:
                    user.is_active = True
                    updated += 1
                else:
                    skipped += 1
            else:
                # Create new user
                user = User(
                    username=username,
                    password_hash=bcrypt.hashpw(DEFAULT_PASSWORD.encode(), bcrypt.gensalt()).decode(),
                    role='user',
                    must_change_password=True,
                    is_active=True,
                )
                db.session.add(user)
                existing_usernames.add(username)
                created += 1

                _audit('user_sync_create', target_type='user', target_id=None,
                       new={'username': username, 'nick': member.nick})
        except Exception as e:
            errors.append(f'{member.nick}: {str(e)}')

    db.session.commit()

    return jsonify({
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'errors': errors,
    })


# ── Permissions ─────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/permissions', methods=['GET'])
@require_permission('admin', 'read')
def get_permissions():
    """Get all permissions with role levels."""
    perms = Permission.query.filter_by(is_deprecated=False).order_by(Permission.feature, Permission.action).all()
    roles = Role.query.all()

    result = []
    for perm in perms:
        entry = {
            'id': perm.id,
            'feature': perm.feature,
            'action': perm.action,
            'label': perm.label,
            'description': perm.description,
            'roles': {},
        }
        for role in roles:
            rp = RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first()
            entry['roles'][role.name] = rp.level if rp else 'none'
        result.append(entry)

    return jsonify({'permissions': result, 'roles': [r.to_dict() for r in roles]})


@admin_bp.route('/api/admin/permissions/role/<int:role_id>', methods=['PUT'])
@require_permission('admin', 'write')
def update_role_permissions(role_id):
    """Update permissions for a role."""
    role = Role.query.get_or_404(role_id)
    if role.is_system and role.name == 'admin':
        return jsonify({'error': 'Нельзя изменить права системной роли admin'}), 400

    data = request.json
    if not data or 'permissions' not in data:
        return jsonify({'error': 'permissions обязательны'}), 400

    updated = 0
    for perm_id, level in data['permissions'].items():
        if level not in ('full', 'read', 'none'):
            return jsonify({'error': f'Недопустимый уровень: {level}'}), 400

        rp = RolePermission.query.filter_by(role_id=role_id, permission_id=int(perm_id)).first()
        if rp:
            if rp.level != level:
                rp.level = level
                updated += 1
        else:
            rp = RolePermission(role_id=role_id, permission_id=int(perm_id), level=level)
            db.session.add(rp)
            updated += 1

    db.session.commit()

    _audit('role_permissions_update', target_type='role', target_id=role_id, new=data['permissions'])

    return jsonify({'status': 'updated', 'count': updated})


@admin_bp.route('/api/admin/permissions/user/<int:user_id>', methods=['GET'])
@require_permission('admin', 'read')
def get_user_permissions(user_id):
    """Get individual permissions for a user."""
    user = User.query.get_or_404(user_id)
    perms = Permission.query.filter_by(is_deprecated=False).order_by(Permission.feature, Permission.action).all()

    result = []
    for perm in perms:
        up = UserPermission.query.filter_by(user_id=user_id, permission_id=perm.id).first()
        result.append({
            'id': perm.id,
            'feature': perm.feature,
            'action': perm.action,
            'label': perm.label,
            'level': up.level if up else 'none',
        })

    return jsonify({'user': user.to_dict(), 'permissions': result})


@admin_bp.route('/api/admin/permissions/user/<int:user_id>', methods=['PUT'])
@require_permission('admin', 'write')
def update_user_permissions(user_id):
    """Update individual permissions for a user."""
    user = User.query.get_or_404(user_id)
    data = request.json
    if not data or 'permissions' not in data:
        return jsonify({'error': 'permissions обязательны'}), 400

    updated = 0
    for perm_id, level in data['permissions'].items():
        if level not in ('full', 'read', 'none'):
            return jsonify({'error': f'Недопустимый уровень: {level}'}), 400

        up = UserPermission.query.filter_by(user_id=user_id, permission_id=int(perm_id)).first()
        if up:
            if up.level != level:
                up.level = level
                updated += 1
        else:
            up = UserPermission(user_id=user_id, permission_id=int(perm_id), level=level)
            db.session.add(up)
            updated += 1

    db.session.commit()

    _audit('user_permissions_update', target_type='user', target_id=user_id, new=data['permissions'])

    return jsonify({'status': 'updated', 'count': updated})


# ── Audit Log ───────────────────────────────────────────────────────────

@admin_bp.route('/api/admin/audit', methods=['GET'])
@require_permission('admin', 'admin')
def get_audit_log():
    """Get audit log with filters."""
    user_filter = request.args.get('user_id', type=int)
    action_filter = request.args.get('action')
    target_type_filter = request.args.get('target_type')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = AuditLog.query.outerjoin(User, AuditLog.user_id == User.id)

    if user_filter:
        query = query.filter(AuditLog.user_id == user_filter)
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if target_type_filter:
        query = query.filter(AuditLog.target_type == target_type_filter)

    query = query.order_by(AuditLog.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
        'entries': [e.to_dict() for e in pagination.items],
    })


# ── Features Reference ──────────────────────────────────────────────────

@admin_bp.route('/api/admin/features', methods=['GET'])
@require_permission('admin', 'read')
def get_features():
    """Get reference list of all features with descriptions."""
    perms = Permission.query.filter_by(is_deprecated=False).order_by(Permission.feature, Permission.action).all()

    features = {}
    for perm in perms:
        if perm.feature not in features:
            features[perm.feature] = {'feature': perm.feature, 'actions': []}
        features[perm.feature]['actions'].append({
            'action': perm.action,
            'label': perm.label,
            'description': perm.description,
        })

    return jsonify({'features': list(features.values())})


# ── Deprecated Permissions Cleanup ──────────────────────────────────────

@admin_bp.route('/api/admin/permissions/deprecated', methods=['DELETE'])
@require_permission('admin', 'write')
def delete_deprecated_permissions():
    """Delete all deprecated permissions."""
    deprecated = Permission.query.filter_by(is_deprecated=True).all()
    count = len(deprecated)

    for perm in deprecated:
        # Delete associated role_permissions and user_permissions
        RolePermission.query.filter_by(permission_id=perm.id).delete()
        UserPermission.query.filter_by(permission_id=perm.id).delete()
        db.session.delete(perm)

    db.session.commit()

    _audit('deprecated_permissions_deleted', target_type='permission', new={'count': count})

    return jsonify({'status': 'deleted', 'count': count})


# ── Database Backups ────────────────────────────────────────────────────

def _get_backup_info(filepath):
    """Get backup file metadata."""
    stat = os.stat(filepath)
    return {
        'filename': os.path.basename(filepath),
        'size': stat.st_size,
        'size_human': _human_size(stat.st_size),
        'created_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def _human_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


@admin_bp.route('/api/admin/backups', methods=['GET'])
@require_permission('admin', 'read')
def list_backups():
    """List all database backups."""
    if not os.path.exists(BACKUP_DIR):
        return jsonify({'backups': [], 'total': 0, 'total_size': 0})

    backups = []
    total_size = 0
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.startswith('dwar_rater_backup_') and f.endswith('.sql.gz'):
            filepath = os.path.join(BACKUP_DIR, f)
            info = _get_backup_info(filepath)
            backups.append(info)
            total_size += info['size']

    return jsonify({
        'backups': backups,
        'total': len(backups),
        'total_size': _human_size(total_size),
        'schedule': 'Daily at 03:00 UTC',
        'retention': 'No automatic deletion',
    })


@admin_bp.route('/api/admin/backups', methods=['POST'])
@require_permission('admin', 'write')
def create_backup():
    """Trigger manual database backup."""
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"dwar_rater_backup_{timestamp}.sql.gz"
    filepath = os.path.join(BACKUP_DIR, filename)

    os.makedirs(BACKUP_DIR, exist_ok=True)

    env = os.environ.copy()
    env['PGPASSWORD'] = os.environ.get('POSTGRES_PASSWORD', 'change-me-in-production')

    cmd = [
        'pg_dump',
        '-h', os.environ.get('POSTGRES_HOST', 'postgres'),
        '-p', os.environ.get('POSTGRES_PORT', '5432'),
        '-U', os.environ.get('POSTGRES_USER', 'dwar'),
        '-d', os.environ.get('POSTGRES_DB', 'dwar_rater'),
        '--no-owner', '--no-acl'
    ]

    try:
        with open(filepath, 'wb') as f:
            result = subprocess.run(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )
            if result.returncode != 0:
                os.remove(filepath)
                return jsonify({'error': f'Backup failed: {result.stderr.decode()}'}), 500

            # Compress
            import gzip
            with gzip.open(filepath + '.tmp', 'wb') as gz:
                gz.write(result.stdout)
            os.rename(filepath + '.tmp', filepath)

        info = _get_backup_info(filepath)
        _audit('backup_created', target_type='backup', new={'filename': filename, 'size': info['size']})

        return jsonify({'status': 'created', 'backup': info})
    except subprocess.TimeoutExpired:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': 'Backup timed out'}), 504
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/admin/backups/<filename>', methods=['DELETE'])
@require_permission('admin', 'write')
def delete_backup(filename):
    """Delete a specific backup file."""
    if not filename.startswith('dwar_rater_backup_') or not filename.endswith('.sql.gz'):
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Backup not found'}), 404

    os.remove(filepath)
    _audit('backup_deleted', target_type='backup', old={'filename': filename})

    return jsonify({'status': 'deleted', 'filename': filename})


@admin_bp.route('/api/admin/backups/<filename>/download', methods=['GET'])
@require_permission('admin', 'read')
def download_backup(filename):
    """Download a backup file."""
    if not filename.startswith('dwar_rater_backup_') or not filename.endswith('.sql.gz'):
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Backup not found'}), 404

    return send_file(filepath, as_attachment=True, download_name=filename)


@admin_bp.route('/api/admin/backups/<filename>/restore', methods=['POST'])
@require_permission('admin', 'admin')
def restore_backup(filename):
    """Restore database from a backup file."""
    if not filename.startswith('dwar_rater_backup_') or not filename.endswith('.sql.gz'):
        return jsonify({'error': 'Invalid filename'}), 400

    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Backup not found'}), 404

    env = os.environ.copy()
    env['PGPASSWORD'] = os.environ.get('POSTGRES_PASSWORD', 'change-me-in-production')

    cmd = [
        'psql',
        '-h', os.environ.get('POSTGRES_HOST', 'postgres'),
        '-p', os.environ.get('POSTGRES_PORT', '5432'),
        '-U', os.environ.get('POSTGRES_USER', 'dwar'),
        '-d', os.environ.get('POSTGRES_DB', 'dwar_rater'),
    ]

    try:
        import gzip
        with gzip.open(filepath, 'rb') as gz:
            result = subprocess.run(
                cmd,
                env=env,
                stdin=gz,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600
            )
            if result.returncode != 0:
                return jsonify({'error': f'Restore failed: {result.stderr.decode()}'}), 500

        _audit('backup_restored', target_type='backup', new={'filename': filename})

        return jsonify({'status': 'restored', 'filename': filename})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Restore timed out'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500
