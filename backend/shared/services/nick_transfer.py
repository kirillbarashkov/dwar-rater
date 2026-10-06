"""Reconnect a renamed character's history — pure, no Flask.

An in-game rename leaves the treasurer with a hole: the old nick keeps every
payment and level record while the new one starts from zero, so the ledger shows
one member as an overpaid ghost and another as a debtor. This planner says exactly
what would move from one nick to the other.

What moves: treasury operations (the money), carry-over rows (the review ledger)
and level-change events (the level chain the norms are derived from). What does
NOT move: nothing is deleted and no amounts are merged — a carry-over collision is
reported for a human to resolve, because summing two people's money is a decision,
not a mechanic.
"""

from typing import Any, Iterable, Mapping, Optional, Sequence

from shared.services.tax_engine import parse_ddmmyyyy

CONFLICT = "carryover_conflict"


def _nick_key(value: Any) -> str:
    return (value or '').strip().lower()


def _ym(value: Any) -> Optional[tuple]:
    parsed = parse_ddmmyyyy(value)
    # parse_ddmmyyyy returns (year, month, day).
    return (parsed[1], parsed[0]) if parsed else None


def plan_nick_transfer(
    *,
    from_nick: str,
    to_nick: str,
    operations: Iterable[Mapping[str, Any]] = (),
    carryovers: Iterable[Mapping[str, Any]] = (),
    level_events: Iterable[Mapping[str, Any]] = (),
) -> dict:
    """What would move from `from_nick` to `to_nick`, and what cannot."""
    source = _nick_key(from_nick)
    target = _nick_key(to_nick)

    carried: list = []
    taken: set = set()
    for row in carryovers:
        key = _nick_key(row.get('nick'))
        if key == target:
            taken.add((row.get('source_month'), row.get('source_year')))
        elif key == source:
            carried.append(row)

    moving = []
    skipped = []
    for row in carried:
        source_ym = (row.get('source_month'), row.get('source_year'))
        if source_ym in taken:
            # The receiving nick already has a carry-over row for this very month;
            # the table has a unique constraint on it, and merging money would be a
            # decision nobody asked this tool to make.
            skipped.append(
                {
                    'id': row.get('id'),
                    'month': row.get('source_month'),
                    'year': row.get('source_year'),
                    'amount': row.get('amount'),
                    'reason': CONFLICT,
                }
            )
        else:
            taken.add(source_ym)
            moving.append(row.get('id'))

    moved_operations = []
    months = set()
    for op in operations:
        if _nick_key(op.get('nick')) != source:
            continue
        moved_operations.append(op.get('id'))
        pair = _ym(op.get('date'))
        if pair:
            months.add(pair)

    dates = sorted(d for d in (op.get('date') for op in operations
                               if _nick_key(op.get('nick')) == source and op.get('date')))

    moved_levels = [row.get('id') for row in level_events if _nick_key(row.get('nick')) == source]

    return {
        'from_nick': (from_nick or '').strip(),
        'to_nick': (to_nick or '').strip(),
        'operations': {
            'count': len(moved_operations),
            'ids': moved_operations,
            'total_quantity': sum(
                int(op.get('quantity') or 0)
                for op in operations
                if _nick_key(op.get('nick')) == source
            ),
            'first_date': dates[0] if dates else None,
            'last_date': dates[-1] if dates else None,
            'months': sorted(months, key=lambda pair: (pair[1], pair[0])),
        },
        'carryovers': {'move': moving, 'skip': skipped, 'skipped_count': len(skipped)},
        'level_events': {'count': len(moved_levels), 'ids': moved_levels},
        'is_empty': not (moved_operations or moving or moved_levels),
    }
