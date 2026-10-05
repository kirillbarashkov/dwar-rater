"""Pure tax carry-over engine tests (no DB, no Flask).

The engine is the second implementation of the tax rules the UI computes, so
these cases pin the rules that could silently drift:
  * the norm comes from the level, defaulting to DEFAULT_NORM;
  * an overpayment is a running credit: carry(N) = max(0, Σpaid - Σnorms);
  * debt never turns into a negative carry that offsets a later excess;
  * «зачёт» rows (compensation_flag) are NOT money — counting them would
    invent a phantom credit;
  * a member pays from the month after joining and only while active;
  * confirmed decisions fix the amount, cancelled ones block the carry.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.services.tax_engine import (
    Carryover,
    add_months,
    compute_carryovers,
    is_month_closed,
    level_at_month_end,
    month_key,
    norm_for_level,
    payment_start_ym,
    prev_ym,
    ym_index,
)

TODAY = date(2026, 10, 5)


def op(day, month, year, nick, quantity, op_type="Деньги", obj="Монеты", flagged=False):
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


def amounts(proposals):
    return {p.nick: p.amount for p in proposals}


def run(operations, members, month, year, decisions=None, level_events=None, today=TODAY):
    return compute_carryovers(
        operations,
        members,
        level_events or {},
        decisions or {},
        month,
        year,
        today=today,
    )


def test_norm_table_and_fallback():
    assert norm_for_level(1) == 10
    assert norm_for_level(5) == 10
    assert norm_for_level(8) == 15
    assert norm_for_level(10) == 20
    assert norm_for_level(12) == 25
    assert norm_for_level(15) == 50
    assert norm_for_level(20) == 100
    assert norm_for_level(99) == 10
    assert norm_for_level(None) == 10


def test_month_helpers():
    assert month_key("15.01.2020 10:00") == (1, 2020)
    assert month_key("nonsense") is None
    assert prev_ym(1, 2020) == (12, 2019)
    assert add_months(11, 2025, 3) == (2, 2026)
    assert ym_index(1, 2020) == ym_index(12, 2019) + 1
    assert is_month_closed(1, 2020, TODAY) is True
    assert is_month_closed(10, 2026, TODAY) is False
    assert is_month_closed(9, 2026, TODAY) is True


def test_simple_overpayment_is_carried():
    ops = [op(10, 1, 2020, "Alpha", 250)]
    proposals = run(ops, [member("Alpha")], 1, 2020)
    assert amounts(proposals) == {"Alpha": 240}  # 250 paid - 10 norm (level 5)


def test_no_proposal_without_overpayment():
    ops = [op(10, 1, 2020, "Alpha", 10)]
    assert run(ops, [member("Alpha")], 1, 2020) == []


def test_chain_reduces_the_credit_by_each_month_norm():
    """carry(N) == Σpaid - Σnorms (never negative): the same money is not carried twice."""
    ops = [op(10, 1, 2020, "Alpha", 310)]
    members = [member("Alpha")]  # norm 10/month

    assert amounts(run(ops, members, 1, 2020)) == {"Alpha": 300}
    assert amounts(run(ops, members, 2, 2020)) == {"Alpha": 290}
    assert amounts(run(ops, members, 3, 2020)) == {"Alpha": 280}


def test_remainder_flows_past_a_bigger_norm():
    """Overpay 300 at level 5, then the member levels up to 16 (norm 100)."""
    ops = [op(10, 1, 2020, "Alpha", 310)]
    members = [member("Alpha", level=16)]
    level_events = {"alpha": [{"date": "05.01.2020", "new_level": 16}]}

    # January: 310 - 100 = 210 carried; February: 210 - 100 = 110.
    assert amounts(run(ops, members, 1, 2020, level_events=level_events)) == {"Alpha": 210}
    assert amounts(run(ops, members, 2, 2020, level_events=level_events)) == {"Alpha": 110}


def test_debt_does_not_offset_a_later_overpayment():
    ops = [
        op(10, 1, 2020, "Alpha", 0),      # ignored: quantity must be > 0
        op(10, 2, 2020, "Alpha", 250),    # February
    ]
    members = [member("Alpha")]  # norm 10
    # January is unpaid (0 paid, 10 owed) -> carry 0, not -10.
    assert run(ops, members, 1, 2020) == []
    assert amounts(run(ops, members, 2, 2020)) == {"Alpha": 240}


def test_compensation_rows_are_not_money():
    """A «зачёт» (+norm, flagged) must not look like an overpayment."""
    ops = [
        op(15, 1, 2020, "Alpha", 10, flagged=True),
        op(16, 1, 2020, "Alpha", 10),
    ]
    members = [member("Alpha")]
    assert run(ops, members, 1, 2020) == []


def test_non_tax_operations_are_ignored():
    ops = [
        op(10, 1, 2020, "Alpha", 500, op_type="Склад", obj="Кристаллы истины"),
        op(10, 1, 2020, "Alpha", 500, obj="Что-то ещё"),
        op(10, 1, 2020, "Alpha", -500),  # negative -> not income
    ]
    assert run(ops, [member("Alpha")], 1, 2020) == []


def test_member_pays_from_the_month_after_joining():
    assert payment_start_ym(member("A", join_date="10.01.2020"), TODAY) == (2, 2020)
    # Joined in January -> January has no obligation, so the payment is a credit.
    ops = [op(20, 1, 2020, "Alpha", 50)]
    members = [member("Alpha", join_date="10.01.2020")]
    assert amounts(run(ops, members, 1, 2020)) == {"Alpha": 50}
    # ...and February's norm eats into it.
    assert amounts(run(ops, members, 2, 2020)) == {"Alpha": 40}


def test_expired_trial_sets_the_join_date():
    # Trial ended 24.01.2020 (in the past vs TODAY) -> joined ~10.01.2020 -> pays from February.
    assert payment_start_ym(member("A", trial_until="24.01.2020"), TODAY) == (2, 2020)
    # Future trial -> pays the month after the trial month.
    assert payment_start_ym(member("A", trial_until="24.12.2026"), TODAY) == (1, 2027)


def test_departed_member_gets_no_carryover():
    ops = [op(10, 1, 2020, "Alpha", 250)]
    assert run(ops, [member("Alpha", is_deleted=True)], 1, 2020) == []


def test_payer_absent_from_roster_is_ignored():
    ops = [op(10, 1, 2020, "Ghost", 250)]
    assert run(ops, [member("Alpha")], 1, 2020) == []


def test_cancelled_decision_blocks_the_carry():
    ops = [op(10, 1, 2020, "Alpha", 310)]
    members = [member("Alpha")]
    decisions = {("alpha", 1, 2020): {"status": "cancelled", "amount": 300}}

    assert run(ops, members, 1, 2020, decisions=decisions) == []
    assert run(ops, members, 2, 2020, decisions=decisions) == []


def test_confirmed_decision_fixes_the_amount():
    ops = [op(10, 1, 2020, "Alpha", 310)]
    members = [member("Alpha")]
    decisions = {("alpha", 1, 2020): {"status": "confirmed", "amount": 150}}

    assert run(ops, members, 1, 2020, decisions=decisions) == []
    assert amounts(run(ops, members, 2, 2020, decisions=decisions)) == {"Alpha": 140}


def test_level_at_month_end_uses_the_latest_event_in_that_month():
    events = [
        {"date": "20.01.2020", "new_level": 6},
        {"date": "05.02.2020", "new_level": 9},
    ]
    assert level_at_month_end(events, 1, 2020) == 6
    assert level_at_month_end(events, 2, 2020) == 9
    assert level_at_month_end(events, 3, 2020) == 9
    assert level_at_month_end([], 1, 2020) is None


def test_level_history_is_sorted_defensively():
    """event_date is DD.MM.YYYY — string order is wrong across years."""
    events = [
        {"date": "05.02.2021", "new_level": 12},
        {"date": "20.12.2020", "new_level": 7},
    ]
    assert level_at_month_end(events, 12, 2020) == 7
    assert level_at_month_end(events, 2, 2021) == 12


def test_no_operations_means_no_proposals():
    assert run([], [member("Alpha")], 1, 2020) == []


def test_lookback_bound_does_not_break_the_chain():
    ops = [op(10, 1, 2015, "Alpha", 100), op(10, 1, 2020, "Alpha", 250)]
    proposals = run(ops, [member("Alpha")], 1, 2020)
    # The 2015 excess is out of the lookback window; only the 2020 month counts.
    assert amounts(proposals) == {"Alpha": 240}


def test_proposals_are_sorted_by_amount_desc():
    ops = [
        op(10, 1, 2020, "Small", 50),
        op(10, 1, 2020, "Big", 250),
    ]
    members = [member("Small"), member("Big")]
    proposals = run(ops, members, 1, 2020)
    assert [p.nick for p in proposals] == ["Big", "Small"]
    assert isinstance(proposals[0], Carryover)
