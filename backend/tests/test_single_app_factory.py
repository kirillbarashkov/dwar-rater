"""A30: тесты идут против той же фабрики, что и прод.

Было две фабрики: `app.create_app()` (прод, 326 строк) и `test_app.create_test_app()`
(120 строк). Совпадали они не полностью: в тестовой не было части кода прода —
`session_auth` с проверкой срока сессии, `security_checks`, обработчиков ошибок.
То есть тест мог быть зелёным на приложении, которого в бою не существует.

Теперь одна фабрика: `create_app(run_startup=True)` для прода и
`create_app(run_startup=False)` для тестов. Отличие ровно одно — стартовые шаги
(миграции, сиды, создание администратора), которые в тестах делает `conftest.py`.

Тесты статические: проверяют, что второй фабрики нет и что режим без старта не
теряет того, что нужно тестам (ProxyFix, TESTING).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


def test_there_is_only_one_factory():
    app_source = _read('backend/app.py')
    assert re.search(r'^def create_app\(run_startup: bool = True\):', app_source, re.M), (
        'у фабрики снова нет режима без стартовых шагов'
    )
    assert app_source.count('def create_app') == 1, 'фабрик больше одной'

    test_source = _read('backend/test_app.py')
    assert 'create_app(run_startup=False)' in test_source, (
        'тестовое приложение снова собирается отдельной копией кода'
    )
    for duplicated in ('app.register_blueprint', '@app.before_request', 'db.init_app'):
        assert duplicated not in test_source, (
            f'test_app.py снова дублирует {duplicated} — фабрики разойдутся'
        )


def test_test_app_is_small():
    """Признак копии — рост файла: раньше он занимал 120 строк."""
    lines = _read('backend/test_app.py').count('\n')
    assert lines < 40, f'test_app.py разросся до {lines} строк — снова копия фабрики'


def test_startup_is_skipped_in_test_mode():
    source = _read('backend/app.py')
    block = source.split('if not run_startup:')[1][:400]
    assert 'install_proxy_fix(app)' in block, (
        'в тестовом режиме теряется ProxyFix — тесты перестанут видеть реальный IP'
    )
    assert 'return app' in block, 'фабрика продолжает стартовые шаги в тестах'


def test_prod_factory_keeps_startup_by_default():
    source = _read('backend/app.py')
    assert 'run_startup: bool = True' in source, 'по умолчанию прод лишится миграций'
    assert 'app = create_app()' in source, (
        'модульный экземпляр приложения (нужен gunicorn) собирается не по умолчанию'
    )
