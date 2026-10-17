"""Займы из казны: минусовые операции, не закрытые подтверждённой парой.

Не путать с «долгом» из «Статуса персонажа» и сводки: там `debt` — это недосдача
налога (`норма − покрыто`), совсем другое понятие. Здесь заём: участник взял из
казны и не вернул.

Закрывает заём подтверждённая пара (обе операции становятся нейтральными) или
списание на таланты клана. Пока этого не произошло, минусовая операция учитывается
(`op_class = 'tax'`) — значит, взятое числится за человеком.

Причина, по которой заём открыт, показывается отдельно: «пары нет», «ждёт разбора»,
«пара отклонена», «пара разорвана». Без этого казначей видит сумму и не понимает,
что с ней делать.
"""

from __future__ import annotations

from shared.models import db
from shared.models.clan_info import TreasuryOperation, TreasuryOperationPair
from shared.services.tax_engine import parse_ddmmyyyy

REASON_NONE = 'none'
REASON_CANDIDATE = 'candidate'
REASON_REJECTED = 'rejected'
REASON_SPLIT = 'split'

REASON_LABELS = {
    REASON_NONE: 'пары нет',
    REASON_CANDIDATE: 'ждёт разбора',
    REASON_REJECTED: 'пара отклонена',
    REASON_SPLIT: 'пара разорвана',
}

# Классы, при которых минусовая операция уже не числится за человеком: нейтральная
# (подтверждённая пара или списание на таланты) и исключённая правилом группы.
CLOSED_CLASSES = ('neutral', 'excluded')


def _reason(pair_status: str | None) -> str:
    if pair_status is None:
        return REASON_NONE
    if pair_status == 'candidate':
        return REASON_CANDIDATE
    if pair_status == 'rejected':
        return REASON_REJECTED
    return REASON_SPLIT


def _pair_index(clan_id: int) -> dict[int, tuple[int, str]]:
    """Операция → (id пары, статус). Пара ищется по обеим сторонам."""
    rows = (
        db.session.query(
            TreasuryOperationPair.id,
            TreasuryOperationPair.first_op_id,
            TreasuryOperationPair.second_op_id,
            TreasuryOperationPair.status,
        )
        .filter(TreasuryOperationPair.clan_id == clan_id)
        .all()
    )
    index: dict[int, tuple[int, str]] = {}
    for pair_id, first_id, second_id, status in rows:
        for op_id in (first_id, second_id):
            if op_id:
                index[op_id] = (pair_id, status)
    return index


def _operation_rows(clan_id: int) -> list[tuple]:
    return (
        db.session.query(
            TreasuryOperation.id,
            TreasuryOperation.nick,
            TreasuryOperation.date,
            TreasuryOperation.operation_type,
            TreasuryOperation.object_name,
            TreasuryOperation.quantity,
            TreasuryOperation.op_class,
        )
        .filter(
            TreasuryOperation.clan_id == clan_id,
            TreasuryOperation.quantity < 0,
        )
        .order_by(TreasuryOperation.id)
        .all()
    )


def collect_loans(clan_id: int, nick: str | None = None) -> dict:
    """Открытые займы: сводка по людям и, если указан ник, операции этого человека.

    Сводку отдаём отдельно от операций: минусовых операций тысячи, и тянуть их все
    в один ответ незачем — казначей раскрывает одного человека за раз.
    """
    pairs = _pair_index(clan_id)

    people: dict[str, dict] = {}
    operations: list[dict] = []
    excluded_hidden = 0

    for op_id, op_nick, date, op_type, object_name, quantity, op_class in _operation_rows(clan_id):
        if op_class == 'excluded':
            # Правило группы вывело объект из отчётов — заём тут считать нечего.
            excluded_hidden += 1
            continue
        if op_class in CLOSED_CLASSES:
            # Подтверждённая пара или списание на таланты: за человеком не числится.
            continue

        pair_info = pairs.get(op_id)
        reason = _reason(pair_info[1] if pair_info else None)
        taken = abs(int(quantity or 0))
        parsed = parse_ddmmyyyy(date)

        bucket = people.setdefault(
            op_nick or '',
            {
                'nick': op_nick or '',
                'count': 0,
                'taken': 0,
                'first_date': date,
                'last_date': date,
                'first_key': None,
                'last_key': None,
                'reasons': {},
            },
        )
        bucket['count'] += 1
        bucket['taken'] += taken
        bucket['reasons'][reason] = bucket['reasons'].get(reason, 0) + 1
        if parsed:
            if bucket['first_key'] is None or parsed < bucket['first_key']:
                bucket['first_key'] = parsed
                bucket['first_date'] = date
            if bucket['last_key'] is None or parsed > bucket['last_key']:
                bucket['last_key'] = parsed
                bucket['last_date'] = date

        operations.append(
            {
                'id': op_id,
                'nick': op_nick or '',
                'date': date,
                'operation_type': op_type,
                'object_name': object_name,
                'quantity': quantity,
                'taken': taken,
                'reason': reason,
                'pair_id': pair_info[0] if pair_info else None,
                'pair_status': pair_info[1] if pair_info else None,
            }
        )

    summary = sorted(people.values(), key=lambda row: -row['taken'])
    for row in summary:
        row.pop('first_key', None)
        row.pop('last_key', None)

    result = {
        'people': summary,
        'totals': {
            'people': len(summary),
            'ops': len(operations),
            'taken': sum(row['taken'] for row in summary),
            # Сколько минусовых операций скрыто правилами групп исключений.
            'excluded_hidden': excluded_hidden,
        },
        'reason_labels': REASON_LABELS,
    }

    if nick:
        wanted = nick.strip().lower()
        result['ops'] = [
            op for op in operations if (op['nick'] or '').lower() == wanted
        ]
    return result
