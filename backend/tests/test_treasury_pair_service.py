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
    batch_decide,
    confirm_pair,
    pair_as_dict,
    pair_history,
    reject_pair,
    restore_pair,
    revise_pair,
    split_pair,
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


def test_split_marks_kept_side_as_talents_and_frees_other(app):
    """Указанная сторона — списание на таланты, вторая снова учитываемая."""
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        split_pair(pair, 'first', user_id=1)
        db.session.commit()

        kept = db.session.get(TreasuryOperation, pair.first_op_id)
        other = db.session.get(TreasuryOperation, pair.second_op_id)

        assert kept.op_class == 'neutral'
        assert kept.class_kind == 'talents'
        assert kept.class_source == 'manual'

        assert other.op_class == 'tax'
        assert other.class_kind == ''
        assert pair.status == 'split'


def test_split_writes_revision_log(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        split_pair(pair, 'second', user_id=1)
        db.session.commit()

        revs = TreasuryPairRevision.query.filter_by(pair_id=pair_id).all()
        assert len(revs) == 1
        assert 'talents' in revs[0].new_value
        assert 'second' in revs[0].new_value


def test_split_rejects_unknown_side(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        try:
            split_pair(pair, 'third', user_id=1)
            raise AssertionError('неизвестная сторона должна падать')
        except PairError:
            pass


def test_restore_returns_pair_to_candidates(app):
    """Отмена решения: пара снова кандидат, операции снова учитываемые."""
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        confirm_pair(pair, 'loan', user_id=1)
        db.session.commit()
        assert db.session.get(TreasuryOperation, pair.first_op_id).op_class == 'neutral'

        restore_pair(pair, user_id=1)
        db.session.commit()

        assert pair.status == 'candidate'
        assert db.session.get(TreasuryOperation, pair.first_op_id).op_class == 'tax'
        assert db.session.get(TreasuryOperation, pair.second_op_id).op_class == 'tax'


def test_restore_after_split_frees_both_sides(app):
    """Возврат после разрыва: списание тоже снова становится учитываемым."""
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        split_pair(pair, 'first', user_id=1)
        db.session.commit()

        restore_pair(pair, user_id=1)
        db.session.commit()

        assert pair.status == 'candidate'
        assert db.session.get(TreasuryOperation, pair.first_op_id).op_class == 'tax'
        assert db.session.get(TreasuryOperation, pair.second_op_id).op_class == 'tax'


def test_restore_on_candidate_is_an_error(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        try:
            restore_pair(pair, user_id=1)
            raise AssertionError('возврат кандидата должен падать')
        except PairError:
            pass


def test_history_collects_entries_oldest_first(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        confirm_pair(pair, 'exchange', user_id=1)
        db.session.commit()
        revise_pair(pair, 'loan', comment='уточнение', user_id=1)
        db.session.commit()

        entries = pair_history(pair)
        # Подтверждение пишет только аудит — его ведут маршруты, а в сервисном тесте
        # их нет. В логе правок остаётся одна запись: от revise_pair.
        assert len(entries) == 1
        assert entries[0]['source'] == 'revision'
        assert all('changed_by_name' in entry for entry in entries)

        times = [entry['at'] for entry in entries if entry['at']]
        assert times == sorted(times)


def test_batch_confirm_applies_one_kind_to_all(app):
    """Групповое подтверждение: один тип на всю пачку."""
    first = _setup(app)
    second = _setup(app)

    with app.app_context():
        pairs = (
            TreasuryOperationPair.query.filter(
                TreasuryOperationPair.id.in_([first, second])
            )
            .order_by(TreasuryOperationPair.id)
            .all()
        )
        result = batch_decide(pairs, 'confirm', kind='exchange', user_id=1)
        db.session.commit()

        assert sorted(result['done']) == sorted([first, second])
        assert result['failed'] == []
        for pair in pairs:
            assert pair.status == 'confirmed'
            assert pair.kind == 'exchange'


def test_batch_reject_leaves_operations_tax(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        result = batch_decide([pair], 'reject', user_id=1)
        db.session.commit()

        assert result['done'] == [pair_id]
        assert pair.status == 'rejected'
        assert db.session.get(TreasuryOperation, pair.first_op_id).op_class == 'tax'


def test_batch_reports_failures_per_pair(app):
    """Ошибка на одной паре не гасит остальные — иначе непонятно, что не прошло."""
    first = _setup(app)
    second = _setup(app)

    with app.app_context():
        pairs = [
            db.session.get(TreasuryOperationPair, first),
            db.session.get(TreasuryOperationPair, second),
        ]
        # Первую подтверждаем заранее: повторное подтверждение обязано попасть в failed.
        confirm_pair(pairs[0], 'loan', user_id=1)
        db.session.commit()

        result = batch_decide(pairs, 'confirm', kind='loan', user_id=1)
        db.session.commit()

        assert result['done'] == [second]
        assert len(result['failed']) == 1
        assert result['failed'][0]['id'] == first


def test_batch_rejects_unknown_action(app):
    pair_id = _setup(app)
    with app.app_context():
        pair = db.session.get(TreasuryOperationPair, pair_id)
        try:
            batch_decide([pair], 'delete', user_id=1)
            raise AssertionError('неизвестное действие должно падать')
        except PairError:
            pass
