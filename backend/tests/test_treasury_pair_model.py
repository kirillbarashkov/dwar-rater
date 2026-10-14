"""Модель пар казны: значения по умолчанию и связи.

Этап 1 классификации выкатывается отдельно от изменения расчётов, поэтому тест
фиксирует главное свойство: операция без классификации учитывается (`op_class='tax'`),
а пара начинается кандидатом и требует подтверждения казначеем.
"""

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    TreasuryOperation,
    TreasuryOperationPair,
    TreasuryPairRevision,
)

CLAN = 987003  # dedicated id, not shared with other test modules


def _seed(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="PairClan"))
            db.session.commit()


def test_operation_defaults_to_tax(app):
    """Без классификации операция учитывается — цифры не меняются."""
    _seed(app)
    with app.app_context():
        op = TreasuryOperation(
            clan_id=CLAN,
            date='01.10.2026',
            nick='__PairProbe__',
            operation_type='Деньги',
            object_name='Монеты',
            quantity=100,
        )
        db.session.add(op)
        db.session.commit()

        assert op.op_class == 'tax'
        assert op.class_kind == ''
        assert op.class_source == ''


def test_pair_starts_as_candidate_and_links_operations(app):
    """Автоматика предлагает пару, но не решает: статус candidate, подтверждения нет."""
    _seed(app)
    with app.app_context():
        op1 = TreasuryOperation(
            clan_id=CLAN,
            date='01.10.2026',
            nick='__PairProbe__',
            operation_type='Деньги',
            object_name='Монеты',
            quantity=100,
        )
        op2 = TreasuryOperation(
            clan_id=CLAN,
            date='01.10.2026',
            nick='__PairProbe__',
            operation_type='Предмет',
            object_name='Сущность Гальфиды',
            quantity=-5,
        )
        db.session.add_all([op1, op2])
        db.session.commit()

        pair = TreasuryOperationPair(
            clan_id=CLAN, first_op_id=op1.id, second_op_id=op2.id, kind='exchange'
        )
        db.session.add(pair)
        db.session.commit()

        assert pair.status == 'candidate'
        assert pair.confirmed_at is None
        # Связи разрешаются — по ним интерфейс будет показывать пару целиком.
        assert pair.first_op.id == op1.id
        assert pair.second_op.id == op2.id


def test_pair_revision_is_recorded(app):
    """Лог корректировок: требование владельца — история изменений сохраняется."""
    _seed(app)
    with app.app_context():
        op1 = TreasuryOperation(clan_id=CLAN, date='02.10.2026', nick='__PairProbe__')
        op2 = TreasuryOperation(clan_id=CLAN, date='03.10.2026', nick='__PairProbe__')
        db.session.add_all([op1, op2])
        db.session.commit()

        pair = TreasuryOperationPair(
            clan_id=CLAN, first_op_id=op1.id, second_op_id=op2.id, kind='loan'
        )
        db.session.add(pair)
        db.session.commit()

        rev = TreasuryPairRevision(
            pair_id=pair.id,
            old_value='{"kind": "exchange"}',
            new_value='{"kind": "loan"}',
            comment='переклассифицировано в долг',
        )
        db.session.add(rev)
        db.session.commit()

        assert rev.id is not None
        assert rev.pair_id == pair.id
