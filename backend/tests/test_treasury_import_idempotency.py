"""Re-importing a period must replace it, not double it.

dwar legitimately repeats identical rows (the same payment listed twice on a
page), so idempotency is a day-span replacement derived from the batch — never
value-based dedupe, which would silently drop real operations.
"""
from shared.models import db
from shared.models.clan_info import ClanInfo, TreasuryOperation

import pytest

CLAN = 987005

OP = {
    "date": "09.09.2026 20:03",
    "nick": "_ Sanych_",
    "operation_type": "Деньги",
    "object_name": "Монеты",
    "quantity": 100,
}
OP2 = {
    "date": "09.09.2026 20:04",
    "nick": "_ Sanych_",
    "operation_type": "Склад",
    "object_name": "Мо-датхар нурида",
    "quantity": 5,
}


@pytest.fixture(autouse=True)
def _clan(app):
    with app.app_context():
        if not ClanInfo.query.filter_by(clan_id=CLAN).first():
            db.session.add(ClanInfo(clan_id=CLAN, name="IdempotencyClan"))
            db.session.commit()
        TreasuryOperation.query.filter_by(clan_id=CLAN).delete()
        db.session.commit()
    yield


def _import(client, admin_headers, operations, replace_range=True):
    return client.post(
        f"/api/clan/{CLAN}/treasury/import",
        headers=admin_headers,
        json={"operations": operations, "replace_range": replace_range},
    )


def _count(app):
    with app.app_context():
        return TreasuryOperation.query.filter_by(clan_id=CLAN).count()


def test_reimporting_the_same_range_is_idempotent(app, client, admin_headers):
    batch = [OP, OP2]
    for attempt in range(3):
        resp = _import(client, admin_headers, batch)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert resp.get_json().get("success") is True
    assert _count(app) == 2


def test_legitimate_identical_rows_survive(app, client, admin_headers):
    """dwar really lists the same operation twice — both must survive."""
    batch = [OP, OP]
    _import(client, admin_headers, batch)
    assert _count(app) == 2
    _import(client, admin_headers, batch)
    assert _count(app) == 2


def test_days_outside_the_batch_are_untouched(app, client, admin_headers):
    with app.app_context():
        db.session.add(
            TreasuryOperation(
                clan_id=CLAN,
                date="01.01.2026 10:00",
                nick="Other",
                operation_type="Склад",
                object_name="Что-то",
                quantity=1,
            )
        )
        db.session.commit()

    _import(client, admin_headers, [OP])
    _import(client, admin_headers, [OP])

    assert _count(app) == 2
    with app.app_context():
        january = TreasuryOperation.query.filter_by(clan_id=CLAN).filter(
            TreasuryOperation.date == "01.01.2026 10:00"
        ).count()
        assert january == 1


def test_empty_batch_is_refused_without_touching_data(app, client, admin_headers):
    _import(client, admin_headers, [OP])
    resp = _import(client, admin_headers, [])
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "empty_import"
    assert _count(app) == 1


def test_append_mode_keeps_legacy_value_dedupe(app, client, admin_headers):
    """The paste-a-page flow keeps its old contract: a page is part of a day, so
    it is appended, and a row already stored with the same (date, nick, type,
    object, quantity) is treated as an update instead of a second copy."""
    _import(client, admin_headers, [OP], replace_range=False)
    _import(client, admin_headers, [OP], replace_range=False)
    assert _count(app) == 1
