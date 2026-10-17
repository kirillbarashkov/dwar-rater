"""Поиск пар операций казны: обмены и долги.

Автоматика НЕ классифицирует. Она находит первое событие и подставляет набор
кандидатов на второе — решение принимает казначей. Без подтверждённой пары
операция остаётся учитываемой (`op_class = 'tax'`), поэтому этот модуль сам по
себе расчёты не меняет.

Почему по нику и дате, а не по сумме: в казне операции обмена почти всегда
совпадают по нику и близки по дате, а суммы у денег и ресурсов несопоставимы
(монеты против штук ресурса). Совпадение суммы годится как дополнительный сигнал,
но не как основание.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterable, Mapping

from shared.services.tax_engine import is_money_operation, parse_ddmmyyyy

# Окно поиска второй стороны. Операции обмена могут попадать в разные дни, поэтому
# это параметр поиска, а не жёсткое правило.
DEFAULT_WINDOW_DAYS = 1
DEFAULT_LIMIT = 20
# Порог уверенности для жадного сопоставления. 6 — это тот же день, противоположные
# знаки и разные объекты (ресурс на ресурс). Ниже — совпадения по дню и знаку без
# подтверждающих признаков; на реальных данных таких оказалось 16 тысяч.
DEFAULT_MIN_SCORE = 6


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _op_date(op: Mapping[str, Any]) -> date | None:
    """Дата операции. В базе это текст DD.MM.YYYY — сравнивать строками нельзя."""
    parsed = parse_ddmmyyyy(op.get('date'))
    if not parsed:
        return None
    year, month, day = parsed
    return date(year, month, day)


def candidate_score(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> int:
    """Насколько вторая операция похожа на пару к первой. 0 — не подходит.

    Сигналы: тот же ник, близость даты, противоположные знаки, разные объекты.
    Совпадение «деньги против ресурса» весит больше: это самый частый случай
    в казне (положил деньги — забрал ресурс и наоборот).
    """
    if (first.get('nick') or '').strip().lower() != (
        second.get('nick') or ''
    ).strip().lower():
        return 0
    if first.get('id') is not None and first.get('id') == second.get('id'):
        return 0

    d1, d2 = _op_date(first), _op_date(second)
    if not d1 or not d2:
        return 0
    delta = abs((d1 - d2).days)
    if delta > window_days:
        return 0

    q1, q2 = _as_int(first.get('quantity')), _as_int(second.get('quantity'))
    if q1 == 0 or q2 == 0:
        return 0
    # Противоположные знаки: одна сторона отдаёт, другая получает.
    if (q1 > 0) == (q2 > 0):
        return 0

    o1 = (first.get('object_name') or '').strip()
    o2 = (second.get('object_name') or '').strip()
    if o1 and o1 == o2:
        # Тот же объект с обратным знаком — это сторно/отмена, а не обмен.
        return 0

    score = 3 if delta == 0 else 1
    score += 2
    if o1 != o2:
        score += 1
    if is_money_operation(first) != is_money_operation(second):
        score += 2
    return score


def find_candidates(
    first: Mapping[str, Any],
    operations: Iterable[Mapping[str, Any]],
    window_days: int = DEFAULT_WINDOW_DAYS,
    limit: int = DEFAULT_LIMIT,
) -> list[tuple[int, Mapping[str, Any]]]:
    """Кандидаты на вторую сторону, по убыванию уверенности."""
    scored: list[tuple[int, Mapping[str, Any]]] = []
    for op in operations:
        score = candidate_score(first, op, window_days)
        if score > 0:
            scored.append((score, op))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get('date') or '')))
    return scored[:limit]


def _describe(op: Mapping[str, Any]) -> str:
    return (
        f"{op.get('operation_type') or '?'} {op.get('object_name') or '?'} "
        f"{_as_int(op.get('quantity')):+d}"
    )


def _prepare(op: Mapping[str, Any]) -> tuple | None:
    """Разбор операции один раз: дата, количество, объект.

    Без этого вес пары парсит дату на каждом сравнении — на реальных данных казны
    это 5.5 млн сравнений и 30 секунд.
    """
    parsed = _op_date(op)
    if not parsed:
        return None
    return (op, parsed, _as_int(op.get('quantity')), (op.get('object_name') or '').strip())


def _can_pair(first: tuple, second: tuple, window_days: int) -> bool:
    """Дешёвая отсечка: может ли пара вообще дать score > 0.

    Повторяет условия `candidate_score` ровно, но без вычисления веса. Ник уже
    совпадает — операции лежат в одной корзине по нику.
    """
    op1, d1, q1, o1 = first
    op2, d2, q2, o2 = second
    if op1.get('id') is not None and op1.get('id') == op2.get('id'):
        return False
    if abs((d1 - d2).days) > window_days:
        return False
    if q1 == 0 or q2 == 0:
        return False
    if (q1 > 0) == (q2 > 0):
        return False
    if o1 and o1 == o2:
        return False
    return True


def match_pairs(
    operations: Iterable[Mapping[str, Any]],
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_score: int = DEFAULT_MIN_SCORE,
) -> list[tuple[int, Mapping[str, Any], Mapping[str, Any]]]:
    """Жадное сопоставление 1:1: операция участвует максимум в одной паре.

    Без этого одна операция становится кандидатом для десятков других. Проверено
    на реальных данных казны: 15 432 операции давали 32 269 «пар», из них около
    30 тысяч — совпадения по дню и знаку без участия денег. Жадный отбор по
    убыванию уверенности плюс порог убирают этот шум.

    Порядок обхода и сортировка сохранены как были: при равных весах победитель
    определяется порядком операций, и менять его — значит менять результат.
    """
    prepared = [item for item in (_prepare(op) for op in operations) if item]

    by_nick: dict[str, list[tuple]] = defaultdict(list)
    for item in prepared:
        by_nick[(item[0].get('nick') or '').strip().lower()].append(item)

    candidates: list[tuple[int, Mapping[str, Any], Mapping[str, Any]]] = []
    for nick_ops in by_nick.values():
        # Индекс по датам: сравнивать операции из разных дней незачем — окно поиска
        # 1–2 дня, а ники с тысячами операций дают миллионы заведомо пустых сравнений.
        by_date: dict[date, list[int]] = defaultdict(list)
        for index, item in enumerate(nick_ops):
            by_date[item[1]].append(index)

        for i, first in enumerate(nick_ops):
            day = first[1]
            partners: list[int] = []
            for shift in range(-window_days, window_days + 1):
                partners.extend(by_date.get(day + timedelta(days=shift), ()))

            # Партнёры по возрастанию индекса — ровно тот порядок, в котором их
            # обходил прежний двойной цикл. Порядок важен: при равных весах
            # победителя определяет он, и перестановка меняет результат.
            for j in sorted(index for index in partners if index > i):
                second = nick_ops[j]
                if not _can_pair(first, second, window_days):
                    continue
                score = candidate_score(first[0], second[0], window_days)
                if score >= min_score:
                    candidates.append((score, first[0], second[0]))

    candidates.sort(key=lambda item: -item[0])
    used: set = set()
    result: list[tuple[int, Mapping[str, Any], Mapping[str, Any]]] = []
    for score, first, second in candidates:
        if first.get('id') in used or second.get('id') in used:
            continue
        used.add(first.get('id'))
        used.add(second.get('id'))
        result.append((score, first, second))
    return result


def dry_run(
    operations: Iterable[Mapping[str, Any]],
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_score: int = DEFAULT_MIN_SCORE,
) -> list[dict[str, Any]]:
    """Отчёт по истории: какие пары нашлись. В базу НЕ пишет.

    Возвращает список пар с оценкой уверенности и кратким описанием сторон —
    ровно то, что нужно показать владельцу перед применением.
    """
    pairs = [
        {
            'score': score,
            'nick': first.get('nick'),
            'date': first.get('date'),
            'first': _describe(first),
            'second': _describe(second),
            'money_involved': is_money_operation(first) or is_money_operation(second),
        }
        for score, first, second in match_pairs(operations, window_days, min_score)
    ]
    pairs.sort(key=lambda pair: (-pair['score'], str(pair['date'] or '')))
    return pairs
