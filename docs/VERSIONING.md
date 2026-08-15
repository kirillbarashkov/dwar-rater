# Версионирование деплоев (модель «Git-bump в CI»)

Реализовано по плану `development-roadmap/versioning-deploy-fix-plan.md` (2026-07-24).

## Как это работает

```
push в main → тесты → деплой на VM (build с args) → health-check →
бамп VERSION в CI → commit "chore(release): vX.Y.Z [skip ci]" → тег vX.Y.Z → push в main
```

Релизный коммит содержит `[skip ci]` — GitHub Actions не запускает его повторно
(плюс guard на `chore(release)` в job `test` для надёжности).

## Единый источник правды

| Файл | Роль |
|---|---|
| `VERSION` (корень репо) | **Канон.** Бампается только CI (или dev-CLI). Вручную не править |
| `frontend/package.json` → `version` | Sync-точка: обновляется CI автоматически вместе с `VERSION` (через jq). Вручную не править |
| `backend/docs/openapi.yaml` → `info.version` | Статичная схема: синхронизировать вручную при релизе, если менялась схема |

## Версия в рантайме (env-first)

`backend/shared/utils/version.py`:
- `read_version()`: `APP_VERSION` env → файл `VERSION` → `'0.0.0'`
- `read_git_hash()`: `APP_GIT_HASH` env → git (локалка) → `'unknown'`
- `read_branch()`: `APP_BRANCH` env → git → `'unknown'`
- `read_build_date()`: `APP_BUILD_DATE` env → mtime `VERSION` → now UTC

Инъекция при сборке:
- `backend/Dockerfile`: `ARG`/`ENV` `APP_VERSION`, `APP_GIT_HASH`, `APP_BRANCH`, `APP_BUILD_DATE`
- `frontend/Dockerfile` + `Dockerfile.prod`: `ARG APP_VERSION` → `ENV VITE_APP_VERSION` (build-time)
- `docker-compose*.yml`: секции `build.args` читают `${APP_VERSION:-dev}` и др. из окружения
- CI передаёт их на VM через `envs:` SSH-action и `export` в скрипте деплоя

В Header UI: версия из `VITE_APP_VERSION` (build-time), tooltip (build_date/git_hash/branch) —
через axios `client` к `GET /api/version` (без raw fetch, с auth-интерцептором).

## Правила бампа

- push в main: patch по умолчанию; `minor`/`major` — если PR имеет label `bump:minor` / `bump:major`
- `workflow_dispatch` (хотфикс): выбор `bump_part` (default patch)
- Идемпотентность: если тег `vX.Y.Z` уже существует — шаг релиза молча пропускается (safe re-run)
- Откатов нет: миграции forward-only, теги не пересоздаются

## Dev-CLI (не рантайм)

```bash
cd backend
python -m shared.utils.version          # показать текущую информацию
python -m shared.utils.version patch    # локальный бамп (только для dev-экспериментов)
```

`bump_version()` осталась как util для dev-CLI; из HTTP-путей удалена.

## Что было удалено (мёртвый код)

- `frontend/src/components/layout/DeployModal.tsx` + `.css` — мёртвый UI деплоя
- `POST /api/version/bump` — рантайм-бамп
- `POST /api/admin/deploy`, `GET /api/admin/deploy/status` — runtime-деплой через GitHub API
- `GITHUB_TOKEN` / `GITHUB_REPO` из `docker-compose.prod.yml` и контейнера — больше не нужны (CI использует встроенный `GITHUB_TOKEN`)

Остался только публичный `GET /api/version`.

## Тесты

`backend/tests/test_version.py` (13 тестов): env-priority для всех четырёх полей,
fallback'и, публичность `/api/version`, 404 на удалённые эндпоинты, dev-CLI `bump_version`.
