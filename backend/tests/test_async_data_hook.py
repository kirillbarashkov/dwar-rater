"""A35: загрузка данных идёт через общий хук, а не самописным `.catch`.

Было: паттерн «загрузить, при ошибке — пустое значение» переписан в каждом
компоненте по-своему (`.then(setX).catch(() => setX([]))`, свой `isLoading`, свой
повтор при смене ключа). Отличия случайные: где-то ошибка молчала (A20), где-то
оставался старый массив.

Сделано в этом срезе: хук `frontend/src/hooks/useAsyncData.ts` и перевод
`TreasuryImport` (две вкладки, где `dbOperations` грузились вручную). Остальные
потребители — `ClanOverview`, `TreasuryAnalytics` — ещё на своих загрузчиках:
их перевод требует проверки в браузере, которой в этой среде нет. Находка
остаётся частично закрытой, и это записано в реестре.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')
HOOK = os.path.join(SRC, 'hooks', 'useAsyncData.ts')
IMPORT_TAB = os.path.join(SRC, 'components', 'clan', 'TreasuryImport.tsx')


def test_hook_exists_and_handles_the_fallback():
    source = open(HOOK, encoding='utf-8').read()
    assert 'export function useAsyncData' in source
    assert 'setData(fallback)' in source, 'при ошибке не подставляется пустое значение'
    assert 'setError(err)' in source, 'ошибка проглатывается — вызывающий не узнает'
    assert 'silent' in source, 'нет тихого обновления (спиннер размонтирует вкладку)'
    assert 'loaderRef' in source, 'инлайн-стрелка перезапустит эффект на каждый рендер'


def test_hook_clears_the_error_on_success():
    source = open(HOOK, encoding='utf-8').read()
    block = source.split('const next = await loaderRef.current()')[1][:200]
    assert 'setError(null)' in block, 'успешная перезагрузка не снимает прошлую ошибку'


def test_treasury_import_uses_the_hook():
    source = open(IMPORT_TAB, encoding='utf-8').read()
    assert 'useAsyncData' in source, 'TreasuryImport вернулся к самописной загрузке'
    assert 'useAsyncData<TreasuryOperationData[]>' in source
    assert source.count('useAsyncData<TreasuryOperationData[]>') == 2, (
        'обе вкладки импорта должны грузить операции через хук'
    )


def test_no_hand_written_empty_fallback_for_treasury_operations():
    source = open(IMPORT_TAB, encoding='utf-8').read()
    offenders = re.findall(r'getTreasuryOperations\([^)]*\)[^\n]*\.catch\(', source)
    assert not offenders, f'остался ручной catch для операций: {offenders}'
