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

## Стек

| Компонент | Технологии |
|---|---|
| Фронтенд | React 18 + TypeScript + Vite |
| Бэкенд | Python 3.14 + Flask + SQLAlchemy |
| СУБД | SQLite |
| Деплой | Docker + Gunicorn |

## Установка и запуск

### Бэкенд

```bash
cd dwar-rater

# Создание виртуального окружения
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # Linux/macOS

# Установка зависимостей
pip install -r requirements.txt

# Запуск
python backend/run.py
```

Бэкенд запустится на `http://127.0.0.1:5000`.

### Фронтенд

```bash
cd frontend

# Установка зависимостей
npm install

# Запуск dev-сервера
npm run dev
```

Фронтенд запустится на `http://localhost:5173`. Запросы к `/api` автоматически проксируются на бэкенд (порт 5000).

### Docker Compose (рекомендуется)

Один запуск для всей инфраструктуры (бэкенд + фронтенд):

```bash
docker compose up -d
```

Сервисы:
- **Бэкенд:** `http://localhost:5000`
- **Фронтенд:** `http://localhost:5173`

### Docker (отдельный контейнер)

```bash
docker build -t dwar-rater .
docker run -d -p 5000:5000 \
  -e ADMIN_PASS=secure_password \
  -e DATABASE_URL=sqlite:///dwar_rater.db \
  dwar-rater
```

## Конфигурация

Все настройки в `backend/config.py` или через переменные окружения:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `SECRET_KEY` | random | Секретный ключ Flask |
| `DATABASE_URL` | `sqlite:///dwar_rater.db` | Строка подключения к БД |
| `AUTH_ENABLED` | `true` | Включить аутентификацию |
| `ADMIN_USER` | `admin` | Логин администратора |
| `ADMIN_PASS` | `admin` | Пароль администратора |
| `RATE_LIMIT_MAX` | `30` | Макс. запросов в окно |
| `RATE_LIMIT_WINDOW` | `60` | Окно rate limit (сек) |

> **Важно:** Смените дефолтный пароль админа перед первым запуском в production.
```

## API

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/login` | Проверка авторизации |
| `GET` | `/api/me` | Данные текущего пользователя |
| `GET` | `/api/health` | Проверка работоспособности |
| `POST` | `/api/analyze` | Анализ персонажа |
| `GET` | `/api/snapshots` | Список слепков |
| `GET` | `/api/snapshots/<id>` | Детали слепка |
| `POST` | `/api/save-snapshot` | Сохранить слепок |
| `DELETE` | `/api/snapshots/<id>` | Удалить слепок |
| `GET` | `/api/scenarios` | Список сценариев прокачки |
| `GET` | `/api/scenarios/<id>` | Детали сценария |
| `POST` | `/api/scenarios` | Создать сценарий (admin) |
| `PUT` | `/api/scenarios/<id>` | Обновить сценарий |
| `DELETE` | `/api/scenarios/<id>` | Удалить сценарий |
| `POST` | `/api/scenarios/<id>/compare` | Сравнить персонаж со сценарием |
| `GET` | `/api/tracks` | Список треков улучшений |
| `GET` | `/api/tracks/<id>` | Детали трека |
| `POST` | `/api/tracks/generate` | Сгенерировать трек из сценария |
| `PUT` | `/api/tracks/<id>/step/<step_id>` | Отметить шаг как выполненный |
| `DELETE` | `/api/tracks/<id>` | Удалить трек |
| `GET` | `/api/clan/<clan_id>/info` | Информация о клане |
| `GET` | `/api/clan/<clan_id>/members` | Состав клана |
| `POST` | `/api/clan/<clan_id>/members` | Добавить участника |
| `PUT` | `/api/clan/<clan_id>/members/<member_id>` | Редактировать участника |
| `DELETE` | `/api/clan/<clan_id>/members/<member_id>` | Удалить участника |
| `GET` | `/api/clans` | Список кланов пользователя |
| `POST` | `/api/clans` | Создать клан (admin) |
| `GET` | `/api/clans/<id>/members` | Участники клана |
| `POST` | `/api/clans/<id>/members` | Добавить участника |
| `DELETE` | `/api/clans/<id>/members/<user_id>` | Удалить участника |
| `GET` | `/api/clans/<id>/rooms` | Комнаты чата клана |
| `POST` | `/api/clans/<id>/rooms` | Создать комнату |
| `GET` | `/api/clans/<id>/rooms/<room_id>/messages` | История сообщений |
| `POST` | `/api/clans/<id>/rooms/<room_id>/messages` | Отправить сообщение |
| `DELETE` | `/api/clans/<id>/rooms/<room_id>/messages/<msg_id>` | Удалить сообщение |

## Структура проекта

```
dwar-rater/
├── backend/                    # Бэкенд (Flask)
│   ├── __init__.py             # App factory (create_app)
│   ├── run.py                  # Точка входа
│   ├── config.py               # Конфигурация
│   ├── models/                 # SQLAlchemy модели
│   │   ├── user.py
│   │   ├── character_cache.py
│   │   ├── character_snapshot.py
│   │   └── analysis_log.py
│   ├── routes/                 # Flask blueprints
│   │   ├── auth.py
│   │   ├── analyze.py
│   │   ├── snapshots.py
│   │   └── health.py
│   ├── services/               # Бизнес-логика
│   │   ├── parser.py           # Парсинг dwar.ru
│   │   ├── processor.py        # Обработка данных
│   │   └── cache_service.py    # Кэширование и слепки
│   ├── middleware/             # Промежуточное ПО
│   │   ├── rate_limiter.py
│   │   ├── security.py
│   │   └── auth.py
│   └── utils/                  # Утилиты
│       ├── validators.py
│       └── formatters.py
├── frontend/                   # Фронтенд (React + TS)
│   ├── src/
│   │   ├── api/                # API клиенты (Axios)
│   │   ├── components/         # React компоненты
│   │   │   ├── ui/             # Базовые UI элементы
│   │   │   └── layout/         # Layout компоненты
│   │   ├── hooks/              # React hooks
│   │   ├── types/              # TypeScript типы
│   │   ├── styles/             # Глобальные стили
│   │   └── utils/              # Константы и утилиты
│   ├── vite.config.ts
│   └── package.json
├── templates/                  # Legacy шаблон (пока используется)
├── static/                     # Legacy статика (пока используется)
├── requirements.txt
└── Dockerfile
```

## Ролевая модель

| Роль | Права |
|---|---|
| **admin** | Видит все слепки, удаляет любые |
| **user** | Видит только свои слепки, удаляет только свои |

## Миграция на PostgreSQL (рекомендуется для production)

SQLite не гарантирует целостность данных при сбоях. Для надёжного хранения используйте PostgreSQL.

### Быстрый старт

```bash
# 1. Запустить PostgreSQL
docker compose up -d postgres

# 2. Создать схему БД
psql -h localhost -U dwar -d dwar_rater -f scripts/schema_postgres.sql

# 3. Мигрировать данные из SQLite
python scripts/migrate_to_postgres.py --sqlite backend/instance/dwar_rater.db --pg-url postgresql://dwar:change-me-in-production@localhost:5432/dwar_rater

# 4. Запустить приложение
docker compose up -d
```

### Настройка автоматического бэкапа (Windows)

```batch
schtasks /create /tn "Dwar Rater Backup" /tr "dwar-rater\backup_cron.bat" /sc daily /st 03:00
```

### Ручной бэкап

```bash
python scripts/backup_postgres.py --keep 7 --cloud rclone
```

## Лицензия

MIT
