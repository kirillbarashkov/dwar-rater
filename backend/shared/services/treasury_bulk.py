"""Bulk operations over a clan's treasury — pure, no Flask.

A bulk action is only trustworthy if the dry-run and the write run the SAME
planner. Both the preview endpoint and the apply endpoint call
`plan_compensations` here, against the same DB state, so what the treasurer
reviewed is what gets written — they cannot drift apart.

What gets created is a compensation MARKER (`compensation_flag=True`), not money:
the same bookkeeping row the single «Зачесть» writes, one per (nick, month).

Every pair is classified rather than silently dropped:

- `create`  — the marker will be written;
- `skip`    — the treasurer's intent is already satisfied or impossible
              (`already_compensated`, `unknown_nick`, `no_norm`);
- `blocked` — refusing is not a judgement call (`bad_period`, `future_month`,
              `month_closed`) — a closed month is frozen (see §6-5), and a
              waiver in a month that has not started yet is a mistake.
"""

from datetime import date
from typing import Any, Iterable, Mapping, Optional, Sequence

from shared.services.tax_engine import norm_for_level, parse_ddmmyyyy

CREATE = "create"
SKIP = "skip"
BLOCKED = "blocked"

ALREADY_COMPENSATED = "already_compensated"
UNKNOWN_NICK = "unknown_nick"
NO_NORM = "no_norm"
BAD_PERIOD = "bad_period"
FUTURE_MONTH = "future_month"
MONTH_CLOSED = "month_closed"

REASONS = {
    ALREADY_COMPENSATED: "Уже зачтено",
    UNKNOWN_NICK: "Ника нет в составе",
    NO_NORM: "Норма не определена",
    BAD_PERIOD: "Некорректный месяц",
    FUTURE_MONTH: "Месяц ещё не наступил",
    MONTH_CLOSED: "Месяц закрыт",
}

# Refusals that no reviewer can override — the tariff data must not accept them.
BLOCKING_REASONS = (BAD_PERIOD, FUTURE_MONTH, MONTH_CLOSED)

MIN_YEAR = 2000


def _as_month(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        month = int(value)
    except (TypeError, ValueError):
        return None
    return month if 1 <= month <= 12 else None


def _as_amount(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def plan_compensations(
    *,
    nicks: Sequence[str],
    months: Sequence[int],
    year: int,
    members: Iterable[Mapping[str, Any]],
    operations: Iterable[Mapping[str, Any]],
    closed_keys: Iterable[tuple] = (),
    amount_by_nick: Optional[Mapping[str, Any]] = None,
    today: Optional[date] = None,
) -> dict:
    """What WOULD be written for these nicks × months, and why.

    `closed_keys` are (month, year) pairs the clan froze; `amount_by_nick` lets
    the caller override the per-member norm (case-insensitive keys).
    """
    today = today or date.today()
    today_ym = (today.year, today.month)
    closed = set()
    for key in closed_keys:
        try:
            closed.add((int(key[0]), int(key[1])))
        except (TypeError, ValueError, IndexError):
            continue

    # Roster: lowercased nick -> (canonical spelling, level). Spelling from the
    # roster wins so a waiver cannot introduce a second spelling of a nick.
    roster = {}
    for member in members:
        nick = (member.get("nick") or "").strip()
        if nick:
            roster[nick.lower()] = (nick, member.get("level"))

    already = set()
    for op in operations:
        if not op.get("compensation_flag"):
            continue
        parsed = parse_ddmmyyyy(op.get("date"))
        nick = (op.get("nick") or "").strip().lower()
        if parsed and nick:
            # parse_ddmmyyyy returns (year, month, day) — not the display order.
            already.add((nick, parsed[1], parsed[0]))

    overrides = {}
    for nick, amount in (amount_by_nick or {}).items():
        overrides[(nick or "").strip().lower()] = amount

    items = []
    for raw_nick in nicks:
        requested = (raw_nick or "").strip()
        key = requested.lower()
        member = roster.get(key)
        for raw_month in months:
            month = _as_month(raw_month)
            item = {
                "nick": member[0] if member else requested,
                "month": month if month is not None else raw_month,
                "year": year,
                "amount": 0,
                "action": CREATE,
                "reason": None,
            }

            if month is None or year < MIN_YEAR:
                item.update(action=BLOCKED, reason=BAD_PERIOD)
            elif (year, month) > today_ym:
                item.update(action=BLOCKED, reason=FUTURE_MONTH)
            elif (month, year) in closed:
                item.update(action=BLOCKED, reason=MONTH_CLOSED)
            elif not member:
                item.update(action=SKIP, reason=UNKNOWN_NICK)
            else:
                amount = overrides.get(key)
                if amount is None:
                    amount = norm_for_level(member[1])
                amount = _as_amount(amount)
                if amount <= 0:
                    item.update(action=SKIP, reason=NO_NORM)
                elif (key, month, year) in already:
                    item["amount"] = amount
                    item.update(action=SKIP, reason=ALREADY_COMPENSATED)
                else:
                    item["amount"] = amount

            items.append(item)

    by_reason = {}
    for item in items:
        if item["reason"]:
            by_reason[item["reason"]] = by_reason.get(item["reason"], 0) + 1

    return {
        "items": items,
        "totals": {
            "pairs": len(items),
            "create": sum(1 for i in items if i["action"] == CREATE),
            "skip": sum(1 for i in items if i["action"] == SKIP),
            "blocked": sum(1 for i in items if i["action"] == BLOCKED),
        },
        "by_reason": {code: by_reason.get(code, 0) for code in REASONS if by_reason.get(code)},
        "labels": REASONS,
        "today": today.isoformat(),
    }
