"""Лицевой счёт участника (compute_member_ledger) — pure engine tests.

The ledger reuses the same month chain as the carry-over proposals, so the key
property to pin is agreement: a member's carried credit in the ledger must equal
the amount the carry-over engine proposes for that month. Two views, one rule.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.services.tax_engine import compute_carryovers, compute_member_ledger

TODAY = date(2026, 10, 5)


def op(day, month, year, nick, quantity, flagged=False, op_type="Деньги", obj="Монеты"):
    return {
        "date": f"{day:02d}.{month:02d}.{year} 12:00",
        "nick": nick,
        "operation_type": op_type,
        "object_name": obj,
        "quantity": quantity,
        "compensation_flag": flagged,
    }


def member(nick, level=5, join_date="", trial_until="", is_deleted=False):
    return {
        "nick": nick,
        "level": level,
        "join_date": join_date,
        "trial_until": trial_until,
        "is_deleted": is_deleted,
    }


def ledger(operations, members, from_m, from_y, to_m, to_y, decisions=None):
    return compute_member_ledger(
        operations,
        members,
        {},
        decisions or {},
        from_m,
        from_y,
        to_m,
        to_y,
        today=TODAY,
    )


def row(result, nick):
    for r in result["rows"]:
        if r["nick"] == nick:
            return r
    raise AssertionError(f"{nick} not in ledger: {[r['nick'] for r in result['rows']]}")


def test_ledger_is_empty_without_operations():
    result = ledger([], [member("Alpha")], 1, 2020, 3, 2020)
    assert result["rows"] == []
    assert result["reason"] == "no_operations"


def test_overpayment_becomes_a_carried_credit():
    ops = [op(10, 1, 2020, "Alpha", 310)]
    result = ledger(ops, [member("Alpha")], 1, 2020, 3, 2020)
    r = row(result, "Alpha")
    assert r["paid_total"] == 310
    assert r["norm_total"] == 30  # three months x 10 (level 5)
    assert r["carried_out_final"] == 280
    assert r["debt"] == 0
    assert r["balance"] == 280
    assert r["months"][0]["month"] == 1  # sorted oldest first


def test_ledger_agrees_with_the_carryover_engine():
    """The same money: the proposal for the last month == the ledger's carry."""
    ops = [op(10, 1, 2020, "Alpha", 310)]
    members = [member("Alpha")]
    for month in (1, 2, 3):
        proposals = compute_carryovers(ops, members, {}, {}, month, 2020, today=TODAY)
        expected = proposals[0].amount if proposals else 0
        r = row(ledger(ops, members, 1, 2020, month, 2020), "Alpha")
        assert r["carried_out_final"] == expected, f"month {month}"


def test_unpaid_months_become_debt():
    result = ledger([op(10, 1, 2020, "Alpha", 10)], [member("Alpha")], 1, 2020, 3, 2020)
    r = row(result, "Alpha")
    assert r["paid_total"] == 10
    assert r["debt"] == 20  # February + March unpaid
    assert r["balance"] == -20
    assert r["carried_out_final"] == 0


def test_compensation_settles_without_creating_a_credit():
    """A «зачёт» closes the month but is not money, so no phantom credit appears."""
    ops = [op(15, 1, 2020, "Alpha", 10, flagged=True)]
    result = ledger(ops, [member("Alpha")], 1, 2020, 1, 2020)
    r = row(result, "Alpha")
    assert r["compensation_total"] == 10
    assert r["paid_total"] == 0
    assert r["debt"] == 0
    assert r["balance"] == 0
    assert r["carried_out_final"] == 0


def test_months_before_the_window_only_feed_the_credit():
    ops = [
        op(10, 12, 2019, "Alpha", 50),   # outside the window
        op(10, 1, 2020, "Alpha", 5),     # inside
    ]
    result = ledger(ops, [member("Alpha")], 1, 2020, 1, 2020)
    r = row(result, "Alpha")
    # Only January counts in the totals...
    assert r["paid_total"] == 5
    assert r["norm_total"] == 10
    # ...but December's excess flows in as a carried credit.
    assert r["carried_in_total"] == 40
    assert r["carried_out_final"] == 35
    assert r["debt"] == 0
    assert r["balance"] == 35


def test_cancelled_decision_blocks_the_credit_in_the_ledger():
    ops = [op(10, 1, 2020, "Alpha", 310)]
    members = [member("Alpha")]
    decisions = {("alpha", 1, 2020): {"status": "cancelled", "amount": 300}}
    r = row(ledger(ops, members, 1, 2020, 3, 2020, decisions), "Alpha")
    assert r["carried_in_total"] == 0
    assert r["debt"] == 20  # Feb + Mar, since January's excess was not carried
    assert r["balance"] == -20


def test_departed_member_is_absent():
    ops = [op(10, 1, 2020, "Alpha", 250)]
    result = ledger(ops, [member("Alpha", is_deleted=True)], 1, 2020, 1, 2020)
    assert result["rows"] == []


def test_totals_are_the_sum_of_rows():
    ops = [
        op(10, 1, 2020, "Rich", 310),
        op(10, 1, 2020, "Poor", 0),
    ]
    ops = [o for o in ops if o["quantity"] > 0]
    members = [member("Rich"), member("Poor")]
    result = ledger(ops, members, 1, 2020, 1, 2020)
    totals = result["totals"]
    assert totals["paid_total"] == sum(r["paid_total"] for r in result["rows"])
    assert totals["debt"] == sum(r["debt"] for r in result["rows"])
    assert totals["balance"] == sum(r["balance"] for r in result["rows"])


def test_rows_are_sorted_by_balance_ascending():
    ops = [
        op(10, 1, 2020, "Rich", 310),
        op(10, 1, 2020, "Poor", 5),
    ]
    result = ledger(ops, [member("Rich"), member("Poor")], 1, 2020, 1, 2020)
    assert [r["nick"] for r in result["rows"]] == ["Poor", "Rich"]
    assert result["rows"][0]["balance"] < result["rows"][1]["balance"]


def test_months_are_window_only_and_each_carries_its_own_debt():
    """The breakdown must match the totals: window months only, each with debt.

    Lookback months exist to seed the chain; showing them in the per-month table
    would contradict the window totals right above it.
    """
    ops = [
        op(10, 12, 2019, "Alpha", 50),  # lookback only
        op(10, 1, 2020, "Beta", 5),     # window, short of the norm
    ]
    result = ledger(ops, [member("Alpha"), member("Beta")], 1, 2020, 2, 2020)

    alpha = row(result, "Alpha")
    assert [(m["month"], m["year"]) for m in alpha["months"]] == [(1, 2020), (2, 2020)]

    beta = row(result, "Beta")
    assert [m["debt"] for m in beta["months"]] == [5, 10]
    assert beta["debt"] == 15
    assert all("debt" in m for m in beta["months"])


def test_month_cells_expose_only_public_fields():
    """Internal chain keys (the review decision, the nick) must not leak."""
    ops = [op(10, 1, 2020, "Alpha", 10)]
    cell = row(ledger(ops, [member("Alpha")], 1, 2020, 1, 2020), "Alpha")["months"][0]
    assert set(cell) == {
        "month",
        "year",
        "norm",
        "paid",
        "compensation",
        "carried_in",
        "carried_out",
        "debt",
    }
