"""Pure tests for the chat-ready markdown summaries.

Run: python -m pytest tests/test_treasury_summary.py -q --noconftest
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.services.treasury_summary import (  # noqa: E402
    build_summary,
    format_carryovers,
    format_debtors,
    format_totals,
)


def _debtor(nick, debt, paid=0):
    return {'nick': nick, 'debt': debt, 'paid': paid}


def _carry(nick, month, year, amount, status='pending'):
    return {
        'nick': nick,
        'source_month': month,
        'source_year': year,
        'amount': amount,
        'status': status,
    }


def test_totals_read_as_three_numbers_and_the_debtor_count():
    text = format_totals(
        month=10, year=2026, collected=2600, expected=2700, missing=100, debtors=1, members=2
    )
    assert text == (
        '**Налоги за октябрь 2026**\n'
        '\n'
        'Собрано: **2600**\n'
        'Ожидалось: 2700\n'
        'Не собрано: **100**\n'
        'Должников: 1 из 2'
    )


def test_totals_omit_the_denominator_when_the_roster_size_is_unknown():
    assert 'Должников: 3' in format_totals(month=1, year=2026, debtors=3)
    assert 'из' not in format_totals(month=1, year=2026, debtors=3)
    assert 'Должников' not in format_totals(month=1, year=2026)


def test_a_month_out_of_range_falls_back_to_the_numeric_form():
    assert 'за 13.2026' in format_totals(month=13, year=2026)


def test_debtors_are_a_flat_markdown_list_with_a_total():
    text = format_debtors(
        month=10, year=2026, rows=[_debtor('Beta', 20, 10), _debtor('Alpha', 100), _debtor('Paid', 0, 50)]
    )
    assert '**Должники за октябрь 2026** (2)' in text
    assert '- **Beta** — 20 (заплатил 10)' in text
    assert '- **Alpha** — 100' in text
    assert 'Paid' not in text  # a settled member is not a debtor
    assert 'Итого долг: **120**' in text
    # No tables: a clan chat renders them as a wall of pipes.
    assert '|' not in text


def test_debtors_say_so_when_nobody_owes():
    text = format_debtors(month=10, year=2026, rows=[_debtor('Alpha', 0, 100)])
    assert text == '**Должники за октябрь 2026** (0)\n\nДолгов нет.'


def test_carryovers_are_listed_with_month_status_and_a_total():
    text = format_carryovers(
        rows=[
            _carry('Beta', 10, 2026, 50, 'confirmed'),
            _carry('Alpha', 9, 2026, 100, 'pending'),
        ]
    )
    assert '**Переносы переплаты** (2)' in text
    # Sorted by period, so the oldest month comes first — how a ledger reads.
    assert text.index('**Alpha**') < text.index('**Beta**')
    assert '- **Alpha** — 100 за сентябрь 2026 (ждёт решения)' in text
    assert '- **Beta** — 50 за октябрь 2026 (подтверждён)' in text
    assert 'Итого: **150**' in text


def test_carryovers_can_be_limited_to_confirmed_ones():
    text = format_carryovers(
        rows=[_carry('Beta', 10, 2026, 50, 'confirmed'), _carry('Alpha', 9, 2026, 100, 'pending')],
        only_confirmed=True,
    )
    assert '**Переносы переплаты** (1)' in text
    assert 'Alpha' not in text
    assert 'Итого: **50**' in text


def test_carryovers_say_so_when_there_are_none():
    assert format_carryovers(rows=[]) == '**Переносы переплаты** (0)\n\nПереносов нет.'


def test_the_dispatcher_serves_every_kind_and_refuses_the_rest():
    assert build_summary('totals', month=1, year=2026).startswith('**Налоги за январь 2026**')
    assert build_summary('debtors', month=1, year=2026, rows=[]).startswith('**Должники')
    assert build_summary('carryovers', rows=[]).startswith('**Переносы')
    with pytest.raises(ValueError):
        build_summary('everything', month=1, year=2026)
