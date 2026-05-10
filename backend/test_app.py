"""Test app factory — creates Flask app WITHOUT Alembic migrations.

Used by pytest to avoid migration overhead and conflicts during tests.
"""

import os
import bcrypt
from flask import Flask, request, jsonify, abort, g
from flask import render_template
from flask_cors import CORS

from shared.config import Config
from shared.models import db
from shared.models.user import User
from shared.middleware.rate_limiter import check_rate_limit
from shared.middleware.security import add_security_headers


def create_test_app():
    """Create a Flask app for testing — no Alembic, no startup code."""
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static'),
        template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'),
    )
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS, "supports_credentials": True}})

    db.init_app(app)

    from features.auth.routes import auth_bp
    from features.analyze.routes import analyze_bp
    from features.snapshots.routes import snapshots_bp
    from features.health.routes import health_bp
    from features.scenarios.routes import scenarios_bp
    from features.tracks.routes import tracks_bp
    from features.clans.routes import clans_bp
    from features.clan_info.routes import clan_info_bp
    from features.compare.routes import compare_bp
    from features.closed_profiles.routes import closed_profiles_bp
    from features.admin.routes import admin_bp

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
    app.register_blueprint(admin_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/apidocs')
    def apidocs():
        return render_template('apidocs.html')

    @app.route('/api/openapi.yaml')
    def openapi_spec():
        spec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'openapi.yaml')
        with open(spec_path, 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'text/yaml'}

    @app.before_request
    def session_auth():
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            from shared.rbac.models import SessionToken
            session = SessionToken.query.filter_by(token=token).first()
            if session and not session.is_expired:
                g.current_user = session.user
                return
            if request.path.startswith('/api/admin/') or request.path.startswith('/api/auth/'):
                return jsonify({'error': 'Сессия истекла'}), 401

    @app.before_request
    def security_checks():
        if request.path in ('/api/login', '/api/auth/login', '/api/auth/login/2fa', '/api/auth/logout', '/api/auth/change-password', '/', '/api/health', '/apidocs', '/api/openapi.yaml') or request.path.startswith('/static/'):
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

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({'error': 'Method not allowed'}), 405

    return app
