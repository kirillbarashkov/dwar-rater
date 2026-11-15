"""Re-import must survive classification pairs pointing at the replaced operations.

`treasury_operation_pair` / `treasury_pair_revision` reference operations and pairs
with plain foreign keys — no ON DELETE CASCADE. A bulk delete of operations while a
pair still points at them raised ForeignKeyViolation and the whole import answered
HTTP 500 (prod 2026-11-15, replace_range import of 923 operations). These tests keep
the ordering guarantee: revisions, then pairs, then operations.
"""
import pytest

from shared.models import db
from shared.models.clan_info import (
    ClanInfo,
    TreasuryOperation,
    TreasuryOperationPair,
    TreasuryPairRevision,
)

CLAN = 987041

IN_SPAN = "09.09.2026 20:03"
OUT_OF_SPAN = "10.10.2026 11:15"

NEW_OP = {
    "date": IN_SPAN,
    "nick": "_ Sanych_",
    "operation_type": "Деньги",
    "object_name": "Монеты",
    "quantity": 100,
}


@pytest.fixture(autouse=True)
def _cleanup(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="PairsImportClan"))
            db.session.commit()
        yield
        db.session.rollback()
        pair_ids = [
            row.id for row in TreasuryOperationPair.query.filter_by(clan_id=CLAN).all()
        ]
        if pair_ids:
            TreasuryPairRevision.query.filter(
                TreasuryPairRevision.pair_id.in_(pair_ids)
            ).delete(synchronize_session=False)
        TreasuryOperationPair.query.filter_by(clan_id=CLAN).delete(
            synchronize_session=False
        )
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete(
            synchronize_session=False
        )
        db.session.commit()


def _op(date, nick, quantity, op_class="tax", kind="", source=""):
    op = TreasuryOperation(
        clan_id=CLAN,
        date=date,
        nick=nick,
        operation_type="Склад",
        object_name="Мо-датхар нурида",
        quantity=quantity,
        op_class=op_class,
        class_kind=kind,
        class_source=source,
    )
    db.session.add(op)
    db.session.flush()
    return op


def _pair(first, second, status, kind="exchange"):
    pair = TreasuryOperationPair(
        clan_id=CLAN,
        first_op_id=first.id,
        second_op_id=second.id,
        kind=kind,
        status=status,
    )
    db.session.add(pair)
    db.session.flush()
    db.session.add(
        TreasuryPairRevision(
            pair_id=pair.id,
            old_value="{}",
            new_value='{"status": "%s"}' % status,
            comment="test fixture",
        )
    )
    return pair


def _import(client, admin_headers, operations, **extra):
    payload = {"operations": operations}
    payload.update(extra)
    return client.post(
        f"/api/clan/{CLAN}/treasury/import", headers=admin_headers, json=payload
    )


def test_replace_range_with_confirmed_pair_inside_span(app, client, admin_headers):
    with app.app_context():
        first = _op(IN_SPAN, "Alpha", 50, op_class="neutral", kind="exchange", source="manual")
        second = _op(IN_SPAN, "Beta", -50, op_class="neutral", kind="exchange", source="manual")
        pair = _pair(first, second, "confirmed")
        pair_id = pair.id
        db.session.commit()

    resp = _import(client, admin_headers, [NEW_OP], replace_range=True)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["success"] is True

    with app.app_context():
        assert db.session.get(TreasuryOperationPair, pair_id) is None
        assert (
            TreasuryPairRevision.query.filter_by(pair_id=pair_id).count() == 0
        ), "revision log must not outlive its pair"
        dates = {row.date for row in TreasuryOperation.query.filter_by(clan_id=CLAN).all()}
        assert dates == {IN_SPAN}
        assert TreasuryOperation.query.filter_by(clan_id=CLAN).count() == 1


def test_counterpart_outside_span_returns_to_tax(app, client, admin_headers):
    with app.app_context():
        first = _op(IN_SPAN, "Alpha", 50, op_class="neutral", kind="exchange", source="manual")
        second = _op(OUT_OF_SPAN, "Beta", -50, op_class="neutral", kind="exchange", source="manual")
        _pair(first, second, "confirmed")
        second_id = second.id
        db.session.commit()

    resp = _import(client, admin_headers, [NEW_OP], replace_range=True)
    assert resp.status_code == 200, resp.get_data(as_text=True)

    with app.app_context():
        survivor = db.session.get(TreasuryOperation, second_id)
        assert survivor is not None
        assert (survivor.op_class, survivor.class_kind, survivor.class_source) == (
            "tax",
            "",
            "",
        ), "a counterpart left without a pair must count again — nothing explains its neutral class"


def test_split_pair_counterpart_keeps_talents_class(app, client, admin_headers):
    """The write-off half is a treasurer decision; re-importing the other half must not undo it."""
    with app.app_context():
        first = _op(IN_SPAN, "Alpha", 50)
        second = _op(
            OUT_OF_SPAN, "Beta", -500, op_class="neutral", kind="talents", source="manual"
        )
        _pair(first, second, "split")
        second_id = second.id
        db.session.commit()

    resp = _import(client, admin_headers, [NEW_OP], replace_range=True)
    assert resp.status_code == 200, resp.get_data(as_text=True)

    with app.app_context():
        survivor = db.session.get(TreasuryOperation, second_id)
        assert survivor.op_class == "neutral"
        assert survivor.class_kind == "talents"


def test_full_replace_clears_pairs(app, client, admin_headers):
    with app.app_context():
        first = _op(OUT_OF_SPAN, "Alpha", 50, op_class="neutral", kind="loan", source="manual")
        second = _op(OUT_OF_SPAN, "Beta", -50, op_class="neutral", kind="loan", source="manual")
        _pair(first, second, "confirmed", kind="loan")
        db.session.commit()

    resp = _import(client, admin_headers, [NEW_OP], replace=True)
    assert resp.status_code == 200, resp.get_data(as_text=True)

    with app.app_context():
        assert TreasuryOperationPair.query.filter_by(clan_id=CLAN).count() == 0
        assert TreasuryOperation.query.filter_by(clan_id=CLAN).count() == 1
