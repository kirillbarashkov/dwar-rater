"""Pure tests for the bulk compensation planner (no DB, no Flask).

Run: python -m pytest tests/test_treasury_bulk.py -q --noconftest
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.services.treasury_bulk import (  # noqa: E402
    ALREADY_COMPENSATED,
    BAD_PERIOD,
    BLOCKED,
    CREATE,
    FUTURE_MONTH,
    MONTH_CLOSED,
    NO_NORM,
    SKIP,
    UNKNOWN_NICK,
    plan_compensations,
)

TODAY = date(2026, 10, 6)


def _members(*pairs):
    return [{"nick": nick, "level": level} for nick, level in pairs]


def _compensation(nick, month, year=2026):
    return {
        "nick": nick,
        "date": f"15.{month:02d}.{year} 00:00",
        "quantity": 100,
        "compensation_flag": True,
    }


def _plan(**kwargs):
    base = dict(
        nicks=["Alpha"],
        months=[9],
        year=2026,
        members=_members(("Alpha", 19)),
        operations=[],
        today=TODAY,
    )
    base.update(kwargs)
    return plan_compensations(**base)


def _only(plan):
    assert len(plan["items"]) == 1
    return plan["items"][0]


def test_a_waiver_for_a_past_month_is_created_with_the_members_own_norm():
    item = _only(_plan())
    assert item["action"] == CREATE
    assert item["reason"] is None
    assert item["amount"] == 100  # level 19 -> 100


def test_the_canonical_spelling_from_the_roster_wins():
    item = _only(_plan(nicks=["alpha"]))
    assert item["nick"] == "Alpha"
    assert item["action"] == CREATE


def test_a_future_month_is_blocked_not_skipped():
    item = _only(_plan(months=[12]))
    assert item["action"] == BLOCKED
    assert item["reason"] == FUTURE_MONTH


def test_the_current_month_is_allowed():
    assert _only(_plan(months=[10]))["action"] == CREATE


def test_a_closed_month_is_blocked():
    item = _only(_plan(closed_keys=[(9, 2026)]))
    assert item["action"] == BLOCKED
    assert item["reason"] == MONTH_CLOSED


def test_a_closed_month_wins_over_an_unknown_nick():
    item = _only(_plan(nicks=["Ghost"], closed_keys=[(9, 2026)]))
    assert item["reason"] == MONTH_CLOSED


def test_an_unknown_nick_is_skipped_with_a_reason():
    item = _only(_plan(nicks=["Ghost"]))
    assert item["action"] == SKIP
    assert item["reason"] == UNKNOWN_NICK


def test_an_existing_waiver_is_not_duplicated():
    item = _only(_plan(operations=[_compensation("Alpha", 9)]))
    assert item["action"] == SKIP
    assert item["reason"] == ALREADY_COMPENSATED
    assert item["amount"] == 100


def test_an_existing_waiver_does_not_leak_into_another_month():
    assert _only(_plan(operations=[_compensation("Alpha", 8)]))["action"] == CREATE


def test_a_zero_amount_is_skipped_as_no_norm():
    item = _only(_plan(amount_by_nick={"alpha": 0}))
    assert item["action"] == SKIP
    assert item["reason"] == NO_NORM


def test_an_override_replaces_the_norm():
    assert _only(_plan(amount_by_nick={"ALPHA": 250}))["amount"] == 250


def test_a_junk_month_is_blocked():
    for bad in (13, 0, "abc", None, True):
        item = _only(_plan(months=[bad]))
        assert item["action"] == BLOCKED, bad
        assert item["reason"] == BAD_PERIOD, bad


def test_a_junk_year_is_blocked():
    assert _only(_plan(year=1999))["reason"] == BAD_PERIOD


def test_many_nicks_and_months_produce_one_item_per_pair():
    plan = _plan(
        nicks=["Alpha", "Beta", "Ghost"],
        months=[8, 9],
        members=_members(("Alpha", 19), ("Beta", 1)),
    )
    assert plan["totals"]["pairs"] == 6
    assert plan["totals"]["create"] == 4
    assert plan["totals"]["skip"] == 2
    assert plan["by_reason"] == {UNKNOWN_NICK: 2}
    assert plan["labels"][UNKNOWN_NICK] == "Ника нет в составе"


def test_blocked_pairs_are_counted_separately_from_skips():
    plan = _plan(nicks=["Alpha", "Beta"], months=[9, 12], members=_members(("Alpha", 19)))
    assert plan["totals"] == {"pairs": 4, "create": 1, "skip": 1, "blocked": 2}
    assert plan["by_reason"] == {FUTURE_MONTH: 2, UNKNOWN_NICK: 1}


def test_an_empty_request_plans_nothing():
    plan = _plan(nicks=[], months=[])
    assert plan["items"] == []
    assert plan["totals"] == {"pairs": 0, "create": 0, "skip": 0, "blocked": 0}
    assert plan["by_reason"] == {}


def test_the_plan_carries_the_reference_date_it_judged_by():
    assert _plan()["today"] == "2026-10-06"
