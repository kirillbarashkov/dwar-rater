"""Нейтральные операции (подтверждённый обмен или долг) в налог не идут."""

from shared.services.tax_engine import _classify, is_real_payment

BUCKET = ('__taxprobe__', 10, 2026)


def _money(quantity=100, op_class='tax', compensation=False):
    return {
        'date': '05.10.2026',
        'nick': '__TaxProbe__',
        'operation_type': 'Деньги',
        'object_name': 'Монеты',
        'quantity': quantity,
        'compensation_flag': compensation,
        'op_class': op_class,
    }


def test_neutral_operation_is_not_a_payment():
    assert is_real_payment(_money()) is True
    assert is_real_payment(_money(op_class='neutral')) is False


def test_missing_op_class_still_counts():
    """У старых записей поля нет — поведение не меняется."""
    op = _money()
    op.pop('op_class')
    assert is_real_payment(op) is True


def test_compensation_marker_still_not_a_payment():
    assert is_real_payment(_money(compensation=True)) is False


def test_classify_skips_neutral_money():
    """Главная проверка этапа: нейтральная сумма не попадает в сдачу."""
    ops = [_money(quantity=100), _money(quantity=50, op_class='neutral')]
    _, paid, _ = _classify(ops)
    assert paid[BUCKET] == 100


def test_classify_counts_operations_without_op_class():
    ops = [_money(quantity=100), _money(quantity=50)]
    for op in ops:
        op.pop('op_class')
    _, paid, _ = _classify(ops)
    assert paid[BUCKET] == 150


def test_classify_keeps_compensation_separate():
    ops = [_money(quantity=100), _money(quantity=30, compensation=True)]
    _, paid, compensation = _classify(ops)
    assert paid[BUCKET] == 100
    assert compensation[BUCKET] == 30
