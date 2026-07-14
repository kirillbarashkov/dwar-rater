"""RBAC seed data: roles, permissions, default role_permissions."""

ROLES = [
    {'name': 'admin', 'label': 'Администратор', 'is_system': True},
    {'name': 'superuser', 'label': 'Суперпользователь', 'is_system': False},
    {'name': 'user', 'label': 'Пользователь', 'is_system': True},
    {'name': 'custom', 'label': 'Пользовательский', 'is_system': False},
]

PERMISSIONS = [
    # analyze
    ('analyze', 'read', 'Анализ персонажа', 'POST /api/analyze — парсинг персонажа'),
    ('analyze', 'write', 'Принудительное обновление', 'force_refresh=true'),
    # snapshots
    ('snapshots', 'read', 'Просмотр снапшотов', 'GET /api/snapshots'),
    ('snapshots', 'write', 'Сохранение снапшота', 'POST /api/save-snapshot'),
    ('snapshots', 'delete', 'Удаление снапшота', 'DELETE /api/snapshots/:id'),
    ('snapshots', 'admin', 'Очистка кэша', 'DELETE /api/cache'),
    # clans
    ('clans', 'read', 'Просмотр кланов', 'GET /api/clans'),
    ('clans', 'write', 'Управление кланами', 'POST/DELETE /api/clans/*'),
    ('clans', 'admin', 'Управление чатом', 'Chat rooms/messages admin'),
    # clan_info
    ('clan_info', 'read', 'Просмотр инфо/состава/казны', 'GET /api/clan/*'),
    ('clan_info', 'write', 'Редактирование участников', 'POST/PUT/DELETE /api/clan/*/members/*'),
    ('clan_info', 'admin', 'Импорт/экспорт казны, бэкапы', 'Treasury import/export/backup admin'),
    # scenarios
    ('scenarios', 'read', 'Просмотр сценариев', 'GET /api/scenarios'),
    ('scenarios', 'write', 'Создание/редактирование сценариев', 'POST/PUT/DELETE /api/scenarios/*'),
    # tracks
    ('tracks', 'read', 'Просмотр треков', 'GET /api/tracks'),
    ('tracks', 'write', 'Генерация/обновление треков', 'POST/PUT/DELETE /api/tracks/*'),
    # compare
    ('compare', 'read', 'Просмотр сравнений', 'GET /api/compare'),
    ('compare', 'write', 'Управление сравнениями', 'POST/DELETE /api/compare/*'),
    # closed_profiles
    ('closed_profiles', 'read', 'Просмотр закрытых профилей', 'GET /api/closed-profiles'),
    ('closed_profiles', 'write', 'Добавление/удаление/проверка', 'POST/PUT/DELETE /api/closed-profiles/*'),
    # admin
    ('admin', 'read', 'Просмотр админки', 'GET /api/admin/*'),
    ('admin', 'write', 'Управление пользователями и ролями', 'POST/PUT/DELETE /api/admin/*'),
    ('admin', 'admin', 'Просмотр audit log', 'GET /api/admin/audit'),
]

# Default role_permissions: (role_name, feature, action, level)
DEFAULT_ROLE_PERMISSIONS = [
    # admin: everything full
    ('admin', 'analyze', 'read', 'full'),
    ('admin', 'analyze', 'write', 'full'),
    ('admin', 'snapshots', 'read', 'full'),
    ('admin', 'snapshots', 'write', 'full'),
    ('admin', 'snapshots', 'delete', 'full'),
    ('admin', 'snapshots', 'admin', 'full'),
    ('admin', 'clans', 'read', 'full'),
    ('admin', 'clans', 'write', 'full'),
    ('admin', 'clans', 'admin', 'full'),
    ('admin', 'clan_info', 'read', 'full'),
    ('admin', 'clan_info', 'write', 'full'),
    ('admin', 'clan_info', 'admin', 'full'),
    ('admin', 'scenarios', 'read', 'full'),
    ('admin', 'scenarios', 'write', 'full'),
    ('admin', 'tracks', 'read', 'full'),
    ('admin', 'tracks', 'write', 'full'),
    ('admin', 'compare', 'read', 'full'),
    ('admin', 'compare', 'write', 'full'),
    ('admin', 'closed_profiles', 'read', 'full'),
    ('admin', 'closed_profiles', 'write', 'full'),
    ('admin', 'admin', 'read', 'full'),
    ('admin', 'admin', 'write', 'full'),
    ('admin', 'admin', 'admin', 'full'),

    # superuser: everything full EXCEPT admin.*
    ('superuser', 'analyze', 'read', 'full'),
    ('superuser', 'analyze', 'write', 'full'),
    ('superuser', 'snapshots', 'read', 'full'),
    ('superuser', 'snapshots', 'write', 'full'),
    ('superuser', 'snapshots', 'delete', 'full'),
    ('superuser', 'snapshots', 'admin', 'full'),
    ('superuser', 'clans', 'read', 'full'),
    ('superuser', 'clans', 'write', 'full'),
    ('superuser', 'clans', 'admin', 'full'),
    ('superuser', 'clan_info', 'read', 'full'),
    ('superuser', 'clan_info', 'write', 'full'),
    ('superuser', 'clan_info', 'admin', 'none'),
    ('superuser', 'scenarios', 'read', 'full'),
    ('superuser', 'scenarios', 'write', 'full'),
    ('superuser', 'tracks', 'read', 'full'),
    ('superuser', 'tracks', 'write', 'full'),
    ('superuser', 'compare', 'read', 'full'),
    ('superuser', 'compare', 'write', 'full'),
    ('superuser', 'closed_profiles', 'read', 'full'),
    ('superuser', 'closed_profiles', 'write', 'full'),
    ('superuser', 'admin', 'read', 'none'),
    ('superuser', 'admin', 'write', 'none'),
    ('superuser', 'admin', 'admin', 'none'),

    # user: read on everything, write on select features
    ('user', 'analyze', 'read', 'full'),
    ('user', 'analyze', 'write', 'full'),
    ('user', 'snapshots', 'read', 'full'),
    ('user', 'snapshots', 'write', 'full'),
    ('user', 'snapshots', 'delete', 'none'),
    ('user', 'snapshots', 'admin', 'none'),
    ('user', 'clans', 'read', 'full'),
    ('user', 'clans', 'write', 'none'),
    ('user', 'clans', 'admin', 'none'),
    ('user', 'clan_info', 'read', 'full'),
    ('user', 'clan_info', 'write', 'none'),
    ('user', 'clan_info', 'admin', 'none'),
    ('user', 'scenarios', 'read', 'full'),
    ('user', 'scenarios', 'write', 'none'),
    ('user', 'tracks', 'read', 'full'),
    ('user', 'tracks', 'write', 'full'),
    ('user', 'compare', 'read', 'full'),
    ('user', 'compare', 'write', 'full'),
    ('user', 'closed_profiles', 'read', 'full'),
    ('user', 'closed_profiles', 'write', 'full'),
    ('user', 'admin', 'read', 'none'),
    ('user', 'admin', 'write', 'none'),
    ('user', 'admin', 'admin', 'none'),

    # custom: everything none by default (admin assigns individually)
]


def seed_roles(db, Role):
    """Insert roles if they don't exist. Handles concurrent seeding."""
    from sqlalchemy.exc import IntegrityError
    for role_data in ROLES:
        existing = Role.query.filter_by(name=role_data['name']).first()
        if not existing:
            role = Role(**role_data)
            db.session.add(role)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()


def seed_permissions(db, Permission):
    """Insert permissions if they don't exist. Handles concurrent seeding."""
    from sqlalchemy.exc import IntegrityError
    for feature, action, label, description in PERMISSIONS:
        existing = Permission.query.filter_by(feature=feature, action=action).first()
        if not existing:
            perm = Permission(
                feature=feature, action=action, label=label, description=description
            )
            db.session.add(perm)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()


def seed_role_permissions(db, Role, Permission, RolePermission):
    """Insert default role_permissions if they don't exist. Handles concurrent seeding."""
    from sqlalchemy.exc import IntegrityError
    for role_name, feature, action, level in DEFAULT_ROLE_PERMISSIONS:
        role = Role.query.filter_by(name=role_name).first()
        perm = Permission.query.filter_by(feature=feature, action=action).first()
        if role and perm:
            existing = RolePermission.query.filter_by(
                role_id=role.id, permission_id=perm.id
            ).first()
            if not existing:
                rp = RolePermission(role_id=role.id, permission_id=perm.id, level=level)
                db.session.add(rp)
                try:
                    db.session.flush()
                except IntegrityError:
                    db.session.rollback()


def seed_all(db):
    """Run all seed operations including admin user creation."""
    import bcrypt
    import os
    import logging
    import psycopg2
    from shared.rbac.models import Role, Permission, RolePermission
    from shared.models.user import User

    logger = logging.getLogger('data_operations')

    seed_roles(db, Role)
    db.session.flush()
    logger.info('RBAC: roles seeded')

    seed_permissions(db, Permission)
    db.session.flush()
    logger.info('RBAC: permissions seeded')

    seed_role_permissions(db, Role, Permission, RolePermission)
    logger.info('RBAC: role_permissions seeded')

    # Commit seed data first
    db.session.commit()
    logger.info('RBAC: seed data committed')

    # Create admin user using DIRECT psycopg2 with autocommit
    # This bypasses all SQLAlchemy session issues
    admin_user = os.environ.get('ADMIN_USER', 'admin')
    admin_pass = os.environ.get('ADMIN_PASS', 'change-me-in-production')

    try:
        db_url = os.environ.get('DATABASE_URL', 'postgresql://dwar:change-me-in-production@postgres:5432/dwar_rater')
        parts = db_url.replace('postgresql://', '').split('@')
        user_pass = parts[0].split(':')
        host_db = parts[1].split('/')
        host_port = host_db[0].split(':')

        conn = psycopg2.connect(
            host=host_port[0],
            port=int(host_port[1]) if len(host_port) > 1 else 5432,
            dbname=host_db[1],
            user=user_pass[0],
            password=user_pass[1]
        )
        conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM app_user WHERE username = %s", (admin_user,))
            if cur.fetchone():
                logger.info(f'RBAC: admin user already exists: {admin_user}')
            else:
                h = bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()).decode()
                cur.execute(
                    "INSERT INTO app_user (username, password_hash, role, is_active, must_change_password, created_at) VALUES (%s, %s, 'admin', true, false, NOW())",
                    (admin_user, h)
                )
                # autocommit=True means INSERT is immediately committed
                cur.execute("SELECT id, username FROM app_user WHERE username = %s", (admin_user,))
                row = cur.fetchone()
                if row:
                    logger.info(f'RBAC: admin user created via psycopg2: id={row[0]}, username={row[1]}')
                else:
                    logger.error('RBAC: admin INSERT succeeded but SELECT returned nothing')

        conn.close()
    except Exception as e:
        logger.error(f'RBAC: failed to create admin user via psycopg2: {e}')
