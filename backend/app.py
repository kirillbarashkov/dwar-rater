import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

import bcrypt
from flask import Flask, request, jsonify, abort, g
from flask import render_template
from flask_cors import CORS

from config import Config
from models import db
from models.user import User
from models.compare_character import CompareCharacter
from middleware.rate_limiter import check_rate_limit
from middleware.security import add_security_headers


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, 'static'),
        template_folder=os.path.join(BASE_DIR, 'templates'),
    )
    app.config.from_object(Config)
    
    cors = CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS, "supports_credentials": True}})

    db.init_app(app)

    from routes.auth import auth_bp
    from routes.analyze import analyze_bp
    from routes.snapshots import snapshots_bp
    from routes.health import health_bp
    from routes.scenarios import scenarios_bp
    from routes.tracks import tracks_bp
    from routes.clans import clans_bp
    from routes.clan_info import clan_info_bp
    from routes.compare import compare_bp
    from routes.closed_profiles import closed_profiles_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(snapshots_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(scenarios_bp)
    app.register_blueprint(tracks_bp)
    app.register_blueprint(clans_bp)
    app.register_blueprint(clan_info_bp)
    app.register_blueprint(compare_bp)
    app.register_blueprint(closed_profiles_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.before_request
    def security_checks():
        if request.path == '/api/login' or request.path == '/' or request.path.startswith('/static/'):
            return
        if request.method == 'OPTIONS':
            return
        if not check_rate_limit(Config.RATE_LIMIT_MAX, Config.RATE_LIMIT_WINDOW):
            response = jsonify({'error': 'Слишком много запросов. Подождите.'})
            response.status_code = 429
            return response
        if request.method == 'POST':
            content_type = request.content_type or ''
            if 'application/json' not in content_type:
                abort(415)

    @app.after_request
    def after_request(response):
        return add_security_headers(response)

    with app.app_context():
        from services.data_logger import data_logger
        import logging

        instance_dir = os.path.join(BASE_DIR, 'backend', 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        data_logger.info(f'Instance directory: {instance_dir}')

        db_path = db.engine.url.database
        db_exists = os.path.exists(db_path) if db_path else False
        db_size = os.path.getsize(db_path) if db_path and db_exists else 0

        data_logger.info('=== APPLICATION STARTUP ===')
        data_logger.info(f'Database path: {os.path.abspath(db_path) if db_path else "unknown"}')
        data_logger.info(f'Database exists: {db_exists}')
        data_logger.info(f'Database size: {db_size / 1024 / 1024:.2f} MB')
        data_logger.info(f'DATABASE_URL: {Config.DATABASE_URL}')

        try:
            import fcntl
            _has_fcntl = True
        except ImportError:
            _has_fcntl = False

        if _has_fcntl:
            lock_path = os.path.join(instance_dir, '.migration.lock')
            migration_lock = open(lock_path, 'w')
            try:
                fcntl.flock(migration_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                data_logger.info('Alembic: another worker is running migrations, waiting...')
                import time
                time.sleep(3)
                migration_lock.close()
                migration_lock = None

            if migration_lock:
                try:
                    from alembic.config import Config as AlembicConfig
                    from alembic import command
                    from alembic.script import ScriptDirectory
                    from alembic.runtime.migration import MigrationContext
                    alembic_ini = os.path.join(BASE_DIR, 'backend', 'alembic.ini')
                    if not os.path.exists(alembic_ini):
                        alembic_ini = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alembic.ini')
                    alembic_cfg = AlembicConfig(alembic_ini)
                    alembic_cfg.set_main_option('sqlalchemy.url', Config.DATABASE_URL)

                    with db.engine.connect() as conn:
                        context = MigrationContext.configure(conn)
                        current_rev = context.get_current_revision()
                        script = ScriptDirectory.from_config(alembic_cfg)
                        head_rev = script.get_current_head()
                        if current_rev != head_rev:
                            command.upgrade(alembic_cfg, 'head')
                            data_logger.info(f'Alembic: upgraded {current_rev} -> {head_rev}')
                        else:
                            data_logger.info(f'Alembic: already at revision {head_rev}')
                except Exception as e:
                    data_logger.warning(f'Alembic migration failed, falling back to db.create_all(): {e}')
                    db.create_all()
                finally:
                    fcntl.flock(migration_lock, fcntl.LOCK_UN)
                    migration_lock.close()
        else:
            try:
                from alembic.config import Config as AlembicConfig
                from alembic import command
                from alembic.script import ScriptDirectory
                from alembic.runtime.migration import MigrationContext
                alembic_ini = os.path.join(BASE_DIR, 'backend', 'alembic.ini')
                if not os.path.exists(alembic_ini):
                    alembic_ini = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alembic.ini')
                alembic_cfg = AlembicConfig(alembic_ini)
                alembic_cfg.set_main_option('sqlalchemy.url', Config.DATABASE_URL)

                with db.engine.connect() as conn:
                    context = MigrationContext.configure(conn)
                    current_rev = context.get_current_revision()
                    script = ScriptDirectory.from_config(alembic_cfg)
                    head_rev = script.get_current_head()
                    if current_rev != head_rev:
                        command.upgrade(alembic_cfg, 'head')
                        data_logger.info(f'Alembic: upgraded {current_rev} -> {head_rev}')
                    else:
                        data_logger.info(f'Alembic: already at revision {head_rev}')
            except Exception as e:
                data_logger.warning(f'Alembic migration failed, falling back to db.create_all(): {e}')
                db.create_all()

        from models.clan_info import ClanMemberInfo, ClanInfo
        member_count = ClanMemberInfo.query.filter_by(is_deleted=False).count()
        clan_count = ClanInfo.query.count()
        data_logger.info(f'Database state: {clan_count} clans, {member_count} active members')
        data_logger.info('=== STARTUP COMPLETE ===')
        data_logger.info('')
        if not User.query.filter_by(username=Config.ADMIN_USER).first():
            admin = User(
                username=Config.ADMIN_USER,
                password_hash=bcrypt.hashpw(Config.ADMIN_PASS.encode(), bcrypt.gensalt()).decode('utf-8'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=app.config.get('APP_HTTP_PORT', 5000))