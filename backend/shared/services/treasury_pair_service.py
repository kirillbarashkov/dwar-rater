"""Пары казны: подтверждение, отклонение, корректировка.

Источник истины — пара, а не поля на операциях. Подтверждение переводит обе операции
в `neutral`: только после этого они перестают учитываться в налоге и ресурсах.
Отмена подтверждения возвращает их в `tax`.

Аудит (`audit_log`) пишут маршруты — здесь только бизнес-логика, чтобы не заводить
второй способ записи истории. Корректировки пары дополнительно логируются в
`treasury_pair_revision`: требование владельца — история изменений сохраняется.
"""

from __future__ import annotations

import json
from datetime import datetime

from shared.models import db
from shared.models.clan_info import (
    TreasuryOperation,
    TreasuryOperationPair,
    TreasuryPairRevision,
)

PAIR_KINDS = ('exchange', 'loan')
STATUS_CANDIDATE = 'candidate'
STATUS_CONFIRMED = 'confirmed'
STATUS_REJECTED = 'rejected'


class PairError(ValueError):
    """Нарушение правила пары. Маршруты превращают это в 400."""


def apply_pair_class(pair: TreasuryOperationPair) -> None:
    """Пересчитывает op_class у операций пары.

    Подтверждённая пара — операции нейтральные (не идут в налог и ресурсы).
    В остальных статусах они учитываемые, как и были до классификации.
    """
    neutral = pair.status == STATUS_CONFIRMED
    for op_id in (pair.first_op_id, pair.second_op_id):
        if not op_id:
            continue
        op = db.session.get(TreasuryOperation, op_id)
        if not op:
            continue
        op.op_class = 'neutral' if neutral else 'tax'
        op.class_kind = pair.kind if neutral else ''
        op.class_source = 'manual' if neutral else ''


def confirm_pair(
    pair: TreasuryOperationPair, kind: str, user_id: int | None = None
) -> TreasuryOperationPair:
    """Подтверждение пары казначеем. Тип выбирает человек: обмен или долг."""
    if kind not in PAIR_KINDS:
        raise PairError(f'неизвестный тип пары: {kind}')
    if pair.status == STATUS_CONFIRMED:
        raise PairError('пара уже подтверждена')
    pair.kind = kind
    pair.status = STATUS_CONFIRMED
    pair.confirmed_at = datetime.utcnow()
    pair.confirmed_by = user_id
    apply_pair_class(pair)
    return pair


def reject_pair(pair: TreasuryOperationPair) -> TreasuryOperationPair:
    """Отклонение пары: операции остаются учитываемыми."""
    if pair.status == STATUS_CONFIRMED:
        raise PairError('подтверждённую пару сначала нужно отменить')
    pair.status = STATUS_REJECTED
    apply_pair_class(pair)
    return pair


def unconfirm_pair(pair: TreasuryOperationPair) -> TreasuryOperationPair:
    """Отмена подтверждения: операции возвращаются в учитываемые."""
    if pair.status != STATUS_CONFIRMED:
        raise PairError('пара не подтверждена')
    pair.status = STATUS_CANDIDATE
    pair.confirmed_at = None
    pair.confirmed_by = None
    apply_pair_class(pair)
    return pair


def revise_pair(
    pair: TreasuryOperationPair,
    new_kind: str,
    comment: str = '',
    user_id: int | None = None,
) -> TreasuryOperationPair:
    """Корректировка пары с записью в лог.

    Требование владельца: корректировка возможна в модальном окне, а лог изменений
    сохраняется. Поэтому пишем и старое, и новое значение.
    """
    if new_kind not in PAIR_KINDS:
        raise PairError(f'неизвестный тип пары: {new_kind}')
    old = {'kind': pair.kind, 'status': pair.status}
    pair.kind = new_kind
    apply_pair_class(pair)
    db.session.add(
        TreasuryPairRevision(
            pair_id=pair.id,
            changed_by=user_id,
            old_value=json.dumps(old, ensure_ascii=False),
            new_value=json.dumps(
                {'kind': pair.kind, 'status': pair.status}, ensure_ascii=False
            ),
            comment=comment or '',
        )
    )
    return pair


def pair_as_dict(pair: TreasuryOperationPair) -> dict:
    """Представление пары для интерфейса: обе стороны + служебные поля."""
    def side(op: TreasuryOperation | None) -> dict | None:
        if not op:
            return None
        return {
            'id': op.id,
            'date': op.date,
            'nick': op.nick,
            'operation_type': op.operation_type,
            'object_name': op.object_name,
            'quantity': op.quantity,
            'op_class': op.op_class,
        }

    return {
        'id': pair.id,
        'kind': pair.kind,
        'status': pair.status,
        'comment': pair.comment,
        'created_at': pair.created_at.isoformat() if pair.created_at else None,
        'confirmed_at': pair.confirmed_at.isoformat() if pair.confirmed_at else None,
        'first': side(pair.first_op),
        'second': side(pair.second_op),
    }
