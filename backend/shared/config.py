import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    
    _default_db_path = os.path.join(BASE_DIR, 'backend', 'instance', 'dwar_rater.db')
    _db_url = _default_db_path.replace('\\', '/')
    DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{_db_url}')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    RATE_LIMIT_MAX = int(os.environ.get('RATE_LIMIT_MAX', '30'))
    RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))

    APP_HTTP_PORT = int(os.environ.get('APP_HTTP_PORT', '5000'))

    AUTH_ENABLED = os.environ.get('AUTH_ENABLED', 'true').lower() == 'true'
    ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
    ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin')

    _cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
    CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(',') if origin.strip()]
