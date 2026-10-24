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
    # A22: дефолт 'admin' оставлен только для локальной разработки. Любое
    # дефолтное значение ловится enforce_secrets() при старте, а в проде
    # (STRICT_SECRETS=true) делает старт фатальным.
    ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin')

    # A22: включается в проде. Отдельный флаг, а не «определить прод по
    # признакам», — чтобы поведение менялось настройкой, а не эвристикой.
    STRICT_SECRETS = os.environ.get('STRICT_SECRETS', 'false').lower() == 'true'

    # A6: в проде падение миграции обязано быть фатальным. Иначе схема
    # создаётся через create_all() по моделям — без данных, без истории
    # миграций и без добавления столбцов в существующие таблицы, что даёт
    # UndefinedColumn уже во время работы. По умолчанию выключено, чтобы
    # локальная разработка на SQLite не падала на первом же расхождении.
    STRICT_MIGRATIONS = os.environ.get('STRICT_MIGRATIONS', 'false').lower() == 'true'

    _cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
    CORS_ORIGINS = [origin.strip() for origin in _cors_origins.split(',') if origin.strip()]

    # === Improvement Track v2 (gap-close) ===
    # Weighted power model: impact = Σ(Δ · weight). Tuning is deferred (see
    # development-roadmap/improvement-track-v2-plan.md §11 — admin UI later).
    POWER_WEIGHTS = {
        'main_stats': {'Живучесть': 1.0, 'Сила': 2.0, 'Ловкость': 1.5,
                       'Интуиция': 1.5, 'Защита': 1.2},
        'combat_stats': {'Инициатива': 1.8, 'Стойкость': 1.3},
        'magic_stats': {'Воля': 1.0, 'Интеллект': 1.2, 'Концентрация': 1.1,
                        'Мудрость': 1.0, 'Подавление': 1.0},
        'hp': 1.5,
    }
    EFFORT_RANK = {'low': 1, 'medium': 2, 'high': 3}


# A22: известные дефолтные значения — секреты, которые нельзя пускать в прод.
INSECURE_SECRETS = {
    'SECRET_KEY': {
        'dev-secret-key-change-me',
        'change-me-in-production',
        'pre-start-key',
        'secret',
    },
    'ADMIN_PASS': {
        'admin',
        'change-me-in-production',
        'pre-start-key',
        'password',
    },
}


def inspect_secrets(secret_key, admin_pass):
    """Вернуть список проблем с секретами. Пустой список — всё в порядке.

    Проверяются только «известные плохие» значения и пустота: надёжность
    произвольного пароля здесь не оценивается (это не эвристика про энтропию,
    а детектор дефолтов, которые лежат в репозитории открытым текстом).
    """
    problems = []
    for name, value in (('SECRET_KEY', secret_key), ('ADMIN_PASS', admin_pass)):
        text = '' if value is None else str(value).strip()
        if not text:
            problems.append(f'{name} не задан')
        elif text in INSECURE_SECRETS[name]:
            problems.append(f'{name} имеет дефолтное значение из репозитория')
    return problems


def enforce_secrets(strict, logger=None, secret_key=None, admin_pass=None):
    """A22: не пропускать дефолтные секреты молча.

    strict=True — старт падает (прод). strict=False — громкий CRITICAL в лог,
    чтобы проблема была видна, но локальная разработка не умирала.

    Возвращает список найденных проблем (пустой — секреты в порядке).
    """
    problems = inspect_secrets(
        Config.SECRET_KEY if secret_key is None else secret_key,
        Config.ADMIN_PASS if admin_pass is None else admin_pass,
    )
    if not problems:
        return []

    message = 'Небезопасные секреты: ' + '; '.join(problems)
    hint = ('Задайте SECRET_KEY и ADMIN_PASS в .env (см. .env.example.prod) '
            'или отключите STRICT_SECRETS для локальной разработки.')
    if strict:
        raise RuntimeError(f'{message}. {hint}')
    if logger is not None:
        logger.critical('%s. %s', message, hint)
    return problems
