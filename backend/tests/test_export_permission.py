"""A64: переключатель `export:read` в матрице прав действительно управляет экспортом.

Было:

```python
@feature('export', [PermDef('read', 'Экспорт аналитики', 'POST /api/export/character')])
@export_bp.route('/api/export/character', methods=['POST'])
@require_permission('analyze', 'read')       # ← фактический гейт
def export_character():
```

Право `export:read` объявлено, показывается в матрице админки, переключатель
двигается, значение сохраняется в `role_permissions` — и ни на что не влияет:
декоратор ближе к функции выполняется первым, а он проверял `analyze:read`.
То есть админ мог сколько угодно выключать экспорт, и это ничего не меняло.

Почему это не просто «мёртвая настройка»: `/api/export/character` отдаёт полную
аналитику персонажа файлом — выключать это право и не иметь эффекта значит
считать, что доступ отозван, когда он не отозван.

Решение: гейт — `require_permission('export', 'read')`; право добавлено в
`PERMISSIONS` и выдано admin/superuser/user (`full`) в seed, чтобы поведение не
изменилось для тех, кому экспорт был доступен (сегодня его мог любой с
`analyze:read`). Seed идемпотентен и досоздаёт строки при старте, поэтому
отдельная миграция не нужна.

Тесты используют seeded-роли: у `user` экспорт есть по умолчанию, а отзыв права
обязан его закрыть.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db  # noqa: E402
from shared.rbac.models import Permission as PermModel, Role, RolePermission  # noqa: E402

PAYLOAD = {
    'format': 'markdown',
    'sections': ['identity'],
    'data': {'name': 'Тест', 'main_stats': {}, 'characteristics': {}},
}


def _token(client, username, password='testpass'):
    response = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert response.status_code == 200, response.get_json()
    return response.get_json()['token']


def _set_role_level(app, role_name, feature, action, level):
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        perm = PermModel.query.filter_by(feature=feature, action=action).first()
        assert role and perm, f'нет роли {role_name} или права {feature}:{action}'
        row = RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first()
        if row is None:
            row = RolePermission(role_id=role.id, permission_id=perm.id, level=level)
            db.session.add(row)
        else:
            row.level = level
        db.session.commit()
        return level


def test_plain_user_can_export_by_default(client):
    token = _token(client, 'testuser')
    response = client.post(
        '/api/export/character', json=PAYLOAD, headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200, response.get_json()
    assert 'attachment' in response.headers['Content-Disposition']


def test_revoking_export_read_closes_the_endpoint(app, client):
    """Главное доказательство: переключатель в матрице теперь что-то делает."""
    _set_role_level(app, 'user', 'export', 'read', 'none')
    token = _token(client, 'testuser')
    response = client.post(
        '/api/export/character', json=PAYLOAD, headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403, (
        'экспорт всё ещё открыт при отозванном export:read — гейт держится на другой фиче'
    )


def test_analyze_read_alone_does_not_grant_export(app, client):
    """Обратный случай: analyze:read без export:read экспорт не открывает."""
    _set_role_level(app, 'user', 'export', 'read', 'none')
    _set_role_level(app, 'user', 'analyze', 'read', 'full')
    token = _token(client, 'testuser')
    response = client.post(
        '/api/export/character', json=PAYLOAD, headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403, 'правом analyze:read снова можно экспортировать'


def test_admin_keeps_export_after_defaults(client):
    token = _token(client, 'admin')
    response = client.post(
        '/api/export/character', json=PAYLOAD, headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 200, response.get_json()


def test_seed_declares_the_permission_for_every_role_that_had_it_before():
    """Поведение не должно измениться молча: export:read выдан тем же ролям."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    seed = open(os.path.join(root, 'backend', 'shared', 'rbac', 'seed.py'), encoding='utf-8').read()
    for role in ('admin', 'superuser', 'user'):
        assert f"('{role}', 'export', 'read', 'full')" in seed, (
            f'{role} потерял экспорт при переходе на export:read'
        )
    routes = open(os.path.join(root, 'backend', 'features', 'export', 'routes.py'), encoding='utf-8').read()
    assert "@require_permission('export', 'read')" in routes
    assert "@require_permission('analyze', 'read')\ndef export_character" not in routes
