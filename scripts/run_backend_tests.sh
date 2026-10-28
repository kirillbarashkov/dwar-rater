#!/usr/bin/env bash
# Прогон тестов бэкенда по РАБОЧЕМУ дереву, а не по запечённому в образ коду.
#
# Зачем скрипт: образ backend несёт только тот код и те тесты, что были в момент
# сборки. Любой прогон внутри готового контейнера (`docker exec … pytest`)
# проверяет старое дерево: новый тест в прогон не попадает, счётчик не растёт,
# «все тесты прошли» относится к прошлой сборке (TD-8).
#
# Раскладка внутри контейнера повторяет CI: корень репозитория = `/app`,
# `backend/` — копия рабочего дерева, поэтому ROOT в статических тестах
# (`dirname(dirname(dirname(__file__)))`) совпадает с корнем, и тесты, читающие
# `frontend/src`, `README.md`, `Makefile`, `.github/workflows` и
# `docker-compose*.yml`, видят рабочее дерево. Копировать только `backend/`
# нельзя: 24 статических теста падают `FileNotFoundError`, и гейт краснеет
# ложным красным (проверено на `test_theme_tokens.py` — 2 failed из 4).
#
# Копируем backend КАТАЛОГОМ ЦЕЛИКОМ, включая `test_app.py` (тестовая фабрика:
# без неё новый blueprint не регистрируется и падают чужие тесты) и `docs/`
# (openapi.yaml и markdown-документы, которые читает рантайм).
#
# Usage: bash scripts/run_backend_tests.sh [аргументы pytest одним токеном]
#   bash scripts/run_backend_tests.sh "tests/test_treasury_pairs.py"
#   bash scripts/run_backend_tests.sh "-k corrects"
# Внимание: аргументы передаются одной строкой — фраза с пробелами и `or`
# («-k "a or b"») разваливается, pytest увидит `or` как путь к тесту.
# Передавай один токен.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_DIR="$(pwd)"

if [[ ! -f .env ]]; then
  echo "error: .env не найден — запускай из корня репозитория (нужны POSTGRES_USER/POSTGRES_PASSWORD)" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

docker compose run --rm --no-deps --entrypoint bash \
  -e TEST_DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/dwar_rater_test" \
  -e PYTEST_ARGS="${*:-}" \
  -v "${REPO_DIR}:/repo:ro" backend \
  -c '
set -euo pipefail

mkdir -p /app/backend
cp -r /repo/backend/. /app/backend/

# Файлы, которые статические тесты читают от корня репозитория.
for item in README.md Makefile VERSION Dockerfile.postgres \
            docker-compose.yml docker-compose.prod.yml; do
  if [ -f "/repo/$item" ]; then cp "/repo/$item" /app/; fi
done

# Каталоги целиком — символическими ссылками на read-only монтирование:
# писать в них не нужно, а копировать frontend (node_modules) — минуты впустую.
# `rm -rf` обязателен: `ln -sfn` в существующий каталог образа (/app/scripts)
# кладёт ссылку ВНУТРЬ него, и файлы остаются невидимыми.
for item in frontend .github scripts; do
  if [ -d "/repo/$item" ]; then
    rm -rf "/app/$item"
    ln -s "/repo/$item" "/app/$item"
  fi
done

cd /app/backend
# PYTEST_ARGS намеренно без кавычек: аргументы — одна строка для pytest.
python -m pytest -q -p no:randomly $PYTEST_ARGS
'
