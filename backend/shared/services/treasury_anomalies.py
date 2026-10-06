"""Anomaly detection over a clan's treasury — pure, no Flask.

The treasurer's «что не так с казной» view. Findings are categorised, carry
examples and NEVER mutate anything: this is a diagnostic, not a cleaner.

Judgment calls are reported rather than refused, because the clan legitimately
has members who left (a payment from a nick the roster no longer knows) and
people who prepay (an amount above the norm). The two unambiguous corruptions —
a future date and a negative amount — are reported here AND refused at the write
boundary, so new ones cannot be created.
"""

from datetime import date
from typing import Any, Iterable, Mapping, Optional, Sequence

from shared.services.tax_engine import (
    is_real_payment,
    norm_for_level,
    parse_ddmmyyyy,
    payment_start_ym,
    ym_index,
)

FUTURE_DATE = "future_date"
NEGATIVE_QUANTITY = "negative_quantity"
BEFORE_JOIN = "before_join"
UNKNOWN_NICK = "unknown_nick"
ABOVE_NORM = "above_norm"

# «Заметно выше нормы»: a single payment of three monthly norms or more reads as
# lumped prepayments (or a typo), which the treasurer should look at.
ABOVE_NORM_FACTOR = 3

# How many example operations each finding carries (the count is always exact).
EXAMPLES = 5

LABELS = {
    FUTURE_DATE: "Дата в будущем",
    NEGATIVE_QUANTITY: "Отрицательная сумма",
    BEFORE_JOIN: "Платёж раньше вступления",
    UNKNOWN_NICK: "Ник не из состава",
    ABOVE_NORM: "Сумма заметно выше нормы",
}

# Findings that are corruption rather than judgement — these are also refused on
# the way in (see the import and correction paths).
BLOCKING = (FUTURE_DATE, NEGATIVE_QUANTITY)


def _example(op: Mapping[str, Any], extra: Optional[str] = None) -> dict:
    row = {
        "id": op.get("id"),
        "date": op.get("date"),
        "nick": op.get("nick"),
        "quantity": op.get("quantity"),
    }
    if extra:
        row["note"] = extra
    return row


def detect_anomalies(
    operations: Iterable[Mapping[str, Any]],
    members: Iterable[Mapping[str, Any]],
    *,
    today: Optional[date] = None,
) -> dict:
    """Findings over the given operations, biggest group first.

    ``operations`` are plain dicts (id, date, nick, operation_type, object_name,
    quantity, compensation_flag); ``members`` are the clan roster. Nothing here
    touches the database, so the endpoint can run on every page load.
    """
    today = today or date.today()
    today_index = ym_index(today.month, today.year)

    roster = {}
    for member in members:
        nick = (member.get("nick") or "").lower()
        if nick:
            roster[nick] = member

    found: dict = {code: [] for code in LABELS}
    checked_operations = 0

    for op in operations:
        checked_operations += 1
        quantity = int(op.get("quantity") or 0)
        nick = (op.get("nick") or "").strip()
        nick_key = nick.lower()
        parsed = parse_ddmmyyyy(op.get("date"))

        if parsed:
            year, month, _day = parsed
            if ym_index(month, year) > today_index:
                found[FUTURE_DATE].append(_example(op))
        if quantity < 0:
            found[NEGATIVE_QUANTITY].append(_example(op))

        member = roster.get(nick_key)
        if member is None:
            if nick:
                found[UNKNOWN_NICK].append(_example(op))
            continue

        if not is_real_payment(op):
            # «Зачёты» are bookkeeping markers: rating them against the norm is
            # meaningless, and they never move money.
            continue

        start = payment_start_ym(member, today)
        if parsed and start is not None:
            year, month, _day = parsed
            if ym_index(month, year) < ym_index(start[0], start[1]):
                found[BEFORE_JOIN].append(
                    _example(op, extra=f"оплата идёт с {start[0]:02d}.{start[1]}")
                )

        norm = norm_for_level(member.get("level"))
        if norm and quantity >= norm * ABOVE_NORM_FACTOR:
            found[ABOVE_NORM].append(
                _example(op, extra=f"норма {norm}, порог {norm * ABOVE_NORM_FACTOR}")
            )

    items = []
    for code, rows in found.items():
        if not rows:
            continue
        items.append(
            {
                "code": code,
                "label": LABELS[code],
                "blocking": code in BLOCKING,
                "count": len(rows),
                "examples": rows[:EXAMPLES],
            }
        )
    items.sort(key=lambda item: (-item["count"], item["code"]))

    return {
        "items": items,
        "total": sum(item["count"] for item in items),
        "checked": {
            "operations": checked_operations,
            "members": len(roster),
        },
        "today": today.isoformat(),
    }
