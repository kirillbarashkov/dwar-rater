"""A26: чтение казны — одна группа прав, `treasury:read`.

Было две матрицы на одни данные: журнал/пары/займы/месяцы требовали
`treasury:read` (а у роли `user` его нет вовсе), а сводка, итоги, аномалии и
**экспорт всей казны** — только `clan_info:read`, который у `user` есть.
То есть обычный пользователь не видел журнал, но мог выгрузить казну целиком.

Почему унификация именно под `treasury:read`, а не под `clan_info:read`:
* `shared/rbac/seed.py` — у `treasurer` есть `treasury:read/write/approve`, у
  `user` нет **ни одного** `treasury:*`;
* `frontend/src/components/layout/Sidebar.tsx:88` уже прячет раздел казны по
  `usePermission('treasury', 'read')` — то есть UI и так считает казну отдельной
  группой, а API был либеральнее интерфейса.

Тесты проверяют и раскладку в коде, и фактический доступ на живом приложении.
"""

import os
import re
import sys
import secrets
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.user import User
from shared.rbac.models import SessionToken

CLAN = 987411
ROUTES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'features', 'clan_info', 'routes.py',
)


def _login(app, username, role):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, password_hash='x', role=role, is_active=True)
            db.session.add(user)
            db.session.commit()
        token = secrets.token_hex(32)
        db.session.add(SessionToken(
            user_id=user.id,
            token_hash=SessionToken.hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        db.session.commit()
        return token


def _headers(token):
    return {'Authorization': f'Bearer {token}'}


def _treasury_routes_with_permission():
    """(путь, метод, право) для всех маршрутов с 'treasury' в пути."""
    lines = open(ROUTES_FILE, encoding='utf-8').read().split('\n')
    result = []
    for i, line in enumerate(lines):
        match = re.match(r'\s*@\w+\.route\((.*)', line)
        if not match or 'treasury' not in match.group(1):
            continue
        path = re.search(r"['\"]([^'\"]+)['\"]", match.group(1))
        if not path:
            continue
        methods = re.search(r'methods=\[([^\]]*)\]', match.group(1))
        verbs = re.findall(r"['\"](\w+)['\"]", methods.group(1)) if methods else ['GET']
        perm = None
        for k in range(i + 1, min(i + 9, len(lines))):
            found = re.search(
                r"require_permission\(\s*['\"](\w+)['\"]\s*,\s*['\"](\w+)['\"]", lines[k]
            )
            if found:
                perm = (found.group(1), found.group(2))
                break
        result.append((path.group(1), verbs, perm))
    return result


AGGREGATES = ('/treasury/summary', '/treasury/totals', '/treasury/anomalies', '/treasury/date-coverage')


def test_aggregates_stay_readable_for_every_role():
    """Сводка и аномалии — агрегаты без деталей; их читает и обычный пользователь.

    Это зафиксировано тестами продукта
    (`test_summary_is_readable_by_a_plain_user`, `test_report_is_readable_by_a_plain_user`),
    поэтому агрегаты остаются на `clan_info:read`.
    """
    offenders = []
    for path, verbs, perm in _treasury_routes_with_permission():
        if 'GET' not in verbs or not path.endswith(AGGREGATES):
            continue
        if perm != ('clan_info', 'read'):
            offenders.append(f'{path} — {perm}')
    assert not offenders, 'агрегаты казны закрылись для обычных ролей:\n' + '\n'.join(offenders)


def test_detailed_treasury_data_requires_treasury_permission():
    """Детальные данные (операции, журнал, пары, займы, месяцы, экспорт) — казначейские."""
    offenders = []
    for path, verbs, perm in _treasury_routes_with_permission():
        if 'GET' not in verbs or path.endswith(AGGREGATES):
            continue
        if perm is None:
            offenders.append(f'{path} — без проверки прав')
        elif perm[0] != 'treasury':
            offenders.append(f'{path} — {perm[0]}:{perm[1]}')
    assert not offenders, 'детальные данные казны под чужой группой прав:\n' + '\n'.join(offenders)


def test_writes_are_not_downgraded_to_read():
    """Запись обязана требовать write/approve/admin, а не read."""
    offenders = []
    for path, verbs, perm in _treasury_routes_with_permission():
        if not ({'POST', 'PUT', 'PATCH', 'DELETE'} & set(verbs)):
            continue
        if perm is None:
            continue
        if perm[0] != 'treasury' or perm[1] == 'read':
            offenders.append(f'{path} — {perm[0]}:{perm[1]}')
    assert not offenders, 'изменяющие маршруты казны с недостаточным правом:\n' + '\n'.join(offenders)


def test_regular_user_reads_aggregates_but_not_details(app, client):
    """Роль `user`: сводка и аномалии — да, операции и экспорт — нет."""
    token = _login(app, 'a26_plain_user', 'user')

    for endpoint in ('/summary', '/anomalies', '/totals'):
        response = client.get(f'/api/clan/{CLAN}/treasury{endpoint}', headers=_headers(token))
        assert response.status_code not in (401, 403), (
            f'агрегат {endpoint} закрылся для обычного пользователя: {response.status_code}'
        )

    for endpoint in ('', '/journal', '/pairs', '/months', '/export', '/backups'):
        response = client.get(f'/api/clan/{CLAN}/treasury{endpoint}', headers=_headers(token))
        assert response.status_code == 403, (
            f'деталь {endpoint or "/"} отдана роли user: {response.status_code}'
        )


def test_treasurer_still_reads_treasury(app, client):
    """Казначей — рабочая роль: чтение обязано остаться.

    Проверяем именно отказ доступа (401/403), а не 200: часть эндпоинтов казны
    требует обязательных query-параметров и отвечает 400 — это не проблема прав.
    """
    token = _login(app, 'a26_treasurer', 'treasurer')

    for endpoint in ('', '/summary', '/totals', '/journal', '/months', '/pairs'):
        response = client.get(f'/api/clan/{CLAN}/treasury{endpoint}', headers=_headers(token))
        assert response.status_code not in (401, 403), (
            f'{endpoint or "/"} закрылся для казначея: {response.status_code}'
        )
