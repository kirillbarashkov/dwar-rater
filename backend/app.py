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

    app.register_blueprint(auth_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(snapshots_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(scenarios_bp)
    app.register_blueprint(tracks_bp)
    app.register_blueprint(clans_bp)
    app.register_blueprint(clan_info_bp)
    app.register_blueprint(compare_bp)

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
        if os.path.exists(instance_dir):
            data_logger.info(f'Instance directory already exists: {instance_dir}')
        elif not os.path.exists(instance_dir):
            os.makedirs(instance_dir)
            data_logger.info(f'Created instance directory: {instance_dir}')
        
        db_path = db.engine.url.database
        db_exists = os.path.exists(db_path) if db_path else False
        db_size = os.path.getsize(db_path) if db_exists else 0
        
        data_logger.info('=== APPLICATION STARTUP ===')
        data_logger.info(f'Database path: {os.path.abspath(db_path) if db_path else "unknown"}')
        data_logger.info(f'Database exists: {db_exists}')
        data_logger.info(f'Database size: {db_size / 1024 / 1024:.2f} MB')
        data_logger.info(f'DATABASE_URL: {Config.DATABASE_URL}')
        
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