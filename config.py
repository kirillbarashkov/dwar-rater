import os

class Config:
    """
    Конфигурация приложения.
    Чтобы перейти на PostgreSQL, поменяй DATABASE_URL.
    """
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')

    # SQLite для разработки (один файл, ничего устанавливать не нужно)
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///dwar_rater.db')

    # Для PostgreSQL на VPS раскомментируй:
    # DATABASE_URL = 'postgresql://user:password@localhost:5432/dwar_rater'

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Rate limiting
    RATE_LIMIT_MAX = int(os.environ.get('RATE_LIMIT_MAX', '30'))
    RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))

    APP_HTTP_PORT = os.environ.get('APP_HTTP_PORT', '5000')

    # Auth
    AUTH_ENABLED = os.environ.get('AUTH_ENABLED', 'true').lower() == 'true'
    ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
    ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin')
