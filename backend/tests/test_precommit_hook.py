"""TD-8: хук коммита проверяет рабочее дерево, а не запечённый образ.

Дефект (2026-10-11): `.git/hooks/pre-commit` делал
`docker exec <dev-backend> python -m pytest`, то есть гонял тесты внутри уже
собранного образа. Образ несёт только тот код и те тесты, что были на момент
сборки, поэтому правки рабочего дерева хук не видел: новый тест в прогон не
попадал, счётчик не рос, «все тесты прошли» относилось к старому коду
(false green). Вдобавок хук был написан так, что при падении всё равно
завершался `exit 0`.

Скрипт `scripts/run_backend_tests.sh` для честного прогона существовал, но хук
его не использовал. Вторая половина долга — сам скрипт: он копировал в контейнер
только `backend/`, поэтому 24 статических теста, читающих `frontend/src`,
`README.md`, `Makefile`, `.github/workflows` и `docker-compose*.yml`, падали
`FileNotFoundError` (проверено: `test_theme_tokens.py` — 2 failed из 4). Хук на
таком скрипте блокировал бы любой коммит ложным красным.

Инварианты: хук делегирует скрипту, скрипт разворачивает в контейнере раскладку
репозитория (ROOT тестов = корень репозитория, как в CI), падение тестов хук
не пропускает.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HOOK = os.path.join(ROOT, 'backend', 'hooks', 'pre-commit')
SCRIPT = os.path.join(ROOT, 'scripts', 'run_backend_tests.sh')


def _read(path):
    return open(path, encoding='utf-8').read()


def _shell_code(text):
    """Снять комментарии: в них упоминаются и `docker exec`, и путь к скрипту."""
    return '\n'.join(
        line for line in text.split('\n') if not line.strip().startswith('#')
    )


def test_hook_delegates_to_the_working_tree_script():
    source = _read(HOOK)
    assert 'scripts/run_backend_tests.sh' in _shell_code(source), (
        'хук не использует прогон по рабочему дереву'
    )
    assert 'docker exec' not in _shell_code(source), (
        'хук снова гоняет тесты внутри готового контейнера — это запечённый код'
    )


def test_hook_does_not_swallow_failures():
    source = _shell_code(_read(HOOK))
    assert 'exit 1' in source, 'нет пути, где падение тестов останавливает коммит'
    assert '--no-verify' in _read(HOOK), (
        'не описан штатный обход для коммитов без прогона (документация/CI-only)'
    )


def test_hook_skips_markdown_only_commits():
    source = _shell_code(_read(HOOK))
    assert 'git diff --cached --name-only' in source, (
        'хук не смотрит, что попадёт в коммит: прогон на 11 минут запускается и '
        'для правки в реестре'
    )
    assert 'ONLY_DOCS' in source, 'нет ветки пропуска для коммитов из одних текстов'
    assert 'README.md' in source, (
        'README.md читают тесты (test_readme_*): он не может считаться «просто текстом»'
    )


def test_hook_has_no_crlf():
    assert b'\r' not in open(HOOK, 'rb').read(), (
        'CRLF в shebang-скрипте: git запускает хук напрямую, bash получит '
        '`bash\\r` и хук молча не выполнится'
    )


def test_script_stages_repository_layout():
    source = _read(SCRIPT)
    assert 'set -euo pipefail' in source
    assert ':/repo:ro' in source, 'корень репозитория не смонтирован в контейнер'
    assert 'cp -r /repo/backend/.' in source, 'нет копии рабочего дерева backend'
    assert 'for item in frontend .github scripts' in source, (
        'каталоги, которые читают статические тесты, не проброшены: '
        '.tsx-проверки упадут FileNotFoundError'
    )
    assert 'rm -rf "/app/$item"' in source, (
        'ссылка в существующий каталог образа (/app/scripts) создаётся ВНУТРИ него, '
        'и файлы остаются невидимыми'
    )
    assert 'cd /app/backend' in source, (
        'ROOT тестов не совпадёт с корнем репозитория — часть тестов ищет '
        'frontend/, README.md, Makefile от трёх уровней вверх'
    )
    assert '/src:ro' not in source, 'остался старый mount только с backend/'
