"""Группы исключений казны: правила, режимы и применение к операциям."""

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    TreasuryExclusionGroup,
    TreasuryExclusionRule,
    TreasuryOperation,
)
from shared.rbac.models import AuditLog
from shared.services.treasury_exclusions import (
    apply_exclusions,
    group_as_dict,
    match_group,
    rule_matches,
)

CLAN = 987008  # dedicated id, not shared with other test modules


def _group(app, name='Тест', mode='exclude', prefixes=('Сущность',)):
    with app.app_context():
        group = TreasuryExclusionGroup(clan_id=CLAN, name=name, mode=mode)
        db.session.add(group)
        db.session.flush()
        for prefix in prefixes:
            db.session.add(TreasuryExclusionRule(group_id=group.id, prefix=prefix))
        db.session.commit()
        return group.id


def _op(app, object_name, op_class='tax', class_source=''):
    with app.app_context():
        # treasury_operations.clan_id — внешний ключ на clan_info, без клана вставка падает.
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name='ExclClan'))
            db.session.commit()

        op = TreasuryOperation(
            clan_id=CLAN,
            date='01.10.2026',
            nick='__ExclProbe__',
            operation_type='Предмет',
            object_name=object_name,
            quantity=1,
            op_class=op_class,
            class_source=class_source,
        )
        db.session.add(op)
        db.session.commit()
        return op.id


def test_rule_matches_by_prefix_only():
    assert rule_matches('Сущность', 'Сущность кретса') is True
    assert rule_matches('сущность', 'СУЩНОСТЬ корра') is True
    assert rule_matches('Сущность', 'Дар сущности') is False
    assert rule_matches('', 'Сущность кретса') is False


def test_match_group_picks_matching_group(app):
    _group(app)
    with app.app_context():
        groups = TreasuryExclusionGroup.query.filter_by(clan_id=CLAN).all()
        assert match_group(groups, 'Сущность кретса') is not None
        assert match_group(groups, 'Золотая шамса') is None


def test_exclude_mode_marks_operation_excluded(app):
    _group(app, mode='exclude')
    op_id = _op(app, 'Сущность кретса')

    with app.app_context():
        groups = TreasuryExclusionGroup.query.filter_by(clan_id=CLAN).all()
        operations = TreasuryOperation.query.filter_by(clan_id=CLAN).all()
        changed = apply_exclusions(operations, groups)
        db.session.commit()

        assert changed >= 1
        op = db.session.get(TreasuryOperation, op_id)
        assert op.op_class == 'excluded'
        assert op.class_source == 'group'


def test_neutral_mode_marks_operation_neutral(app):
    # Префикс отличается от групп других тестов: они делят один клан, а выигрывает
    # первая подходящая группа.
    _group(app, name='Мягкие', mode='neutral', prefixes=('Нейтральный ресурс',))
    op_id = _op(app, 'Нейтральный ресурс А')

    with app.app_context():
        groups = TreasuryExclusionGroup.query.filter_by(clan_id=CLAN).all()
        operations = TreasuryOperation.query.filter_by(clan_id=CLAN).all()
        apply_exclusions(operations, groups)
        db.session.commit()

        op = db.session.get(TreasuryOperation, op_id)
        assert op.op_class == 'neutral'
        assert op.class_kind == 'group'


def test_manual_decision_is_not_overwritten(app):
    """Правило группы не должно отменять решение казначея."""
    _group(app, mode='exclude')
    op_id = _op(app, 'Сущность кретса', op_class='neutral', class_source='manual')

    with app.app_context():
        groups = TreasuryExclusionGroup.query.filter_by(clan_id=CLAN).all()
        operations = TreasuryOperation.query.filter_by(clan_id=CLAN).all()
        apply_exclusions(operations, groups)
        db.session.commit()

        op = db.session.get(TreasuryOperation, op_id)
        assert op.op_class == 'neutral'
        assert op.class_source == 'manual'


def test_group_as_dict_includes_rules(app):
    group_id = _group(app)
    with app.app_context():
        group = db.session.get(TreasuryExclusionGroup, group_id)
        data = group_as_dict(group)
        assert data['name'] == 'Тест'
        assert data['mode'] == 'exclude'
        assert [rule['prefix'] for rule in data['rules']] == ['Сущность']


def test_add_rule_endpoint_excludes_object(client, admin_headers, app):
    """Правая кнопка в очереди пар: объект уходит в группу, правила применяются сразу."""
    group_id = _group(app, name='Правый клик', prefixes=('Другое',))
    op_id = _op(app, 'Сущность корра')

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/exclusions/{group_id}/rules",
        json={'prefix': 'Сущность корра'},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data['changed'] >= 1
    assert any(rule['prefix'] == 'Сущность корра' for rule in data['group']['rules'])

    with app.app_context():
        op = db.session.get(TreasuryOperation, op_id)
        assert op.op_class == 'excluded'
        actions = {entry.action for entry in AuditLog.query.filter_by(clan_id=CLAN).all()}
        assert 'treasury_exclusion_rule_add' in actions


def test_add_rule_endpoint_rejects_duplicate(client, admin_headers, app):
    group_id = _group(app, name='Дубли', prefixes=('Сущность',))

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/exclusions/{group_id}/rules",
        json={'prefix': 'Сущность'},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert 'уже в группе' in resp.get_json()['error']


def test_add_rule_endpoint_requires_prefix(client, admin_headers, app):
    group_id = _group(app, name='Пусто', prefixes=())

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/exclusions/{group_id}/rules",
        json={},
        headers=admin_headers,
    )
    assert resp.status_code == 400


def test_add_rule_endpoint_unknown_group(client, admin_headers, app):
    resp = client.post(
        f"/api/clan/{CLAN}/treasury/exclusions/999999/rules",
        json={'prefix': 'Что-то'},
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_create_group_applies_rules_immediately(client, admin_headers, app):
    """Сохранение группы сразу пересчитывает операции.

    Иначе группа выглядит нерабочей: казначей её сохранил, а в казне ничего не
    изменилось, пока он не нажмёт отдельную «Применить правила».
    """
    op_id = _op(app, 'Сущность кретса')

    resp = client.post(
        f"/api/clan/{CLAN}/treasury/exclusions",
        json={'name': 'Сразу', 'mode': 'exclude', 'prefixes': ['Сущность']},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()['changed'] >= 1

    with app.app_context():
        assert db.session.get(TreasuryOperation, op_id).op_class == 'excluded'


def test_update_group_applies_rules(client, admin_headers, app):
    """Правка группы тоже применяется сразу — иначе настройки не доходят до казны."""
    group_id = _group(app, name='Правка', prefixes=())
    op_id = _op(app, 'Сущность корра')

    resp = client.put(
        f"/api/clan/{CLAN}/treasury/exclusions/{group_id}",
        json={'prefixes': ['Сущность']},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()['changed'] >= 1

    with app.app_context():
        assert db.session.get(TreasuryOperation, op_id).op_class == 'excluded'
