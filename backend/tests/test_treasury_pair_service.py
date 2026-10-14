"""Пары казны: подтверждение меняет op_class операций, корректировки логируются."""

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    TreasuryOperation,
    TreasuryOperationPair,
    TreasuryPairRevision,
)
from shared.services.treasury_pair_service import (
    PairError,
    confirm_pair,
    pair_as_dict,
    reject_pair,
    revise_pair,
    unconfirm_pair,
)

CLAN = 987004  # dedicated id, not shared with other test modules


def _setup(app):
    """Клан, две операции (деньги и ресурс) и пара-кандидат между ними."""
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="SvcClan"))
            db.session.commit()

        op1 = TreasuryOperation(
            clan_id=CLAN,
            date='01.10.2026',
            nick='__SvcProbe__',
            operation_type='Деньги',
            object_name='Монеты',
            quantity=100,
        )
        op2 = TreasuryOperation(
            clan_id=CLAN,
            date='01.10.2026',
            nick='__SvcProbe__',
            operation_type='Предмет',
            object_name='Ресурс',
            quantity=-5,
        )
        db.session.add_all([op1, op2])
        db.session.commit()

        pair = TreasuryOperationPair(
            clan_id=CLAN, first_op_id=op1.id, second_op_id=op2.id
        )
        db.session.add(pair)
        db.session.commit()
        return pair.id


def test_confirm_makes_operations_neutral(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        confirm_pair(pair, 'exchange', user_id=1)
        db.session.commit()

        op1 = db.session.get(TreasuryOperation, pair.first_op_id)
        op2 = db.session.get(TreasuryOperation, pair.second_op_id)
        assert op1.op_class == 'neutral'
        assert op2.op_class == 'neutral'
        assert op1.class_kind == 'exchange'
        assert op1.class_source == 'manual'
        assert pair.confirmed_at is not None


def test_unconfirm_returns_operations_to_tax(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        confirm_pair(pair, 'loan', user_id=1)
        db.session.commit()

        unconfirm_pair(pair)
        db.session.commit()

        op1 = db.session.get(TreasuryOperation, pair.first_op_id)
        assert op1.op_class == 'tax'
        assert op1.class_kind == ''
        assert pair.confirmed_at is None


def test_reject_keeps_operations_tax(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        reject_pair(pair)
        db.session.commit()

        op1 = db.session.get(TreasuryOperation, pair.first_op_id)
        assert op1.op_class == 'tax'
        assert pair.status == 'rejected'


def test_revise_writes_log(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        confirm_pair(pair, 'exchange', user_id=1)
        db.session.commit()

        revise_pair(pair, 'loan', comment='на самом деле долг', user_id=1)
        db.session.commit()

        revs = TreasuryPairRevision.query.filter_by(pair_id=pair_id).all()
        assert len(revs) == 1
        assert 'exchange' in revs[0].old_value
        assert 'loan' in revs[0].new_value
        assert revs[0].comment == 'на самом деле долг'


def test_confirm_twice_is_an_error(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        confirm_pair(pair, 'exchange', user_id=1)
        db.session.commit()

        try:
            confirm_pair(pair, 'exchange', user_id=1)
            raise AssertionError('повторное подтверждение должно падать')
        except PairError:
            pass


def test_pair_as_dict_has_both_sides(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        data = pair_as_dict(pair)
        assert data['first']['nick'] == '__SvcProbe__'
        assert data['second']['quantity'] == -5
        assert data['status'] == 'candidate'
