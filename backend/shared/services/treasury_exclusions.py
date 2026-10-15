"""Группы исключений казны: правила и их применение к операциям.

Админ или казначей сам заводит группы, называет их и наполняет типами ресурсов.
Сопоставление — по началу названия: правило «Сущность» ловит и «Сущность кретса»,
и «Сущность корра».

Два режима:
* `exclude` — операция не попадает ни в один отчёт казны (`op_class='excluded'`);
* `neutral` — операция не считается сдачей, но остаётся видимой в журнале и истории.
"""

from __future__ import annotations

MODE_EXCLUDE = 'exclude'
MODE_NEUTRAL = 'neutral'
MODES = (MODE_EXCLUDE, MODE_NEUTRAL)

CLASS_EXCLUDED = 'excluded'


def rule_matches(prefix: str, object_name: str) -> bool:
    """Сопоставление по началу названия, без учёта регистра и лишних пробелов."""
    if not prefix or not object_name:
        return False
    return object_name.strip().lower().startswith(prefix.strip().lower())


def group_as_dict(group) -> dict:
    """Представление группы для интерфейса: правила идут вместе с ней."""
    return {
        'id': group.id,
        'name': group.name,
        'mode': group.mode,
        'comment': group.comment or '',
        'is_active': bool(group.is_active),
        'created_at': group.created_at.isoformat() if group.created_at else None,
        'rules': [
            {'id': rule.id, 'prefix': rule.prefix}
            for rule in sorted(group.rules, key=lambda item: item.id)
        ],
    }


def match_group(groups, object_name: str):
    """Первая подходящая активная группа для названия ресурса."""
    for group in groups:
        if not group.is_active:
            continue
        for rule in group.rules:
            if rule_matches(rule.prefix, object_name):
                return group
    return None


def apply_exclusions(operations, groups) -> int:
    """Проставляет класс операциям по группам исключений. Возвращает число изменённых.

    Операции, которые казначей уже отнёс к паре (`class_source='manual'`), не трогаем:
    решение человека важнее автоматического правила.
    """
    changed = 0
    for op in operations:
        if (op.class_source or '') == 'manual':
            continue

        group = match_group(groups, op.object_name or '')
        if not group:
            continue

        if group.mode == MODE_EXCLUDE:
            target_class, target_kind = CLASS_EXCLUDED, ''
        else:
            target_class, target_kind = 'neutral', 'group'

        if op.op_class != target_class or (op.class_kind or '') != target_kind:
            op.op_class = target_class
            op.class_kind = target_kind
            op.class_source = 'group'
            changed += 1

    return changed
