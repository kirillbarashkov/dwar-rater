"""Tax carry-over engine — PURE (no Flask, no DB, no clock).

Mirrors the tax rules the UI already computes in
``frontend/src/utils/treasury.ts`` and ``components/clan/TaxAnalytics.tsx``:

  * a **real** tax payment is ``operation_type == 'Деньги'`` and
    ``object_name == 'Монеты'``, ``quantity > 0`` and
    ``compensation_flag`` falsy. Flagged rows are bookkeeping markers of the
    existing «зачёт» feature — not money. Counting them would invent a phantom
    credit (a compensated month looks "overpaid" to the UI, see
    ``isOver`` in TaxAnalytics), so they are deliberately excluded here.
  * the monthly norm comes from the member's level
    (``TAX_NORM_BY_LEVEL``, ``DEFAULT_NORM`` as the fallback);
  * a member starts paying the month AFTER joining
    (``join_date``, or ``trial_until`` when there is no join date);
  * an overpayment is ``paid + carried_in - norm > 0``; the whole excess is
    carried to the next month and a remainder flows further by the same rule.
    Each carry is subtracted from the next month's balance, so the same money
    can never be carried twice.

Decisions supplied by the caller: ``(nick_lower, source_month, source_year) ->
{'status': 'confirmed' | 'cancelled', 'amount': int}``. A ``confirmed`` decision
fixes the carried amount; ``cancelled`` means explicitly "no carry out of this
month" and the month is never re-proposed.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Optional, Sequence

TAX_OPERATION_TYPE = "Деньги"
TAX_OBJECT_NAME = "Монеты"
DEFAULT_NORM = 10
STATUS_PENDING = "pending"
STATUS_CONFIRMED = "confirmed"
STATUS_CANCELLED = "cancelled"
ALL_STATUSES = (STATUS_PENDING, STATUS_CONFIRMED, STATUS_CANCELLED)

# Months the chain may look back from the target month. dwarf's own report only
# keeps ~6 months, so this is a safety bound, not a real limit.
MAX_LOOKBACK_MONTHS = 24

# Mirror of frontend/src/utils/treasury.ts::CLAN_TAX_NORM — keep both in sync
# (same trap as TALENT_RESOURCES: a rule that lives in two places drifts).
TAX_NORM_BY_LEVEL = {
    1: 10, 2: 10, 3: 10, 4: 10, 5: 10,
    6: 15, 7: 15, 8: 15,
    9: 20, 10: 20,
    11: 25, 12: 25,
    13: 50, 14: 50, 15: 50,
    16: 100, 17: 100, 18: 100, 19: 100, 20: 100,
}


@dataclass(frozen=True)
class Carryover:
    """One month→month hop: ``amount`` overpaid in (source) flows to source+1."""

    nick: str
    source_month: int
    source_year: int
    amount: int

    def as_dict(self) -> dict:
        return {
            "nick": self.nick,
            "source_month": self.source_month,
            "source_year": self.source_year,
            "amount": self.amount,
        }


# --------------------------------------------------------------------------- #
# month / date helpers
# --------------------------------------------------------------------------- #


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_ddmmyyyy(value: Any) -> Optional[tuple]:
    """Parse ``DD.MM.YYYY`` (optionally with a time part) -> (year, month, day)."""
    if not value or not isinstance(value, str):
        return None
    parts = value.strip().split()[0].split(".")
    if len(parts) < 3:
        return None
    try:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return year, month, day


def month_key(value: Any) -> Optional[tuple]:
    """(month, year) of an operation date string, or None if unparsable."""
    parsed = parse_ddmmyyyy(value)
    if not parsed:
        return None
    year, month, _day = parsed
    return month, year


def ym_index(month: int, year: int) -> int:
    return year * 12 + (month - 1)


def index_to_ym(index: int) -> tuple:
    return index % 12 + 1, index // 12


def add_months(month: int, year: int, delta: int) -> tuple:
    return index_to_ym(ym_index(month, year) + delta)


def next_ym(month: int, year: int) -> tuple:
    return add_months(month, year, 1)


def prev_ym(month: int, year: int) -> tuple:
    return add_months(month, year, -1)


def is_month_closed(month: int, year: int, today: Optional[date] = None) -> bool:
    """True when the month has fully passed — only closed months are persisted."""
    today = today or date.today()
    return ym_index(month, year) < ym_index(today.month, today.year)


# --------------------------------------------------------------------------- #
# member rules
# --------------------------------------------------------------------------- #


def norm_for_level(level: Any) -> int:
    return TAX_NORM_BY_LEVEL.get(_as_int(level, 0), DEFAULT_NORM)


def payment_start_ym(member: Mapping[str, Any], today: Optional[date] = None) -> Optional[tuple]:
    """First month the member owes tax, or None when they always owed it.

    Mirrors ``TaxAnalytics.getPaymentStartMonth``: a member pays from the month
    after joining; without a join date ``trial_until`` is used, and an expired
    trial is treated as "joined 14 days before it ended".
    """
    today = today or date.today()

    joined = parse_ddmmyyyy(member.get("join_date"))
    if joined:
        return next_ym(joined[1], joined[0])

    trial = parse_ddmmyyyy(member.get("trial_until"))
    if trial:
        year, month, day = trial
        try:
            trial_date = date(year, month, day)
        except ValueError:
            return next_ym(month, year)
        if trial_date < today:
            join_date = trial_date - timedelta(days=14)
            return next_ym(join_date.month, join_date.year)
        return next_ym(month, year)

    return None


def level_at_month_end(events: Sequence[Mapping[str, Any]], month: int, year: int) -> Optional[int]:
    """Member level as of the end of (month, year) from level-change events.

    Events are parsed and sorted here on purpose: the stored ``event_date`` is
    ``DD.MM.YYYY``, which sorts incorrectly as a string across years.
    """
    boundary = ym_index(month, year)
    level = None
    for event in sorted(
        events,
        key=lambda e: (parse_ddmmyyyy(e.get("date")) or (0, 0, 0)),
    ):
        parsed = parse_ddmmyyyy(event.get("date"))
        if not parsed:
            continue
        event_year, event_month, _day = parsed
        if ym_index(event_month, event_year) <= boundary:
            level = _as_int(event.get("new_level"), level or 0)
        else:
            break
    return level


def is_real_payment(op: Mapping[str, Any]) -> bool:
    return (
        (op.get("operation_type") or "") == TAX_OPERATION_TYPE
        and (op.get("object_name") or "") == TAX_OBJECT_NAME
        and _as_int(op.get("quantity")) > 0
        and not op.get("compensation_flag")
    )


# --------------------------------------------------------------------------- #
# engine
# --------------------------------------------------------------------------- #


def compute_carryovers(
    operations: Iterable[Mapping[str, Any]],
    members: Iterable[Mapping[str, Any]],
    level_events: Mapping[str, Sequence[Mapping[str, Any]]],
    decisions: Mapping[tuple, Mapping[str, Any]],
    target_month: int,
    target_year: int,
    today: Optional[date] = None,
    max_lookback: int = MAX_LOOKBACK_MONTHS,
) -> list:
    """Proposals arising FROM (target_month, target_year).

    Only currently active members can receive a carry-over: a member who left
    has nobody to credit next month, so their excess is not proposed.
    """
    today = today or date.today()
    target_index = ym_index(target_month, target_year)

    paid: dict = {}
    op_indexes = []
    for op in operations:
        key = month_key(op.get("date"))
        if not key:
            continue
        month, year = key
        op_indexes.append(ym_index(month, year))
        if not is_real_payment(op):
            continue
        nick = (op.get("nick") or "").strip().lower()
        if not nick:
            continue
        bucket = (nick, month, year)
        paid[bucket] = paid.get(bucket, 0) + _as_int(op.get("quantity"))

    if not op_indexes:
        return []

    start_index = max(min(op_indexes), target_index - max_lookback)

    active = [m for m in members if not m.get("is_deleted")]
    display_nick, level_now, start_due = {}, {}, {}
    for member in active:
        nick = (member.get("nick") or "").strip().lower()
        if not nick:
            continue
        display_nick[nick] = member.get("nick")
        level_now[nick] = member.get("level")
        start_due[nick] = payment_start_ym(member, today)

    if not display_nick:
        return []

    carried = {nick: 0 for nick in display_nick}
    proposals = []

    for index in range(start_index, target_index + 1):
        month, year = index_to_ym(index)
        next_carried = {}
        for nick in display_nick:
            decision = decisions.get((nick, month, year))
            if decision:
                # Already reviewed: a confirmation fixes the amount, a
                # cancellation means "no carry from here" — never re-proposed.
                if (decision.get("status") or "") == STATUS_CONFIRMED:
                    next_carried[nick] = _as_int(decision.get("amount"))
                else:
                    next_carried[nick] = 0
                continue

            start = start_due[nick]
            owes = start is None or index >= ym_index(start[0], start[1])
            if owes:
                level = level_at_month_end(level_events.get(nick, ()), month, year)
                if level is None:
                    level = level_now[nick]
                norm = norm_for_level(level) if level else DEFAULT_NORM
            else:
                norm = 0

            balance = paid.get((nick, month, year), 0) + carried[nick] - norm
            carry = balance if balance > 0 else 0
            next_carried[nick] = carry

            if index == target_index and carry > 0:
                proposals.append(
                    Carryover(
                        nick=display_nick[nick],
                        source_month=month,
                        source_year=year,
                        amount=carry,
                    )
                )

        carried = next_carried

    proposals.sort(key=lambda p: (-p.amount, p.nick.lower()))
    return proposals
