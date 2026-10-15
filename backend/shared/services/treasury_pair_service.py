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
KIND_TALENTS = 'talents'
STATUS_CANDIDATE = 'candidate'
STATUS_CONFIRMED = 'confirmed'
STATUS_REJECTED = 'rejected'
STATUS_SPLIT = 'split'


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


def split_pair(
    pair: TreasuryOperationPair,
    keep: str,
    user_id: int | None = None,
    comment: str = '',
) -> TreasuryOperationPair:
    """Разрыв пары: указанная операция — списание на таланты, вторая возвращается в очередь.

    Списание на таланты клана делает глава или совет: операция всегда минусовая и пары
    у неё нет. Автоматика иногда сшивает её с чем-то похожим, поэтому казначей указывает,
    какую сторону оставить списанием, а вторая снова становится кандидатом.

    `apply_pair_class` здесь намеренно не вызывается: он раздаёт классы по статусу пары
    и вернул бы списанию «tax».
    """
    if keep not in ('first', 'second'):
        raise PairError(f'неизвестная сторона пары: {keep}')

    kept_id = pair.first_op_id if keep == 'first' else pair.second_op_id
    other_id = pair.second_op_id if keep == 'first' else pair.first_op_id

    kept = db.session.get(TreasuryOperation, kept_id) if kept_id else None
    if not kept:
        raise PairError('операция для списания не найдена')

    kept.op_class = 'neutral'
    kept.class_kind = KIND_TALENTS
    kept.class_source = 'manual'

    other = db.session.get(TreasuryOperation, other_id) if other_id else None
    if other:
        other.op_class = 'tax'
        other.class_kind = ''
        other.class_source = ''

    old = {'status': pair.status, 'kind': pair.kind}
    pair.status = STATUS_SPLIT
    if comment:
        pair.comment = comment
    db.session.add(
        TreasuryPairRevision(
            pair_id=pair.id,
            changed_by=user_id,
            old_value=json.dumps(old, ensure_ascii=False),
            new_value=json.dumps(
                {'status': pair.status, 'kept': keep, 'class_kind': KIND_TALENTS},
                ensure_ascii=False,
            ),
            comment=comment or 'разрыв пары: списание на таланты клана',
        )
    )
    return pair


def restore_pair(
    pair: TreasuryOperationPair, user_id: int | None = None
) -> TreasuryOperationPair:
    """Возврат пары в очередь кандидатов — отмена решения казначея.

    Пара не удаляется и история не стирается: это именно возврат. Операции снова
    становятся учитываемыми, поэтому расчёты вернутся к прежним значениям.
    """
    if pair.status == STATUS_CANDIDATE:
        raise PairError('пара и так в очереди кандидатов')

    old = {'status': pair.status, 'kind': pair.kind}
    pair.status = STATUS_CANDIDATE
    pair.confirmed_at = None
    pair.confirmed_by = None
    apply_pair_class(pair)
    db.session.add(
        TreasuryPairRevision(
            pair_id=pair.id,
            changed_by=user_id,
            old_value=json.dumps(old, ensure_ascii=False),
            new_value=json.dumps({'status': pair.status}, ensure_ascii=False),
            comment='возврат пары в очередь кандидатов',
        )
    )
    return pair


def pair_history(pair: TreasuryOperationPair) -> list:
    """История решений по паре: правки из лога и действия из аудита, от старых к новым.

    Два источника, потому что и пишут их разные места: правки — сервис, действия —
    маршруты. Оба хранят старое и новое значение, поэтому история собирается честно.

    Ник человека берём через связь `AuditLog.user`, а не импортом модели `User`:
    она объявлена не рядом с `AuditLog`, и импорт оттуда падает.
    """
    from shared.rbac.models import AuditLog

    raw = []
    names = {}

    for rev in (
        TreasuryPairRevision.query.filter_by(pair_id=pair.id)
        .order_by(TreasuryPairRevision.id)
        .all()
    ):
        raw.append(
            {
                'source': 'revision',
                'action': 'revision',
                'changed_by': rev.changed_by,
                'changed_by_name': None,
                'old': rev.old_value,
                'new': rev.new_value,
                'comment': rev.comment or '',
                'at': rev.changed_at.isoformat() if rev.changed_at else None,
            }
        )

    for entry in (
        AuditLog.query.filter_by(target_type='treasury_pair', target_id=pair.id)
        .order_by(AuditLog.id)
        .all()
    ):
        user = entry.user
        name = (getattr(user, 'username', None) or '—') if user else '—'
        if entry.user_id:
            names[entry.user_id] = name
        raw.append(
            {
                'source': 'audit',
                'action': entry.action,
                'changed_by': entry.user_id,
                'changed_by_name': name,
                'old': entry.old_value,
                'new': entry.new_value,
                'comment': '',
                'at': entry.created_at.isoformat() if entry.created_at else None,
            }
        )

    raw.sort(key=lambda item: item.get('at') or '')
    for item in raw:
        if item.get('changed_by_name') is None:
            item['changed_by_name'] = names.get(item['changed_by']) or '—'
    return raw


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


def batch_decide(
    pairs,
    action: str,
    kind: str | None = None,
    user_id: int | None = None,
) -> dict:
    """Групповое решение по пачке пар: подтвердить или отклонить.

    Ошибка на одной паре не должна гасить остальные — иначе казначей не поймёт,
    что именно не прошло. Поэтому результат приходит по каждой паре отдельно.
    """
    if action not in ('confirm', 'reject'):
        raise PairError(f'неизвестное действие: {action}')
    if action == 'confirm' and kind not in PAIR_KINDS:
        raise PairError(f'неизвестный тип пары: {kind}')

    done = []
    failed = []
    for pair in pairs:
        try:
            if action == 'confirm':
                confirm_pair(pair, kind, user_id=user_id)
            else:
                reject_pair(pair)
            done.append(pair.id)
        except PairError as exc:
            failed.append({'id': pair.id, 'error': str(exc)})

    return {'done': done, 'failed': failed}


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
            'class_kind': op.class_kind,
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
