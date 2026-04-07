import os
import hashlib
from flask import Flask, request, jsonify, abort, g
from flask import render_template
from flask_cors import CORS, cross_origin

from config import Config
from models import db
from models.user import User
from middleware.rate_limiter import check_rate_limit
from middleware.security import add_security_headers


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(BASE_DIR, 'static'),
        template_folder=os.path.join(BASE_DIR, 'templates'),
    )
    app.config.from_object(Config)
    
    # Разрешаем запросы с локального фронта
    cors = CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

    db.init_app(app)

    from routes.auth import auth_bp
    from routes.analyze import analyze_bp
    from routes.snapshots import snapshots_bp
    from routes.health import health_bp
    from routes.scenarios import scenarios_bp
    from routes.tracks import tracks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(analyze_bp)
    app.register_blueprint(snapshots_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(scenarios_bp)
    app.register_blueprint(tracks_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.before_request
    def security_checks():
        if request.path == '/api/login' or request.path == '/' or request.path.startswith('/static/'):
            return
        if not check_rate_limit(Config.RATE_LIMIT_MAX, Config.RATE_LIMIT_WINDOW):
            return jsonify({'error': 'Слишком много запросов. Подождите.'}), 429
        if request.method == 'POST':
            content_type = request.content_type or ''
            if 'application/json' not in content_type:
                abort(415)

    @app.after_request
    def after_request(response):
        return add_security_headers(response)

    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username=Config.ADMIN_USER).first():
            admin = User(
                username=Config.ADMIN_USER,
                password_hash=hashlib.sha256(Config.ADMIN_PASS.encode()).hexdigest(),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=app.config.get('APP_HTTP_PORT', 5000))
