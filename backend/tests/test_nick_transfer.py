"""Pure tests for the renamed-character history transfer planner.

Run: python -m pytest tests/test_nick_transfer.py -q --noconftest
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.services.nick_transfer import CONFLICT, plan_nick_transfer  # noqa: E402


def _op(op_id, nick, date, quantity):
    return {'id': op_id, 'nick': nick, 'date': date, 'quantity': quantity}


def _carry(row_id, nick, month, year, amount=100, status='pending'):
    return {
        'id': row_id,
        'nick': nick,
        'source_month': month,
        'source_year': year,
        'amount': amount,
        'status': status,
    }


def _level(row_id, nick, date):
    return {'id': row_id, 'nick': nick, 'event_date': date}


def _plan(**kwargs):
    base = dict(
        from_nick='OldName',
        to_nick='NewName',
        operations=[],
        carryovers=[],
        level_events=[],
    )
    base.update(kwargs)
    return plan_nick_transfer(**base)


def test_every_operation_of_the_old_nick_moves():
    plan = _plan(
        operations=[
            _op(1, 'OldName', '05.09.2026 12:00', 100),
            _op(2, 'OldName', '05.10.2026 12:00', 50),
            _op(3, 'Other', '05.10.2026 12:00', 999),
        ]
    )
    assert plan['operations']['ids'] == [1, 2]
    assert plan['operations']['count'] == 2
    assert plan['operations']['total_quantity'] == 150
    assert plan['operations']['first_date'] == '05.09.2026 12:00'
    assert plan['operations']['last_date'] == '05.10.2026 12:00'
    assert plan['operations']['months'] == [(9, 2026), (10, 2026)]
    assert plan['is_empty'] is False


def test_the_nick_match_is_case_insensitive_and_spelling_is_ignored():
    plan = _plan(from_nick=' oldname ', operations=[_op(1, 'Oldname', '05.10.2026', 10)])
    assert plan['operations']['ids'] == [1]
    assert plan['from_nick'] == 'oldname'
    assert plan['to_nick'] == 'NewName'


def test_carryovers_move_with_them():
    plan = _plan(carryovers=[_carry(7, 'OldName', 9, 2026), _carry(8, 'Other', 9, 2026)])
    assert plan['carryovers']['move'] == [7]
    assert plan['carryovers']['skip'] == []
    assert plan['is_empty'] is False


def test_a_carryover_for_a_month_the_target_already_has_is_reported_not_merged():
    plan = _plan(
        carryovers=[
            _carry(7, 'OldName', 9, 2026, amount=100),
            _carry(9, 'NewName', 9, 2026, amount=40),
        ]
    )
    assert plan['carryovers']['move'] == []
    assert plan['carryovers']['skipped_count'] == 1
    skipped = plan['carryovers']['skip'][0]
    assert skipped['id'] == 7
    assert skipped['reason'] == CONFLICT
    assert skipped['month'] == 9 and skipped['year'] == 2026
    assert skipped['amount'] == 100


def test_a_second_source_row_for_the_same_month_is_reported_not_planned():
    # The table has a unique (clan, nick, month, year), so this cannot come out of
    # the database — but the planner must never plan a write that would violate it,
    # so the pair stays visible as a conflict instead of being silently moved.
    plan = _plan(
        carryovers=[
            _carry(7, 'OldName', 9, 2026),
            _carry(8, 'OldName', 9, 2026),
        ]
    )
    assert plan['carryovers']['move'] == [7]
    assert plan['carryovers']['skipped_count'] == 1
    assert plan['carryovers']['skip'][0]['id'] == 8
    assert plan['carryovers']['skip'][0]['reason'] == CONFLICT


def test_level_events_follow_the_person():
    plan = _plan(
        level_events=[_level(1, 'OldName', '01.09.2026'), _level(2, 'Other', '01.09.2026')]
    )
    assert plan['level_events'] == {'count': 1, 'ids': [1]}


def test_a_nick_with_nothing_to_move_reports_itself_as_empty():
    plan = _plan(operations=[_op(1, 'Other', '05.10.2026', 10)])
    assert plan['is_empty'] is True
    assert plan['operations']['count'] == 0
    assert plan['operations']['total_quantity'] == 0
    assert plan['operations']['first_date'] is None


def test_junk_dates_do_not_break_the_plan():
    plan = _plan(
        operations=[
            _op(1, 'OldName', 'не-дата', 10),
            _op(2, 'OldName', None, 5),
            _op(3, 'OldName', '01.10.2026', 5),
        ]
    )
    assert plan['operations']['count'] == 3
    assert plan['operations']['total_quantity'] == 20
    assert plan['operations']['months'] == [(10, 2026)]
    assert plan['operations']['last_date'] == 'не-дата'
