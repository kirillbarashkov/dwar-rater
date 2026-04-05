import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///dwar_rater.db')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    RATE_LIMIT_MAX = int(os.environ.get('RATE_LIMIT_MAX', '30'))
    RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))

    APP_HTTP_PORT = int(os.environ.get('APP_HTTP_PORT', '5000'))

    AUTH_ENABLED = os.environ.get('AUTH_ENABLED', 'true').lower() == 'true'
    ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
    ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin')
