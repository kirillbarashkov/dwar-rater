# План: блок A1–A4 (аудит кода 2026-10-20)

> **Для Hermes:** выполнять по одному таску за раз, каждый — с коммитом.
> Порядок обязателен: A1 и A3 меняют код, A2 вводит новый механизм авторизации,
> A4 добавляет инфраструктуру CI. A4 ставится последним, чтобы не ловить
> красный CI на промежуточных коммитах.

**Цель:** закрыть 4 находки High из главы «Аудит» (`backend/docs/about/techdebt.md`),
каждую — с регрессионным тестом, чтобы дефект не вернулся.

**Архитектура:** A1 и A3 — точечные правки с тестами. A2 — новый переиспользуемый
декоратор в `shared/rbac/`, чтобы ручная проверка SSE и `require_permission` вели
из одного источника истины. A4 — отдельный workflow `.github/workflows/frontend-check.yml`,
подключённый как `needs` для деплоя.

**Стек:** Flask 3, SQLAlchemy 2.0, PostgreSQL 16, pytest, React 19, TypeScript 5.9,
ESLint 9, GitHub Actions.

**Репозиторий:** `D:\Programming\Git\Repository\dwar-rater-project\dwar-rater` (ветка `main`).

---

## Сводка по находкам

| # | Дефект | Где | Объём |
|---|--------|-----|--------|
| **A1** | `audit_log` теряет записи — 11 админских операций | `backend/features/admin/routes.py` | 8 правок + тест |
| **A2** | Уровень права `read` проходит гейт `admin` на SSE | `backend/features/clan_info/routes.py` | новый декоратор + 3 правки + тест |
| **A3** | Слепок пишется не в JSON | `backend/features/closed_profiles/routes.py` | 1 строка + тест |
| **A4** | Фронтенд не собирается/типизируется/линтится в CI | `.github/workflows/` | новый workflow |

### Что установлено при подготовке (важно для тасков)

**A1 — уточнение к находке.** Потеряются **11** записей, а не все 13 вызовов `_audit()`:

| Места | Ситуация | Результат |
|---|---|---|
| `L96` (`create_user`), `L282` (`sync_users_from_clan`) | `_audit()` **до** `commit()` | запись **сохраняется** — править не надо |
| `L138, L154, L173, L218, L236, L374, L430, L532` | `_audit()` **после** `commit()` | запись **теряется** |
| `L625, L650, L705` (бэкапы) | `_audit()` **вообще без** `commit()` | запись **теряется** |

**Проверка на проде.** `audit_log` содержит 31 запись, и **все** — treasury-действия
(`treasury_pair_confirm`, `tax_carryover_recompute`, …), где `_audit()` стоит
**до** `commit()`. Админских действий (`user_update`, `user_deactivate`,
`admin_revoke_sessions`, `backup_created`, `backup_restored`, …) — **ноль**.
В `app_user` один пользователь (`admin`, сид от 2026-09-14), созданный не через API.
Вывод: A1 пока **не сжёг** данных, но сработает при первом же админском действии
через API. Восстанавливать нечего — чинить надо до того, как журнал начнёт
наполняться.

**A2 — как устроен вызов.** `EventSource` не умеет отправлять заголовки, поэтому
токен передаётся в query: `frontend/src/components/clan/MembershipImportTab.tsx:98`
и `:548` → `?token=...`. Значит, декоратор должен принимать токен **и** из
заголовка, **и** из query-параметра.

**A3 — писателей ровно три.** `features/closed_profiles/routes.py:223` (сломан),
`shared/services/cache_service.py:30` и `:46` (оба корректны, `json.dumps`).
Читателей три: `features/snapshots/routes.py:62`, `features/export/routes.py:64`,
`features/tracks/routes.py:55` — все через `json.loads`.

**A4 — состояние фронтенда.** `npm run lint` = **17 errors / 8 warnings**
(совпадает с TD-2, долг не растёт). `tsc -b` — чисто. `package.json` не содержит
скрипта `test`, тестов фронтенда нет. `eslint.config.js` — flat config, без
кастомных правил, поэтому «зафиксировать baseline» = добавить inline-директивы
в конкретные файлы.

---

## Этап 0. Подготовка (общий)

### Task 0.1: Зафиксировать базовую линию

**Objective:** иметь эталон для сравнения после каждого таска.

**Files:** не меняются.

**Step 1: Убедиться, что дерево чистое**

```bash
cd D:/Programming/Git/Repository/dwar-rater-project/dwar-rater
git status --short
```
Expected: пусто (иначе — `git stash`).

**Step 2: Прогнать тесты на хосте (после A61 ошибок быть не должно)**

```bash
cd backend
set -a && . <(grep -E "^(POSTGRES_USER|POSTGRES_PASSWORD)=" ../.env) && set +a
export TEST_DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/dwar_rater_test"
python3 -m pytest -q
```
Expected: **446 passed**, 0 errors (≈9 мин).

**Step 3: Записать б��злайн**

```bash
npm run lint 2>&1 | tail -2   # frontend: ожидается «25 problems (17 errors, 8 warnings)»
cd frontend && npx tsc -b && echo "tsc clean"
```

**Примечание.** После A61 прогон на хосте и в контейнере дают одинаковый
результат — 446 passed. Если увидишь расхождение, остановись: значит, что-то
сломалось не там.

---

## Этап 1. A3 — слепок в JSON (самый маленький, чинит первым)

### Task 1.1: Написать падающий тест

**Objective:** тест, который падает на текущем коде и проходит после правки.

**Files:**
- Create: `backend/tests/test_closed_profiles.py`

**Step 1: Написать тест**

```python
"""closed_profiles: слепок обязан сохраняться в JSON — читатели используют json.loads."""
import json

from shared.models import db
from shared.models.character_snapshot import CharacterSnapshot
from shared.models.closed_profile import ClosedProfile


def test_saved_snapshot_is_readable_as_json(app, client, user_headers):
    """POST /api/closed-profiles/<nick>/save-snapshot → GET /api/snapshots/<id> отдаёт 200."""
    nick = 'profileprobe'
    with app.app_context():
        # Поля ClosedProfile: nick, status, level, rank, clan, notes, is_scanned_open.
        # Уникальность nick — чтобы повторный прогон не падал.
        existing = ClosedProfile.query.filter_by(nick=nick).first()
        if existing:
            ClosedProfile.query.filter_by(nick=nick).delete()
        db.session.add(ClosedProfile(nick=nick, status='closed'))
        db.session.commit()

    payload = {
        'name': 'Гном',
        'race': ' dwarf',
        'rank': '100',
        'clan': 'Клан',
    }
    r = client.post(
        f'/api/closed-profiles/{nick}/save-snapshot',
        json={'snapshot_data': payload, 'snapshot_name': 'probe'},
        headers=user_headers,
    )
    assert r.status_code == 200, r.get_json()
    snapshot_id = r.get_json()['snapshot_id']

    with app.app_context():
        snap = CharacterSnapshot.query.get(snapshot_id)
        # запись в БД обязана быть валидным JSON
        parsed = json.loads(snap.snapshot_data)
        assert parsed['name'] == 'Гном'

    # и читательский эндпоинт не должен падать
    r2 = client.get(f'/api/snapshots/{snapshot_id}', headers=user_headers)
    assert r2.status_code == 200, r2.get_json()
```

**Step 2: Убедиться, что тест падает**

```bash
cd backend
export TEST_DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/dwar_rater_test"
python3 -m pytest tests/test_closed_profiles.py -q
```
Expected: FAIL — `JSONDecodeError: Expecting property name enclosed in double quotes`.

**Если тест упал иначе** (404 на `save-snapshot` или 403) — проверь:
1. Права: `save-snapshot` требует `closed_profiles:read` — у роли `user` она
   `full` (`shared/rbac/seed.py:143`), так что `user_headers` подходит.
2. Что `user_headers` вообще выдаёт токен: фикстура `user_token` берёт
   пользователя `testuser` (`tests/conftest.py:182`).
3. Что эндпоинт на месте: `grep -n "save-snapshot" backend/features/closed_profiles/routes.py`.

**Step 3: Закоммитить падающий тест**

```bash
git add backend/tests/test_closed_profiles.py
git commit -m "test(closed_profiles): слепок обязан читаться как JSON"
```
Коммит с падающим тестом допустим — следующий коммит его починит.

### Task 1.2: Починить запись

**Objective:** писать JSON вместо Python-repr.

**Files:**
- Modify: `backend/features/closed_profiles/routes.py:230`

**Step 1: Добавить импорт**

В начало файла (рядом с прочими импортами) — если `json` ещё не импортирован:

```python
import json
```

**Step 2: Заменить строку 230**

Было:
```python
        snapshot_data=str(snapshot_data),
```
Стало:
```python
        snapshot_data=json.dumps(snapshot_data, ensure_ascii=False),
```

**Step 3: Проверить**

```bash
python3 -m pytest tests/test_closed_profiles.py -q
```
Expected: PASS.

**Step 4: Проверить, что не сломались другие писатели**

```bash
python3 -m pytest tests/test_snapshots.py tests/test_analyze.py tests/test_track_engine.py -q
```
Expected: PASS.

**Step 5: Закоммитить**

```bash
git add backend/features/closed_profiles/routes.py
git commit -m "fix(closed_profiles): сохранять слепок в JSON, а не через str()"
```

### Task 1.3: Закрыть A3 в реестре

**Objective:** привести документ в соответствие с фактом.

**Files:**
- Modify: `backend/docs/about/techdebt.md` (раздел A3)

**Step 1: В заголовке A3 заменить**

```markdown
#### A3. [доказано] Слепок сохраняется не в JSON — чтение слепка падает
```
на
```markdown
#### A3. ✅ ЗАКРЫТО (2026-10-20) — Слепок сохранялся не в JSON
```

**Step 2: Дописать в конец раздела A3**

```markdown
**Решение.** `str(snapshot_data)` → `json.dumps(snapshot_data, ensure_ascii=False)`
(`features/closed_profiles/routes.py:230`). Добавлен тест
`tests/test_closed_profiles.py` — он проверяет и разбор записи из БД, и то, что
читательский `GET /api/snapshots/<id>` отвечает 200.
```

**Step 3: Поправить сводку** — в таблице «Ключевые числа аудита» или в списке
открытых находок A3 убрать из «требуют внимания в первую очередь».

**Step 4: Закоммитить вместе с кодом** (можно в том же коммите, что Task 1.2).

---

## Этап 2. A1 — записи аудита не теряются

### Task 2.1: Написать тест, покрывающий все 11 мест

**Objective:** один параметризованный тест, который проверяет, что каждое
админское действие оставляет след в `audit_log`.

**Files:**
- Create: `backend/tests/test_admin_audit.py`

**Образец для подражания** — `backend/tests/test_members_import_audit.py`
(он проверяет, что импорт состава оставляет запись).

**Step 1: Написать тест**

```python
"""A1: каждое админское действие обязано оставлять запись в audit_log.

Регрессия: _audit() только делает db.session.add(), а запись появляется при
следующем commit(). Если _audit() вызван ПОСЛЕ commit() (или без него) —
запись теряется, и журнал аудита молча неполон.
"""
import pytest

from shared.models import db
from shared.models.user import User
from shared.rbac.models import AuditLog, Role


def _count(app, action):
    """Сколько записей с таким action в журнале.

    Читать AuditLog надо внутри app-контекста: после client-запроса сессия
    flask-sqlalchemy уже снята, и AuditLog.query без контекста падает.
    """
    with app.app_context():
        return AuditLog.query.filter_by(action=action).count()


def _role_id(app, name):
    with app.app_context():
        role = Role.query.filter_by(name=name).first()
        assert role is not None, f'роль {name} не засеяна'
        return role.id


@pytest.fixture
def target_user(app):
    """Пользователь-цель для админских операций."""
    with app.app_context():
        u = User.query.filter_by(username='testuser').first()
        db.session.commit()
        yield u.id


def test_user_update_is_audited(app, client, admin_headers, target_user):
    before = _count(app, 'user_update')
    r = client.put(f'/api/admin/users/{target_user}',
                   json={'is_active': True}, headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'user_update') == before + 1


def test_user_deactivate_is_audited(app, client, admin_headers, target_user):
    before = _count(app, 'user_deactivate')
    r = client.delete(f'/api/admin/users/{target_user}', headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'user_deactivate') == before + 1


def test_revoke_other_sessions_is_audited(app, client, admin_headers, target_user):
    before = _count(app, 'admin_revoke_sessions')
    r = client.delete(f'/api/admin/users/{target_user}/sessions/others',
                      headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'admin_revoke_sessions') == before + 1


def test_role_permissions_update_is_audited(app, client, admin_headers):
    role_id = _role_id(app, 'treasurer')
    before = _count(app, 'role_permissions_update')
    r = client.put(f'/api/admin/permissions/role/{role_id}',
                   json={'permissions': {}}, headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'role_permissions_update') == before + 1


def test_user_permissions_update_is_audited(app, client, admin_headers, target_user):
    before = _count(app, 'user_permissions_update')
    r = client.put(f'/api/admin/permissions/user/{target_user}',
                   json={'permissions': {}}, headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'user_permissions_update') == before + 1


def test_deprecated_permissions_delete_is_audited(app, client, admin_headers):
    before = _count(app, 'deprecated_permissions_deleted')
    r = client.delete('/api/admin/permissions/deprecated', headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'deprecated_permissions_deleted') == before + 1
```

**Внимание к `_count`:** он **обязан** брать `app` и открывать контекст сам.
Вариант «посчитать в конце теста без контекста» падает с
`RuntimeError: Working outside of application context` — это уже проверено
на A61 (`db.session.remove()` вне контекста дал 278 errors в teardown).

**Step 2: Запустить — тесты должны ПАСТЬ**

```bash
python3 -m pytest tests/test_admin_audit.py -q
```
Expected: падения на `user_update`, `user_deactivate`, `admin_revoke_sessions`,
`role_permissions_update`, `user_permissions_update`, `deprecated_permissions_deleted`
(тест на бэкапы — см. Task 2.3, он отдельный).

**Step 3: Закоммитить падающий тест**

```bash
git add backend/tests/test_admin_audit.py
git commit -m "test(admin): админские действия обязаны оставлять след в audit_log"
```

### Task 2.2: Починить 8 мест, где `_audit()` идёт после `commit()`

**Objective:** перенести `_audit()` **до** `db.session.commit()`, чтобы операция
и её след фиксировались одной транзакцией.

**Files:**
- Modify: `backend/features/admin/routes.py` — строки 138, 154, 173, 218, 236, 374, 430, 532

**Принцип:** `_audit()` должен идти **до** `commit()`. Тогда `db.session.add(entry)`
попадёт в БД тем же коммитом, что и сама операция. Атомарность сохраняется:
если коммит не прошёл, не будет ни операции, ни её следа.

**Step 1: `update_user` (строка ~129-138)**

Было:
```python
    db.session.commit()

    changes = {}
    if old_role != user.role:
        changes['role'] = {'old': old_role, 'new': user.role}
    if old_active != user.is_active:
        changes['is_active'] = {'old': old_active, 'new': user.is_active}

    if changes:
        _audit('user_update', target_type='user', target_id=user.id, old=old_role, new=user.role)

    return jsonify(user.to_dict())
```
Стало:
```python
    changes = {}
    if old_role != user.role:
        changes['role'] = {'old': old_role, 'new': user.role}
    if old_active != user.is_active:
        changes['is_active'] = {'old': old_active, 'new': user.is_active}

    if changes:
        _audit('user_update', target_type='user', target_id=user.id, old=old_role, new=user.role)

    db.session.commit()

    return jsonify(user.to_dict())
```

**Step 2: `deactivate_user` (~150-154)**

Было:
```python
    user.is_active = False
    SessionToken.query.filter_by(user_id=user_id).delete()
    db.session.commit()

    _audit('user_deactivate', target_type='user', target_id=user.id, old='active', new='inactive')
```
Стало:
```python
    user.is_active = False
    SessionToken.query.filter_by(user_id=user_id).delete()

    _audit('user_deactivate', target_type='user', target_id=user.id, old='active', new='inactive')

    db.session.commit()
```

**Step 3: `admin_unbind_character` (~169-173)**

Было:
```python
    user.character_url = None
    user.character_nick = None
    db.session.commit()

    _audit(
        'admin_unbind_character', target_type='user', target_id=user.id,
        old=old_value, new={'character_url': None, 'character_nick': None},
    )
```
Стало: `_audit(...)` **перед** `db.session.commit()`.

**Step 4: `revoke_user_other_sessions` (~217-218)**

Было:
```python
    db.session.commit()
    _audit(
        'admin_revoke_sessions', target_type='user', target_id=user.id,
        old={'sessions': ids}, new={'count': len(ids)},
    )
```
Стало: `_audit(...)` **перед** `db.session.commit()`.

**Step 5: `revoke_user_session` (~235-236)** — аналогично.

**Step 6: `update_role_permissions` (~372-374)** — аналогично.

**Step 7: `update_user_permissions` (~428-430)** — аналогично.

**Step 8: `delete_deprecated_permissions` (~530-532)** — аналогично.

**Step 9: Прогнать тесты**

```bash
python3 -m pytest tests/test_admin_audit.py -q
```
Expected: тесты на эти 6 действий — PASS; тесты на бэкапы — ещё падают (они в Task 2.3).

**Step 10: Закоммитить**

```bash
git add backend/features/admin/routes.py
git commit -m "fix(admin): _audit() до commit() — записи аудита больше не теряются"
```

### Task 2.3: Починить 3 места, где `_audit()` вообще без `commit()`

**Objective:** бэкап-операции тоже должны оставлять след.

**Files:**
- Modify: `backend/features/admin/routes.py` — строки 625, 650, 705

**Step 1: `create_backup` (~624-625)**

Было:
```python
        info = _get_backup_info(filepath)
        _audit('backup_created', target_type='backup', new={'filename': filename, 'size': info['size']})

        return jsonify({'status': 'created', 'backup': info})
```
Стало:
```python
        info = _get_backup_info(filepath)
        _audit('backup_created', target_type='backup', new={'filename': filename, 'size': info['size']})
        db.session.commit()

        return jsonify({'status': 'created', 'backup': info})
```

**Step 2: `delete_backup` (~649-650)**

Было:
```python
    os.remove(filepath)
    _audit('backup_deleted', target_type='backup', old={'filename': filename})
```
Стало:
```python
    os.remove(filepath)
    _audit('backup_deleted', target_type='backup', old={'filename': filename})
    db.session.commit()
```

**Step 3: `restore_backup` (~704-705)**

Было:
```python
        _audit('backup_restored', target_type='backup', new={'filename': filename})

        return jsonify({'status': 'restored', 'filename': filename})
```
Стало:
```python
        _audit('backup_restored', target_type='backup', new={'filename': filename})
        db.session.commit()

        return jsonify({'status': 'restored', 'filename': filename})
```

**Step 4: Дописать тесты на бэкапы в `tests/test_admin_audit.py`**

```python
def test_backup_created_is_audited(app, client, admin_headers, tmp_path, monkeypatch):
    """Создание бэкапа должно оставлять след в audit_log."""
    import backend.features.admin.routes as admin_routes
    # Подменяем каталог бэкапов на временный и сам pg_dump — тест не должен
    # дёргать реальный Postgres.
    monkeypatch.setattr(admin_routes, 'BACKUP_DIR', str(tmp_path))
    monkeypatch.setattr(admin_routes.subprocess, 'run', _fake_pg_dump)

    before = _count(app, 'backup_created')
    r = client.post('/api/admin/backups', headers=admin_headers)
    assert r.status_code == 200, r.get_json()
    assert _count(app, 'backup_created') == before + 1
```

**`_fake_pg_dump`** — заглушка, которая пишет в stdout байты, чтобы код прошёл
проверку `result.returncode != 0`:

```python
class _FakeResult:
    returncode = 0
    stdout = b'-- fake dump\n'
    stderr = b''


def _fake_pg_dump(*args, **kwargs):
    return _FakeResult()
```

**Примечание.** `create_backup` пишет через `gzip` и `os.rename` — временный
каталог `tmp_path` подходит. Если тест окажется хрупким (например, из-за
`os.makedirs`), упрости: проверяй только `delete_backup` и `restore_backup`,
а для `create_backup` оставь покрытие на будущее — **но тогда не считай A1
закрытым**.

**Step 5: Прогнать**

```bash
python3 -m pytest tests/test_admin_audit.py -q
```
Expected: все PASS.

**Step 6: Полный прогон**

```bash
python3 -m pytest -q
```
Expected: **446+ passed**, 0 errors.

**Step 7: Закоммитить**

```bash
git add backend/features/admin/routes.py backend/tests/test_admin_audit.py
git commit -m "fix(admin): аудит операций с бэкапами + тесты"
```

### Task 2.4: Проверить на проде после деплоя

**Objective:** убедиться, что записи действительно появляются.

**Step 1: После деплоя (v-патч) создать тестового пользователя через API и
проверить журнал**

```bash
# на VM, от root пользователя VM
docker compose -f docker-compose.prod.yml exec -T postgres psql -U dwar -d dwar_rater \
  -c "SELECT action, count(*) FROM audit_log GROUP BY action ORDER BY 2 DESC;"
```
Expected: среди действий появились `user_create` / `user_update` — до правки их
не было **никогда**.

**Step 2: Откатить тестового пользователя** (он не должен остаться в проде):
через API `DELETE /api/admin/users/<id>`.

---

## Этап 3. A2 — единая проверка прав на SSE

### Task 3.1: Спроектировать и добавить декоратор

**Objective:** один источник истины для проверки прав — чтобы ручная проверка
SSE и `require_permission` не могли разойтись.

**Files:**
- Modify: `backend/shared/rbac/__init__.py` (добавить в конец)

**Проблема, которую надо решить:** `require_permission` работает с `g.current_user`,
который ставит `before_request` в `app.py` по заголовку `Authorization`. SSE
передаёт токен в query, поэтому `g.current_user` там **не заполнен**.

**Решение:** декоратор сам достаёт токен (заголовок **или** query), находит
сессию, проверяет срок и `is_active`, и **только потом** проверяет уровень права
**той же логикой**, что `require_permission`.

**Step 1: Вынести проверку уровня в общий хелпер**

Сейчас в `shared/rbac/__init__.py:215-221` логика выглядит так:

```python
            level = get_user_permission(user, feature, action)
            if level == 'none':
                return jsonify({'error': 'Доступ запрещён'}), 403

            # 'read' level blocks write/delete/admin/approve actions
            if level == 'read' and action in ('write', 'delete', 'admin', 'approve'):
                return jsonify({'error': 'Недостаточно прав'}), 403
```

Вынеси её в функцию (чтобы и декоратор, и `require_permission` её звали):

```python
def check_permission_level(user, feature, action):
    """Проверить достаточность уровня права. Возвращает (ok, error_response).

    Единый источник истины: 'read' не даёт write/delete/admin/approve.
    """
    level = get_user_permission(user, feature, action)
    if level == 'none':
        return False, (jsonify({'error': 'Доступ запрещён'}), 403)
    if level == 'read' and action in ('write', 'delete', 'admin', 'approve'):
        return False, (jsonify({'error': 'Недостаточно прав'}), 403)
    return True, None
```

**Step 2: Переписать `require_permission` через неё**

```python
def require_permission(feature: str, action: str):
    """Decorator to require a specific permission.
    ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = g.get('current_user')
            if not user:
                return jsonify({'error': 'Требуется авторизация'}), 401

            if not user.is_active:
                return jsonify({'error': 'Аккаунт деактивирован'}), 403

            ok, error = check_permission_level(user, feature, action)
            if not ok:
                return error

            return f(*args, **kwargs)
        return decorated
    return decorator
```

**Step 3: Добавить декоратор для SSE**

```python
def require_permission_from_token(feature: str, action: str):
    """Проверить право по токену из заголовка ИЛИ query-параметра.

    Нужен для SSE: EventSource не умеет отправлять заголовки, поэтому токен
    приходит в ?token=. Проверки те же, что в require_permission: срок сессии,
    is_active и достаточность уровня права.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from shared.rbac.models import SessionToken
            from shared.models.user import User

            token = request.args.get('token') or request.headers.get(
                'Authorization', ''
            ).replace('Bearer ', '')

            user = None
            if token:
                session = SessionToken.find_by_token(token)
                if session and not session.is_expired:
                    user = session.user

            if not user:
                return jsonify({'error': 'Требуется авторизация'}), 401

            if not user.is_active:
                return jsonify({'error': 'Аккаунт деактивирован'}), 403

            ok, error = check_permission_level(user, feature, action)
            if not ok:
                return error

            return f(*args, **kwargs)
        return decorated
    return decorator
```

**Step 4: Проверить, что ничего не сломалось**

```bash
python3 -m pytest tests/test_auth.py tests/test_session_management.py tests/test_treasury_permissions.py -q
```
Expected: PASS.

**Step 5: Закоммитить**

```bash
git add backend/shared/rbac/__init__.py
git commit -m "refactor(rbac): единая проверка уровня права + декоратор для SSE по токену"
```

### Task 3.2: Написать тест на обход прав

**Objective:** тест, который падает на текущем коде (уровень `read` проходит) и
проходит после правки.

**Files:**
- Create: `backend/tests/test_sse_permissions.py`

**Step 1: Написать тест**

```python
"""A2: SSE-эндпоинты не должны пускать пользователя с уровнем 'read' на действие 'admin'.

Раньше проверка была ручной: get_user_permission(...) == 'none'. Это слабее
require_permission, который уровень 'read' для admin-запрещает.
"""
from datetime import datetime, timezone, timedelta

import pytest

from shared.models import db
from shared.models.user import User
from shared.rbac.models import Permission, UserPermission, SessionToken


@pytest.fixture
def read_level_token(app):
    """Пользователь с индивидуальным правом treasury:admin = 'read'."""
    with app.app_context():
        user = User.query.filter_by(username='testuser').first()
        perm = Permission.query.filter_by(feature='treasury', action='admin').first()
        assert perm is not None

        up = UserPermission.query.filter_by(
            user_id=user.id, permission_id=perm.id
        ).first()
        if up:
            up.level = 'read'
        else:
            db.session.add(UserPermission(
                user_id=user.id, permission_id=perm.id, level='read'
            ))

        token = 'sse-read-level-token'
        db.session.add(SessionToken(
            user_id=user.id,
            token_hash=SessionToken.hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.session.commit()
        yield token


def test_read_level_is_refused_on_treasury_sse(app, client, read_level_token):
    """Уровень 'read' не должен давать доступ к admin-действию."""
    r = client.get(
        f'/api/clan/1/treasury/auto-fetch-stream?token={read_level_token}'
    )
    assert r.status_code == 403, r.get_json()
    body = r.get_data(as_text=True)
    assert 'forbidden' not in body


def test_read_level_is_refused_on_members_sse(app, client, read_level_token):
    r = client.get(
        f'/api/clan/1/members/auto-fetch-stream?token={read_level_token}'
    )
    assert r.status_code == 403, r.get_json()


def test_read_level_is_refused_on_level_events_sse(app, client, read_level_token):
    r = client.get(
        f'/api/clan/1/level-events/import-stream?token={read_level_token}'
    )
    assert r.status_code == 403, r.get_json()
```

**Step 2: Проверить, что тест падает**

```bash
python3 -m pytest tests/test_sse_permissions.py -q
```
Expected: FAIL — сейчас ответ 200 (гейт пройден).

**Step 3: Закоммитить падающий тест**

```bash
git add backend/tests/test_sse_permissions.py
git commit -m "test(sse): уровень read не должен проходить гейт admin"
```

### Task 3.3: Повесить декоратор на три SSE-эндпоинта

**Objective:** убрать ручную проверку, повесить `@require_permission_from_token`.

**Files:**
- Modify: `backend/features/clan_info/routes.py` — строки 4561-4586, 4691-4715, 5196-5221

**Step 1: `auto_fetch_treasury_stream` (4561)**

Было:
```python
@clan_info_bp.route(
    "/api/clan/<int:clan_id>/treasury/auto-fetch-stream", methods=["GET"]
)
def auto_fetch_treasury_stream(clan_id):
    from flask import Response, request
    from urllib.parse import unquote
    import json
    from shared.rbac.models import SessionToken
    from shared.models.user import User
    from datetime import datetime, timezone

    # Auth via query param (for SSE) or standard header
    token = request.args.get("token") or request.headers.get(
        "Authorization", ""
    ).replace("Bearer ", "")
    current_user = None
    if token:
        session_token = SessionToken.find_by_token(token)
        if session_token:
            expires = session_token.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires > datetime.now(timezone.utc):
                current_user = User.query.get(session_token.user_id)

    if not current_user or get_user_permission(current_user, "treasury", "admin") == "none":
        ...  # error_gen с reason=forbidden
```
Стало:
```python
@clan_info_bp.route(
    "/api/clan/<int:clan_id>/treasury/auto-fetch-stream", methods=["GET"]
)
@require_permission_from_token("treasury", "admin")
def auto_fetch_treasury_stream(clan_id):
    from flask import Response, request
    from urllib.parse import unquote
    import json
```

**Важно:** блок с `error_gen` (reason=forbidden) **убирается целиком** — декоратор
теперь отдаёт обычный 403 JSON, а не SSE-ошибку. Фронт это переживёт: он
проверяет `reason` только в потоке, а 403 приходит до открытия потока.

**Step 2: `auto_fetch_members_stream` (4691)** — то же самое, но
`@require_permission_from_token("clan_info", "admin")`.

**Step 3: `import_level_events_stream` (5196)** — то же, `"clan_info", "admin"`.

**Step 4: Проверить импорт**

`require_permission_from_token` должен быть импортирован в
`features/clan_info/routes.py`. Найди строку импорта:

```python
from shared.rbac import require_permission, feature, Permission as PermDef, get_user_permission
```
и добавь в неё `require_permission_from_token`.

**Step 5: Проверить, не осталось ли ручных проверок**

```bash
grep -n "get_user_permission" backend/features/clan_info/routes.py
```
Expected: пусто (или только в местах, не связанных с SSE).

**Step 6: Прогнать тесты**

```bash
python3 -m pytest tests/test_sse_permissions.py -q
```
Expected: PASS.

**Step 7: Полный прогон + контейнерный путь**

```bash
python3 -m pytest -q
cd .. && bash scripts/run_backend_tests.sh
```
Expected: оба — 446+ passed, 0 errors.

**Step 8: Закоммитить**

```bash
git add backend/features/clan_info/routes.py
git commit -m "fix(sse): единая проверка прав на SSE-эндпоинтах, read больше не проходит admin-гейт"
```

### Task 3.4: Проверить фронт после смены ответа

**Objective:** убедиться, что фронт корректно обрабатывает 403 вместо SSE-ошибки.

**Files:**
- Inspect: `frontend/src/components/clan/MembershipImportTab.tsx:96-105`, `:546-556`
- Inspect: `frontend/src/components/clan/TreasuryImport.tsx` (место создания EventSource)

**Step 1: Прочитать обработчик `onerror` у `EventSource`**

EventSource при 403 не открывает поток — браузер получает обычный HTTP-ответ.
`onerror` сработает, но `event.data` будет пустым.

**Step 2: Проверить, что UI не зависнет**

Если обработчик полагается только на SSE-события, пользователь увидит «вечный
спиннер». Если в коде есть ветка на `onerror` — всё в порядке.

**Step 3: Если ветки нет — добавить понятное сообщение**

Минимально: в `onerror` показать «Недостаточно прав» вместо бесконечной загрузки.
Правку фронта согласовать с владельцем — это отдельный файл, и A4 добавит
tsc-проверку, так что ошибка типов всплывёт сразу.

**Step 4: Проверить вручную (в браузере)**

Залогиниться пользователем с `treasury:admin = read`, нажать «Начать сбор» →
ожидается понятная ошибка, а не спиннер.

### Task 3.5: Закрыть A2 в реестре

**Files:**
- Modify: `backend/docs/about/techdebt.md` (раздел A2)

Дописать: решение, новый декоратор, имя теста, факт «уровень read теперь
блокируется на всех трёх SSE», и то, что `is_active` тоже проверяется.

---

## Этап 4. A4 — фронтенд в CI

### Task 4.1: Зафиксировать baseline линта

**Objective:** новые ошибки линта должны ломать CI, а существующие 17 — нет.

**Files:**
- Modify: `frontend/eslint.config.js` (или точечные файлы)

**Вариант A (рекомендую) — baseline через конфиг.** ESLint 9 flat config не имеет
встроенного «baseline», но есть `eslint-plugin-only-warn` — **лишняя зависимость,
не хочу её тащить**.

**Вариант B (проще, без зависимостей) — точечные inline-директивы.** В каждый из
17 мест добавить `// eslint-disable-next-line <rule>`. Это 17 правок в 12 файлах
и они «залипнут» — когда долг TD-2 будет закрыт, директивы придётся убирать.

**Вариант C (рекомендую) — разделить на «ошибки» и «warnings».** ESLint умеет
понижать уровень правила до warning через конфиг. Тогда CI проверяет **новые
ошибки** (exit code 1) и **новые warnings** (exit code 0), а старые 17 станут
warnings и перестанут ломать сборку. Когда TD-2 будет закрыт, правила
возвращаются в error.

Реализация варианта C — в `frontend/eslint.config.js` добавить блок с
пониженными правилами **только** для тех файлов, где они сейчас срабатывают:

```javascript
// Baseline: существующие нарушения (TD-2) понижены до warning, чтобы CI
// ловил НОВЫЕ ошибки. Когда TD-2 закрыт — блок удаляется.
{
  files: [
    'src/App.tsx',
    'src/components/analysis/CharacterComparison.tsx',
    'src/components/character/CharacterClanTab.tsx',
    'src/components/clan/ClanMembersTable.tsx',
    'src/components/clan/MembershipImportTab.tsx',
    'src/components/clan/TalentAnalytics.tsx',
    'src/components/clan/TaxAnalytics.tsx',
    'src/components/clan/TreasuryImport.tsx',
    'src/components/layout/SearchBar.tsx',
    'src/components/snapshots/SnapshotHistory.tsx',
    'src/hooks/useAuth.tsx',
    'src/pages/character/CharacterPageWrapper.tsx',
  ],
  rules: {
    'react-hooks/set-state-in-effect': 'warn',
    'react-hooks/exhaustive-deps': 'warn',
    'react-refresh/only-export-components': 'warn',
    'no-case-declarations': 'warn',
    '@typescript-eslint/no-unused-vars': 'warn',
    '@typescript-eslint/no-explicit-any': 'warn',
  },
}
```

**Step 1: Получить точный список файлов и правил**

```bash
cd frontend
npx eslint . -f json > lint.json
python3 -c "
import json, collections
d=json.load(open('lint.json'))
per=collections.defaultdict(lambda: collections.Counter())
for f in d:
    if not f['messages']: continue
    rel=f['filePath'].split('frontend')[-1]
    for m in f['messages']:
        per[rel][m['ruleId']]+=1
for rel, rules in sorted(per.items()):
    print(rel, dict(rules))
"
```

**Step 2: Внести блок в `eslint.config.js`** по списку из шага 1.

**Step 3: Проверить, что baseline сошёлся**

```bash
npm run lint 2>&1 | tail -3
```
Expected: **0 errors** (17 ушли в warnings), счётчик warnings вырос.

**Step 4: Убедиться, что exit code = 0**

```bash
npm run lint; echo "EXIT=$?"
```
Expected: `EXIT=0`.

**Step 5: Проверить, что НОВАЯ ошибка всё-таки ломает сборку**

Временно добавь в любой `.tsx` `const x: any = 1;` в неигнорируемый файл
(например, `src/utils/constants.ts`) и убедись, что `npm run lint` даёт
`EXIT=1`. Потом убери.

**Step 6: Закоммитить**

```bash
git add frontend/eslint.config.js
git commit -m "chore(frontend): baseline линта — старые 17 нарушений понижены до warning"
```

### Task 4.2: Добавить workflow фронтенда

**Objective:** CI, который собирает, типизирует и линтит фронтенд.

**Files:**
- Create: `.github/workflows/frontend-check.yml`

**Step 1: Создать файл**

```yaml
name: Frontend Check

on:
  pull_request:
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend-check.yml'
  push:
    branches: [main]
    paths:
      - 'frontend/**'
      - '.github/workflows/frontend-check.yml'

concurrency:
  group: frontend-check-${{ github.ref }}
  cancel-in-progress: true

jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Typecheck
        working-directory: frontend
        run: npx tsc -b

      - name: Lint
        working-directory: frontend
        run: npm run lint

      - name: Build
        working-directory: frontend
        run: npx vite build
```

**Почему `npx vite build`, а не `npm run build`:** скрипт `build` = `tsc -b && vite build`,
а `tsc -b` уже отработал отдельным шагом. Двойной TypeScript — потеря времени
(в проекте он занимает ~40 с), а `tsc -b` инкрементален и кеширует результат.

**Step 2: Проверить локально, что команды проходят**

```bash
cd frontend
npm ci && npx tsc -b && npm run lint && npx vite build
```
Expected: всё зелёное, в `dist/` появились файлы.

**Step 3: Закоммитить**

```bash
git add .github/workflows/frontend-check.yml
git commit -m "ci(frontend): проверка типов, линта и сборки фронтенда"
```

### Task 4.3: Подключить workflow к деплою

**Objective:** прод не должен собираться, если фронтенд не проходит проверки.

**Files:**
- Modify: `.github/workflows/deploy.yml:74-76`

**Step 1: Прочитать текущий блок**

```yaml
  deploy:
    needs: [test, validate-deploy-input]
    if: always() && needs.test.result == 'success' && (github.event_name == 'push' || needs.validate-deploy-input.result == 'success')
```

**Step 2: Заменить на**

```yaml
  deploy:
    needs: [test, frontend-check, validate-deploy-input]
    if: always() && needs.test.result == 'success' && needs.frontend-check.result == 'success' && (github.event_name == 'push' || needs.validate-deploy-input.result == 'success')
```

**Внимание:** `needs` ссылается на job **в том же workflow**. `frontend-check` живёт
в другом файле (`frontend-check.yml`) — это **не сработает**: GitHub не умеет
`needs` через workflow-файлы.

Значит, фронтенд-проверку надо **перенести в `deploy.yml`** как отдельный job:

```yaml
  frontend-check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json
      - name: Install dependencies
        working-directory: frontend
        run: npm ci
      - name: Typecheck
        working-directory: frontend
        run: npx tsc -b
      - name: Lint
        working-directory: frontend
        run: npm run lint
      - name: Build
        working-directory: frontend
        run: npx vite build
```

И `frontend-check.yml` оставить как **отдельный быстрый workflow на PR** (чтобы
получать сигнал до мержа, не дожидаясь деплоя) — но тогда проверка будет
выполняться дважды. **Решение владельца:** либо только job в `deploy.yml` (одна
проверка, но сигнал только на push в main), либо оба (быстрый сигнал на PR +
обязательный перед деплоем, но двойной прогон).

**Рекомендация:** только job в `deploy.yml` + отдельный workflow на PR **без**
дублирования — сделать `frontend-check.yml` вызываемым через
`workflow_call` и переиспользовать. Это усложняет конфиг; если важна простота —
оставить только job в `deploy.yml`.

**Step 3: Проверить, что YAML валиден**

```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy.yml')); print('YAML OK')"
```

**Step 4: Закоммитить**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci(deploy): деплой только после успешной проверки фронтенда"
```

### Task 4.4: Проверить, что CI зелёный

**Step 1: Запушить ветку и открыть PR**

```bash
git checkout -b ci/frontend-check
git push -u origin ci/frontend-check
```

**Step 2: Дождаться прогона**

```bash
curl -s "https://api.github.com/repos/kirillbarashkov/dwar-rater/actions/runs?per_page=3"
```
Ожидаемый результат: `Frontend Check` — `success`.

**Примечание про доступ к API.** `api.github.com` бывает заблокирован по IP
(см. скилл `dwar-rater`, «пятый капкан»). Если curl не отвечает — подобрать
рабочий адрес и передать `--resolve`:
```bash
for ip in 140.82.112.6 140.82.121.6 140.82.114.6; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 --resolve "api.github.com:443:$ip" https://api.github.com/)
  [ "$code" = "200" ] && { API_IP=$ip; break; }
done
```

**Step 3: Проверить, что деплой на main тоже зелёный**

После мержа в main — `Deploy to Cloud.ru` должен стать `success`, а прод —
отдать новую версию.

---

## Этап 5. Финал

### Task 5.1: Обновить реестр техдолга

**Files:**
- Modify: `backend/docs/about/techdebt.md`

Для каждой из A1, A2, A3:
- в заголовке добавить `✅ ЗАКРЫТО (2026-10-20)`;
- в конце раздела — блок «Решение»: что сделано, какой файл, какой тест;
- в сводке убрать из «требуют внимания в первую очередь».

Для A4 — то же + отметить, что фронтенд теперь в CI.

### Task 5.2: Обновить скилл

**Files:**
- Modify: `C:/Users/Kirill/AppData/Local/hermes/skills/software-development/dwar-rater/references/*`

Записать:
- **A1**: `_audit()` обязан стоять **до** `commit()`; проверять — «есть ли запись
  в `audit_log` после действия», а не «вызвали ли `_audit`».
- **A2**: ручная проверка прав расходится с `require_permission` — любой новый
  эндпоинт с нестандартной авторизацией обязан переиспользовать общий хелпер.
- **A3**: все писатели в `db.Text`-колонки, которые читают через `json.loads`,
  обязаны писать через `json.dumps`.

### Task 5.3: Финальная проверка

```bash
cd backend
python3 -m pytest -q                      # ожидается 446+ passed, 0 errors
cd ../frontend
npx tsc -b                                # чисто
npm run lint                              # 0 errors (17 в warnings)
cd ..
git status --short                        # чисто
```

---

## Риски и открытые вопросы

| Риск | Как снят |
|---|---|
| Правка `require_permission` (Task 3.1) заденет все 150+ эндпоинтов | Вынесение уровня в хелпер сохраняет поведение 1-в-1; полный прогон обязателен |
| SSE-эндпоинты теперь отдают 403 JSON вместо SSE-ошибки | Фронт должен обработать 403 — Task 3.4 |
| `scope='session'` для фикстуры `app` — нельзя | A61: `test_auth.py` деактивирует `testuser`; сидинг должен быть на каждый тест |
| Baseline линта «залипнет» | Директивы/правила помечены комментарием про TD-2; при закрытии TD-2 блок удаляется |
| Двойной прогон фронтенда (PR + deploy) | Решение за владельцем: только job в `deploy.yml` либо переиспользование через `workflow_call` |
| Правка A1 меняет порядок коммитов в админских маршрутах | Атомарность улучшается, а не ухудшается: операция и след теперь в одной транзакции |

**Открытые вопросы (нужен ответ владельца):**

1. **A4 — где жить проверке фронтенда:** только job в `deploy.yml` (сигнал на push
   в main) или ещё и отдельный workflow на PR (быстрый сигнал, но двойной прогон)?
2. **A4 — формат baseline линта:** понижение правил до warning в конфиге (вариант C)
   или точечные `eslint-disable` в 12 файлах? Рекомендую C.
3. **A2 — одноразовый билет вместо токена в URL.** Находка A41 (токен в логах nginx)
   лечится одноразовым короткоживущим билетом. Это отдельная работа — в б��лок
   A1–A4 не входит, но стоит запланировать следом.

---

## Чего этот блок НЕ покрывает

- **A38, A39** (healthcheck в prod-compose, том бэкапов у бэкенда) — прод-контур,
  отдельный этап.
- **A41** (токен в логах nginx) — см. открытый вопрос 3.
- **A5–A7** (`ProxyFix`, `create_all()` как запасной путь, тестовая БД в проде) —
  тоже прод-контур, отдельным этапом.
- **A61** — уже закрыт (коммит `979e683`).
