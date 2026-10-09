"""Chat-ready markdown summaries of a clan's treasury — pure, no Flask.

The treasurer's clipboard: totals for a month, the flat list of debtors, the flat
list of carry-over records. Markdown on purpose — the result is pasted into a clan
chat as-is, so anything a plain-text chat window would not render (tables, HTML)
is avoided: bold lines and bullet lists only.
"""

from typing import Any, Iterable, Mapping

MONTHS_RU = [
    'январь',
    'февраль',
    'март',
    'апрель',
    'май',
    'июнь',
    'июль',
    'август',
    'сентябрь',
    'октябрь',
    'ноябрь',
    'декабрь',
]

STATUS_LABELS = {
    'pending': 'ждёт решения',
    'confirmed': 'подтверждён',
    'cancelled': 'отменён',
}

TOTALS = 'totals'
DEBTORS = 'debtors'
CARRYOVERS = 'carryovers'

KINDS = {
    TOTALS: 'Итоги месяца',
    DEBTORS: 'Должники',
    CARRYOVERS: 'Переносы переплаты',
}


def _period(month: Any, year: Any) -> str:
    try:
        index = int(month)
    except (TypeError, ValueError):
        return f'{month}.{year}'
    if 1 <= index <= 12:
        return f'{MONTHS_RU[index - 1]} {year}'
    return f'{month}.{year}'


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def format_totals(
    *,
    month: Any,
    year: Any,
    collected: Any = 0,
    expected: Any = 0,
    missing: Any = 0,
    debtors: int = 0,
    members: int = 0,
) -> str:
    """Собрано / ожидалось / не собрано plus how many owe."""
    lines = [f'**Налоги за {_period(month, year)}**', '']
    lines.append(f'Собрано: **{_as_int(collected)}**')
    lines.append(f'Ожидалось: {_as_int(expected)}')
    lines.append(f'Не собрано: **{_as_int(missing)}**')
    if members:
        lines.append(f'Должников: {debtors} из {members}')
    elif debtors:
        lines.append(f'Должников: {debtors}')
    return '\n'.join(lines)


def format_debtors(
    *,
    month: Any,
    year: Any,
    rows: Iterable[Mapping[str, Any]] = (),
) -> str:
    """A flat list — what a clan chat can actually read."""
    owing = [row for row in rows if _as_int(row.get('debt')) > 0]
    header = f'**Должники за {_period(month, year)}** ({len(owing)})'
    if not owing:
        return f'{header}\n\nДолгов нет.'

    lines = [header, '']
    total = 0
    for row in owing:
        debt = _as_int(row.get('debt'))
        total += debt
        paid = _as_int(row.get('paid'))
        tail = f' (заплатил {paid})' if paid else ''
        lines.append(f'- **{row.get("nick") or "—"}** — {debt}{tail}')
    lines.append('')
    lines.append(f'Итого долг: **{total}**')
    return '\n'.join(lines)


def format_carryovers(
    *,
    rows: Iterable[Mapping[str, Any]] = (),
    month: Any = None,
    year: Any = None,
    only_confirmed: bool = False,
) -> str:
    """A flat list of the review ledger, newest month last."""
    items = list(rows)
    if only_confirmed:
        items = [row for row in items if row.get('status') == 'confirmed']
    header = '**Переносы переплаты**'
    if month is not None and year is not None:
        header += f' за {_period(month, year)}'
    header += f' ({len(items)})'
    if not items:
        return f'{header}\n\nПереносов нет.'

    lines = [header, '']
    for row in sorted(
        items,
        key=lambda r: (
            _as_int(r.get('source_year')),
            _as_int(r.get('source_month')),
            str(r.get('nick') or ''),
        ),
    ):
        status = STATUS_LABELS.get(str(row.get('status')), str(row.get('status') or ''))
        lines.append(
            f'- **{row.get("nick") or "—"}** — {_as_int(row.get("amount"))} '
            f'за {_period(row.get("source_month"), row.get("source_year"))} ({status})'
        )
    total = sum(_as_int(row.get('amount')) for row in items)
    lines.append('')
    lines.append(f'Итого: **{total}**')
    return '\n'.join(lines)


def build_summary(kind: str, **kwargs) -> str:
    """Dispatch by kind; unknown kinds raise so the route can answer 400."""
    if kind == TOTALS:
        return format_totals(**kwargs)
    if kind == DEBTORS:
        return format_debtors(**kwargs)
    if kind == CARRYOVERS:
        return format_carryovers(**kwargs)
    raise ValueError(f'unknown summary kind: {kind}')
