# Dwar Rater

Web-приложение для анализа персонажей игры **Легенда: Наследие Драконов** (dwar.ru).

## Возможности

- **Парсинг персонажа** — получение полной информации по ссылке: характеристики, экипировка, медали, эффекты, профессии
- **Категоризация эффектов** — баффы, эликсиры, маунты, дебаффы
- **Расчёт репутации** — медали сгруппированы по репутациям с подсчётом очков
- **Сохранение слепков** — долгосрочное хранение результатов анализа в БД
- **Сценарии прокачки** — создание и сравнение персонажа с целевыми сценариями
- **Треки улучшений** — пошаговое отслеживание прогресса прокачки
- **Сравнение персонажей** — side-by-side сравнение нескольких персонажей
- **Управление кланами** — информация о клане, состав, казна, чат
- **Закрытые профили** — мониторинг закрытых профилей на открытие
- **Ролевая модель (RBAC)** — 4 роли с гибкой настройкой прав на уровне фич и действий
- **Админ-панель** — управление пользователями, ролями, правами, бэкапами БД
- **Автоматические бэкапы** — ежедневный бэкап PostgreSQL с хранением в Docker volume
- **Session-based auth** — Bearer token сессии с TOTP 2FA для администраторов
- **Светлая и тёмная тема** — переключение с сохранением в localStorage
- **Swagger API документация** — доступна по адресу `/apidocs`

## Стек

| Компонент | Технологии |
|---|---|
| Фронтенд | React 18 + TypeScript + Vite |
| Бэкенд | Python 3.14 + Flask + SQLAlchemy |
| СУБД | PostgreSQL 16 |
| Миграции | Alembic |
| Деплой | Docker Compose |
| Тесты | pytest (45 тестов) |

## Быстрый старт

### Docker Compose (рекомендуется)

```bash
docker compose up -d
```

Сервисы:
- **Фронтенд:** http://localhost:5173
- **Бэкенд:** http://localhost:5000
- **Swagger API:** http://localhost:5000/apidocs

**Логин:** `admin` / **Пароль:** `change-me-in-production`

> При первом входе система потребует сменить пароль.

### Локальная разработка

**Бэкенд:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python run.py
```

**Фронтенд:**
```bash
cd frontend
npm install
npm run dev
```

## Конфигурация

Скопируйте `.env.example` в `.env` и настройте:

```bash
cp .env.example .env
```

| Переменная | По умолчанию | Описание |
|---|---|---|
| `POSTGRES_USER` | `dwar` | Пользователь PostgreSQL |
| `POSTGRES_PASSWORD` | `change-me-in-production` | Пароль PostgreSQL |
| `POSTGRES_DB` | `dwar_rater` | Имя базы данных |
| `AUTH_ENABLED` | `true` | Включить аутентификацию |
| `ADMIN_USER` | `admin` | Логин администратора |
| `ADMIN_PASS` | `change-me-in-production` | Пароль администратора |
| `RATE_LIMIT_MAX` | `100` | Макс. запросов в окно |
| `RATE_LIMIT_WINDOW` | `60` | Окно rate limit (сек) |
| `ALLOW_VOLUME_DESTRUCTION` | `false` | Защита от удаления данных |

## Ролевая модель (RBAC)

| Роль | Права | Сессия | 2FA |
|---|---|---|---|
| **admin** | Полный доступ ко всему, включая админку | 8ч | Обязательна |
| **superuser** | Полный доступ кроме админки | 8ч | Опциональна |
| **user** | Чтение всего, запись анализа/треков/сравнений | 24ч | Нет |
| **custom** | Права назначаются индивидуально через админку | 24ч | Нет |

### Матрица фич

| Фича | Действия |
|---|---|
| `analyze` | read (анализ), write (принудительное обновление) |
| `snapshots` | read, write, delete, admin (очистка кэша) |
| `clans` | read, write, admin (управление чатом) |
| `clan_info` | read, write, admin (импорт/экспорт казны) |
| `scenarios` | read, write |
| `tracks` | read, write |
| `compare` | read, write |
| `closed_profiles` | read, write |
| `admin` | read, write, admin (audit log) |

## Админ-панель

Доступна по адресу http://localhost:5173/admin (только для admin).

### Табы

1. **Пользователи** — CRUD, смена роли, деактивация, синхронизация из состава клана
2. **Роли и права** — матрица фич × действий с dropdown [full/read/none]
3. **Бэкапы БД** — создание, скачивание, восстановление, удаление бэкапов
4. **Audit Log** — журнал всех действий с фильтрами
5. **Матрица фич** — справочник всех фич и действий

## API

Полная документация: http://localhost:5000/apidocs

### Auth (session-based)

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/auth/login` | Логин → Bearer token |
| `POST` | `/api/auth/login/2fa` | Верификация 2FA |
| `POST` | `/api/auth/logout` | Инвалидация токена |
| `GET` | `/api/auth/me` | Текущий пользователь + права |
| `POST` | `/api/auth/change-password` | Смена пароля |
| `POST` | `/api/auth/2fa/setup` | Настройка TOTP 2FA |

### Основные

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/analyze` | Анализ персонажа |
| `GET` | `/api/snapshots` | Список слепков |
| `POST` | `/api/save-snapshot` | Сохранить слепок |
| `GET` | `/api/scenarios` | Сценарии прокачки |
| `GET` | `/api/tracks` | Треки улучшений |
| `GET` | `/api/compare` | Сравнение персонажей |
| `GET` | `/api/clans` | Список кланов |
| `GET` | `/api/clan/:id/info` | Информация о клане |
| `GET` | `/api/closed-profiles` | Закрытые профили |

### Админка

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/admin/users` | Список пользователей |
| `POST` | `/api/admin/users` | Создать пользователя |
| `PUT` | `/api/admin/users/:id` | Обновить роль/статус |
| `DELETE` | `/api/admin/users/:id` | Деактивировать |
| `POST` | `/api/admin/users/sync` | Синхронизация из клана |
| `GET` | `/api/admin/permissions` | Матрица прав ролей |
| `PUT` | `/api/admin/permissions/role/:id` | Установить права роли |
| `GET` | `/api/admin/backups` | Список бэкапов |
| `POST` | `/api/admin/backups` | Создать бэкап |
| `POST` | `/api/admin/backups/:file/restore` | Восстановить из бэкапа |
| `GET` | `/api/admin/audit` | Audit log |

## Структура проекта

```
dwar-rater/
├── backend/
│   ├── features/              # Вертикальные срезы (10 фич)
│   │   ├── admin/             # Админ-панель API
│   │   ├── analyze/           # Анализ персонажа
│   │   ├── auth/              # Аутентификация
│   │   ├── clans/             # Управление кланами
│   │   ├── clan_info/         # Информация о клане
│   │   ├── closed_profiles/   # Закрытые профили
│   │   ├── compare/           # Сравнение персонажей
│   │   ├── health/            # Health check
│   │   ├── scenarios/         # Сценарии прокачки
│   │   ├── snapshots/         # Слепки персонажей
│   │   └── tracks/            # Треки улучшений
│   ├── shared/                # Общие модули
│   │   ├── models/            # SQLAlchemy модели
│   │   ├── middleware/        # Rate limiter, security
│   │   ├── services/          # Парсер, процессор, кэш
│   │   ├── utils/             # Транслитерация, валидаторы
│   │   └── rbac/              # Ролевая модель
│   │       ├── models.py      # Permission, Role, SessionToken, AuditLog
│   │       ├── seed.py        # Seed данных
│   │       └── __init__.py    # @require_permission, sync_permissions
│   ├── cli/                   # CLI утилита
│   ├── migrations/            # Alembic миграции
│   ├── docs/                  # OpenAPI спецификация
│   ├── scripts/               # Генерация OpenAPI
│   ├── tests/                 # 45 тестов (pytest)
│   ├── app.py                 # App factory
│   ├── test_app.py            # Test app factory (без Alembic)
│   └── config.py              # Конфигурация
├── frontend/
│   └── src/
│       ├── api/               # API клиенты (Axios)
│       ├── components/        # React компоненты
│       │   ├── ui/            # Button, Input, Modal, Toast
│       │   ├── layout/        # Header, Sidebar
│       │   ├── analysis/      # Вкладки анализа
│       │   ├── snapshots/     # Панель слепков
│       │   ├── clan/          # Компоненты кланов
│       │   └── chat/          # Чат клана
│       ├── pages/
│       │   ├── admin/         # Админ-панель (4 таба)
│       │   └── auth/          # Страница логина
│       ├── hooks/             # useAuth, usePermission
│       ├── styles/            # DESIGN.md токены, темы
│       └── types/             # TypeScript типы
├── scripts/
│   ├── db-backup.sh           # Бэкап PostgreSQL (cron)
│   ├── pre-destroy-check.sh   # Защита от удаления данных
│   └── alembic-safe.sh        # Safe миграции с автобэкапом
├── .github/workflows/
│   ├── api-docs-check.yml     # Проверка актуальности API docs
│   ├── design-md-lint.yml     # Валидация DESIGN.md
│   └── destructive-ops-guard.yml  # Guard от разрушительных PR
├── Dockerfile.postgres        # PostgreSQL + cron бэкапы
├── docker-compose.yml
├── Makefile                   # make start/backup/migrate/destroy
└── .env.example
```

## Бэкапы

### Автоматические

Бэкап создаётся **каждый день в 03:00 UTC** через cron внутри PostgreSQL контейнера. Бэкапы хранятся в Docker volume `postgres_backups` и **не удаляются автоматически**.

### Ручной бэкап

```bash
docker exec dwar_rater_postgres /usr/local/bin/db-backup.sh
```

### Восстановление

Через админ-панель: вкладка «Бэкапы БД» → кнопка «Восстановить».

Или вручную:
```bash
gunzip -c /backups/dwar_rater_backup_YYYYMMDD_HHMMSS.sql.gz | \
  docker exec -i dwar_rater_postgres psql -U dwar -d dwar_rater
```

### CLI утилита

```bash
cd backend
python -m cli users list --format json
python -m cli cache clear
python -m cli db status
python -m cli db backup --output ./dump.json
python -m cli health
python -m cli analyze --url "https://w1.dwar.ru/user_info.php?nick=Test" --dry-run
```

## Тесты

```bash
cd backend
python -m pytest -v              # Все тесты (45)
python -m pytest tests/test_url_validator.py -v  # Конкретный файл
```

Тесты используют PostgreSQL (`dwar_rater_test`) с `TRUNCATE CASCADE` между тестами.

### Pre-commit hook

При каждом коммите запускаются тесты внутри Docker контейнера. Hook **не блокирует** коммит при failures, но показывает предупреждение.

## Безопасность

| Механизм | Описание |
|---|---|
| `ALLOW_VOLUME_DESTRUCTION=false` | Блокирует `docker compose down -v` при наличии данных |
| `scripts/pre-destroy-check.sh` | Проверка перед разрушительными операциями |
| `scripts/alembic-safe.sh` | Автобэкап перед миграциями, авторестор при失敗 |
| CI guard | Блокирует PR с volume destruction |
| TOTP 2FA | Обязательна для admin, опциональна для superuser |
| Session auth | 1 сессия на пользователя, Bearer token |
| Rate limiting | 100 запросов / 60 секунд |
| CSP headers | Content-Security-Policy для защиты от XSS |

## Лицензия

MIT
