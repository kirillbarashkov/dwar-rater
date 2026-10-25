"""A51: таймеры интерфейса отменяются при размонтировании.

Было: `setTimeout(() => setCopyStatus(null), 2000)` без сохранения id — cleanup
его не отменит. Таймер живёт после ухода со страницы, а `setState` приходит в
размонтированный компонент (в React 19 это тихий no-op, но логика «статус
скопировано» обновляет то, чего уже нет).

Решение: хук `useSafeTimeout()` — возвращает `schedule(fn, ms)`, отменяет
предыдущий таймер и отменяет последний при размонтировании. Переведены семь
мест в пяти файлах.

Отдельно: `MemberStatusTab` — это **правильный** debounce (`setTimeout` внутри
эффекта с `clearTimeout` в cleanup), его трогать не нужно, и тест это фиксирует.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')
HOOK = os.path.join(SRC, 'hooks', 'useSafeTimeout.ts')

FILES_WITH_FLASH = [
    os.path.join('components', 'clan', 'MiscAnalytics.tsx'),
    os.path.join('components', 'clan', 'TalentAnalytics.tsx'),
    os.path.join('components', 'clan', 'TaxAnalytics.tsx'),
    os.path.join('components', 'clan', 'TaxLedger.tsx'),
    os.path.join('components', 'clan', 'TreasurySummaryPanel.tsx'),
]


def _read(rel):
    return open(os.path.join(SRC, rel), encoding='utf-8').read()


def _code_only(text):
    without_block = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(
        line for line in without_block.split('\n') if not line.strip().startswith('//')
    )


def test_hook_clears_the_timer_on_unmount():
    source = _code_only(open(HOOK, encoding='utf-8').read())
    assert 'clearTimeout' in source, 'хук не очищает таймер'
    assert 'useEffect' in source, 'нет cleanup-эффекта'
    assert 'return useCallback' in source, 'хук не возвращает функцию планирования'


def test_flash_timers_are_scheduled_through_the_hook():
    offenders = []
    for rel in FILES_WITH_FLASH:
        code = _code_only(_read(rel))
        for number, line in enumerate(code.split('\n'), 1):
            if re.search(r'(window\.)?setTimeout\(\(\) => set(CopyStatus|Copied)', line):
                offenders.append(f'{rel}:{number}')
    assert not offenders, (
        'таймер сброса статуса взводится напрямую, без очистки:\n' + '\n'.join(offenders)
    )


def test_flash_files_use_the_hook():
    missing = [rel for rel in FILES_WITH_FLASH if 'useSafeTimeout' not in _read(rel)]
    assert not missing, f'файлы не используют общий хук: {missing}'


def test_debounce_with_cleanup_is_left_alone():
    """`MemberStatusTab` — правильный debounce: setTimeout внутри эффекта + cleanup."""
    source = _read(os.path.join('components', 'clan', 'MemberStatusTab.tsx'))
    assert 'const timer = setTimeout(' in source, 'debounce пропал'
    assert 'clearTimeout(timer)' in source, 'cleanup debounce пропал'


# Таймеры, которые классу A51 не принадлежат — с причиной, а не «чтобы тест
# был зелёным»:
ALLOWED = {
    # `await new Promise(resolve => setTimeout(resolve, N))` — ожидание внутри
    # асинхронного обработчика, а не фоновый сброс состояния. Отменять нечего:
    # промис нужен именно затем, чтобы дождаться паузы.
    os.path.join('components', 'analysis', 'ClosedProfilesTab.tsx'),
    # Тост живёт в провайдере, который смонтирован на всё время работы
    # приложения; таймер удаляет тост из списка. Это отдельная задача (очистка
    # таймеров провайдера уведомлений), в A51 не входит.
    os.path.join('components', 'ui', 'Toast.tsx'),
}


def test_no_timer_without_cleanup_in_clan_tabs():
    """Общий страж: фоновый таймер обязан идти через хук или иметь cleanup."""
    offenders = []
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for name in filenames:
            if not name.endswith('.tsx'):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, SRC)
            if rel in ALLOWED:
                continue
            code = _code_only(open(path, encoding='utf-8').read())
            if 'useSafeTimeout' in code or 'clearTimeout' in code:
                continue
            for number, line in enumerate(code.split('\n'), 1):
                if re.search(r'(?<![\w.])(window\.)?setTimeout\(', line):
                    offenders.append(f'{rel}:{number}')
    assert not offenders, 'таймер без очистки:\n' + '\n'.join(offenders)


def test_allowed_list_is_justified_and_stable():
    """Каждое исключение должно существовать и содержать таймер."""
    for rel in ALLOWED:
        source = _read(rel)
        assert 'setTimeout(' in source, f'исключение {rel} больше не содержит таймер — уберите его'
