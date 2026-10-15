"""Группы исключений казны: правила, режимы и применение к операциям."""

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    TreasuryExclusionGroup,
    TreasuryExclusionRule,
    TreasuryOperation,
)
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
