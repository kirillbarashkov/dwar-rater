#!/usr/bin/env bash
# Прогон тестов бэкенда по РАБОЧЕМУ дереву, а не по запечённому в образ коду.
#
# Зачем скрипт: образ backend несёт только те код и тесты, которые были в момент
# сборки. Любой прогон внутри готового контейнера проверяет старое дерево, а
# `-v`-монтирование решает это лишь частично: без нужных КОПИЙ тестовая фабрика и
# каталоги остаются запечёнными.
#
# Две строки копирования, которые обязательно должны быть в списке:
#   * test_app.py — тестовая фабрика. Без неё новый blueprint не регистрируется,
#     эндпоинт отвечает 404 и падают даже чужие тесты (симптом — ошибка в setup
#     файла, которого ты не касался);
#   * docs/ — openapi.yaml и markdown-документы, которые читает рантайм.
#
# Копируем КАТАЛОГИ ЦЕЛИКОМ (tests/, shared/, features/, migrations/, docs/):
# забытый файл не падает громко — тест либо проходит на старом коде, либо ловит
# ImportError на сборе.
#
# Usage: bash scripts/run_backend_tests.sh [аргументы pytest одним токеном]
#   bash scripts/run_backend_tests.sh "tests/test_treasury_pairs.py"
#   bash scripts/run_backend_tests.sh "-k corrects"
# Внимание: аргументы передаются как $* — фраза с пробелами и `or` («-k \"a or b\"»)
# разваливается, pytest увидит `or` как путь к тесту. Передавай один токен.
set -euo pipefail

cd "$(dirname "$0")/.."

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
  -v "$(pwd)/backend:/src:ro" backend \
  -c 'cp -r /src/tests/. /app/tests/ && cp -r /src/shared/. /app/shared/ && cp -r /src/features/. /app/features/ && cp -r /src/migrations/. /app/migrations/ && cp -r /src/docs/. /app/docs/ && cp /src/app.py /app/app.py && cp /src/test_app.py /app/test_app.py && cd /app && python -m pytest -q -p no:randomly '"$*"
