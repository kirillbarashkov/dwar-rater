# Dwar Rater

Web-приложение для анализа персонажей игры **Легенда: Наследие Драконов** (dwar.ru).

## Возможности

- **Парсинг персонажа** — получение полной информации по ссылке: характеристики, экипировка, медали, эффекты, профессии
- **Категоризация эффектов** — баффы, эликсиры, маунты, дебаффы
- **Расчёт репутации** — медали сгруппированы по репутациям с подсчётом очков
- **Сохранение слепков** — долгосрочное хранение результатов анализа в БД
- **Экспорт** — выгрузка в PDF или HTML
- **Ролевая модель** — админ видит все слепки, пользователь только свои
- **Кэширование** — данные персонажа кэшируются на 1 час

## Установка

```bash
# Клонирование репозитория
git clone <repository-url>
cd dwar-rater

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python app.py # Предварительно необходимо сменить дефолтный пароль админа в config.py, иначе под ним не получится залогиниться
```

Приложение запустится на `http://127.0.0.1:5000`.

## Конфигурация

Все настройки в `config.py` или через переменные окружения:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `SECRET_KEY` | random | Секретный ключ Flask |
| `DATABASE_URL` | `sqlite:///dwar_rater.db` | Строка подключения к БД |
| `AUTH_ENABLED` | `true` | Включить аутентификацию |
| `ADMIN_USER` | `admin` | Логин администратора |
| `ADMIN_PASS` | `admin` | Пароль администратора |
| `RATE_LIMIT_MAX` | `30` | Макс. запросов в окно |
| `RATE_LIMIT_WINDOW` | `60` | Окно rate limit (сек) |

## Переход на PostgreSQL

Для production замените `DATABASE_URL` в `config.py`:

```python
DATABASE_URL = 'postgresql://user:password@localhost:5432/dwar_rater'
```

Или через переменную окружения:

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/dwar_rater
```

## Docker

```bash
docker build -t dwar-rater .
docker run -d -p 5000:5000 \
  -e ADMIN_PASS=secure_password \
  -e DATABASE_URL=postgresql://user:pass@db:5432/dwar_rater \
  dwar-rater
```

## API

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/login` | Проверка авторизации |
| `POST` | `/api/analyze` | Анализ персонажа |
| `GET` | `/api/snapshots` | Список слепков |
| `GET` | `/api/snapshots/<id>` | Детали слепка |
| `POST` | `/api/save-snapshot` | Сохранить слепок |
| `DELETE` | `/api/snapshots/<id>` | Удалить слепок |

## Структура проекта

```
dwar-rater/
├── app.py              # Flask приложение + парсер
├── config.py           # Конфигурация
├── models.py           # SQLAlchemy модели
├── requirements.txt    # Зависимости
├── Dockerfile          # Docker образ
├── .gitignore
├── templates/
│   └── index.html      # Главная страница
└── static/
    ├── style.css       # Стили
    └── app.js          # Фронтенд логика
```

## Ролевая модель

| Роль | Права |
|---|---|
| **admin** | Видит все слепки, удаляет любые |
| **user** | Видит только свои слепки, удаляет только свои |

## Лицензия

MIT
