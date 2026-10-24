"""A15: аудит аутентификации должен попадать в БД, а не теряться.

Тот же класс, что A1: `_audit()` только добавляет запись в сессию. Если после
неё нет `commit()` до `return`, сессия снимается при завершении запроса и запись
исчезает. В `features/auth/routes.py` так было в семи местах, включая вход:
журнал входов оказывался пустым, хотя при `login` в него кладётся ещё и IP.

Тесты проверяют последствие (есть ли строка в `audit_log`), а не факт вызова.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.rbac.models import AuditLog


def _count(app, action):
    with app.app_context():
        return AuditLog.query.filter_by(action=action).count()


def test_successful_login_is_audited(app, client):
    before = _count(app, 'login')

    resp = client.post('/api/auth/login', json={'username': 'admin', 'password': 'testpass'})
    assert resp.status_code == 200, resp.get_data(as_text=True)

    assert _count(app, 'login') == before + 1, (
        'вход не оставил записи в audit_log — _audit() без commit()'
    )


def test_logout_is_audited(app, client):
    login = client.post('/api/auth/login', json={'username': 'admin', 'password': 'testpass'})
    token = login.get_json()['token']

    before = _count(app, 'logout')
    resp = client.post('/api/auth/logout', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200, resp.get_data(as_text=True)

    assert _count(app, 'logout') == before + 1, (
        'выход не оставил записи в audit_log'
    )


def test_every_audit_call_commits_before_return():
    """Страж на весь модуль: все 7 мест A15 были именно такой формы.

    Проверяет исходник, а не поведение — иначе каждый из семи эндпоинтов
    (2FA, смена пароля, refresh и т.д.) пришлось бы поднимать в тесте целиком.
    """
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'features', 'auth', 'routes.py')
    lines = [l.rstrip('\r') for l in open(path, encoding='utf-8').read().split('\n')]

    offenders = []
    for i, line in enumerate(lines):
        if not re.match(r'\s*_audit\(', line):
            continue
        depth, j = 0, i
        while j < len(lines):
            depth += lines[j].count('(') - lines[j].count(')')
            if depth <= 0:
                break
            j += 1
        k, committed = j + 1, False
        while k < len(lines) and not re.match(r'^(def |@)', lines[k]):
            if 'db.session.commit()' in lines[k]:
                committed = True
                break
            if re.match(r'\s+return\b', lines[k]):
                break
            k += 1
        if not committed:
            offenders.append(i + 1)

    assert not offenders, (
        f'Аудит без commit() до return в строках {offenders} — записи будут '
        'потеряны при закрытии сессии'
    )
