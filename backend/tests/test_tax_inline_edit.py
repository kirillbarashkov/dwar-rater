"""A49: инлайн-правка в аналитике налогов правит ту операцию и тем числом.

Два дефекта в одном месте:

1. **Не то число.** `startInlineEdit` засевал поле количеством из
   `player.totalPaid` — производной суммой (`onTime + delayed`, без компенсации).
   Сохранение писало это значение **обратно в операцию**, то есть в записи
   оказывалось другое число, чем в ней лежало. Для компенсированной строки
   расхождение гарантированное.
2. **Ключ по нику.** `editingRow` хранил ник, поэтому два участника с никами,
   отличающимися только регистром, получали один ключ: правка открывалась у
   обоих, а сохранение могло уйти не в ту строку.

Решение: количество берётся из самой операции (`operations.find(o => o.id ===
targetId)?.quantity`), ключ правки — id операции (у компенсации — зачёт, иначе
платёж).

Тесты статические: фронтенд-раннера в проекте нет.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TAX = os.path.join(ROOT, 'frontend', 'src', 'components', 'clan', 'TaxAnalytics.tsx')


def _source():
    return open(TAX, encoding='utf-8').read()


def _code_only(text):
    without_block = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(
        line for line in without_block.split('\n') if not line.strip().startswith('//')
    )


def test_quantity_is_seeded_from_the_operation():
    code = _code_only(_source())
    start = code.index('const startInlineEdit')
    body = code[start:start + 900]
    assert 'operations.find' in body, 'количество берётся не из операции'
    assert re.search(r'operation\?\.quantity', body), 'не используется quantity самой операции'
    assert 'quantity: player.totalPaid' not in body, (
        'количество снова засевается производной суммой totalPaid'
    )


def test_edit_key_is_the_operation_not_the_nick():
    code = _code_only(_source())
    assert 'editingRowId' in code, 'ключ правки не по id операции'
    assert 'editingRow' not in code.replace('editingRowId', ''), (
        'остался ключ по нику — регистр ников схлопнет строки'
    )


def test_rows_compare_by_operation_id():
    code = _code_only(_source())
    assert 'editingRowId === targetOperationId(p)' in code, 'строка не сравнивается по id'
    assert 'p.nick === editingRow' not in code and 'editingRow === p.nick' not in code, (
        'сравнение по нику вернулось'
    )


def test_single_resolver_for_the_target_operation():
    """Компенсация правится через зачёт, обычный платёж — через операцию месяца."""
    code = _code_only(_source())
    assert 'const targetOperationId' in code, 'нет общего резолвера целевой операции'
    resolver = code.split('const targetOperationId')[1].split('const startInlineEdit')[0]
    assert 'compensated' in resolver and 'operationId' in resolver and 'paymentOpId' in resolver, (
        'резолвер не различает компенсацию и обычную оплату'
    )
    assert code.count('targetOperationId(player)') >= 2, (
        'резолвер используется не везде: правка и сохранение должны брать один id'
    )
