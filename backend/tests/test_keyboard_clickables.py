"""A58: кликабельные элементы доступны с клавиатуры.

Три дефекта одного класса:

* пять `<div onClick>` в `ClanOverview` (узлы дерева состава клана) — ни `role`,
  ни `tabIndex`, ни клавиш: мышью работает, с клавиатуры недоступно;
* `<td onClick>` в `TreasuryTab` (ник в журнале казны) — то же самое;
* переключатель в `CharacterPanel` — `role="button"` и `tabIndex={0}` **есть**, а
  `onKeyDown` нет: элемент попадает в порядок табуляции, но Enter и Space молчат.

Последний случай самый неприятный: он выглядит доступным (роль, фокус,
`aria-expanded`), поэтому его и не замечают.

Решение: `frontend/src/utils/a11y.ts` → `clickableProps(onActivate)` даёт `role`,
`tabIndex`, `onClick` и `onKeyDown` с Enter/Space. Настоящий `<button>` лучше там,
где разметка позволяет, но `<td>` внутри таблицы и узел дерева — не тот случай.

Тесты статические: раннера для React-компонентов в проекте нет.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')
A11Y = os.path.join(SRC, 'utils', 'a11y.ts')

AFFECTED = [
    os.path.join('components', 'clan', 'ClanOverview.tsx'),
    os.path.join('components', 'clan', 'TreasuryTab.tsx'),
    os.path.join('components', 'snapshots', 'CharacterPanel.tsx'),
]

# Клик «наружу» у модалки — законный паттерн, а не кликабельный элемент:
# у него нет ни роли, ни фокуса, и он не должен их иметь.
OVERLAY_MARKERS = ('modal-overlay', 'stopPropagation')


def _read(rel):
    return open(os.path.join(SRC, rel), encoding='utf-8').read()


def _code_only(text):
    without_block = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(
        line for line in without_block.split('\n') if not line.strip().startswith('//')
    )


def _click_lines(text):
    """Строки файла, где клик висит на не-кнопке.

    Разбор идёт по строкам, а не регуляркой по тегу: в JSX стрелка `=>` ломает
    любой поиск «до ближайшей `>`», и многострочный тег выглядит как кликабельный
    без клавиш (или наоборот).
    """
    code = _code_only(text)
    for number, line in enumerate(code.split('\n'), 1):
        stripped = line.strip()
        if not re.match(r'<(div|td|span|li)\b', stripped):
            continue
        if 'onClick=' not in stripped and not stripped.endswith('onClick={'):
            continue
        yield number, stripped


def test_no_clickable_div_without_keyboard_in_affected_files():
    offenders = []
    for rel in AFFECTED:
        for number, line in _click_lines(_read(rel)):
            if any(marker in line for marker in OVERLAY_MARKERS):
                continue
            if 'clickableProps' in line or 'onKeyDown' in line:
                continue
            # многострочный тег: клавиши могут быть ниже
            source = _read(rel).split('\n')
            window = '\n'.join(source[number - 1:number + 8])
            if 'clickableProps' in window or 'onKeyDown' in window:
                continue
            offenders.append(f'{rel}:{number}: {line[:100]}')
    assert not offenders, 'клик без клавиатуры:\n' + '\n'.join(offenders)


def test_role_button_always_has_keyboard_handler():
    """Класс целиком: `role="button"` без клавиш — элемент-обманка."""
    offenders = []
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for name in filenames:
            if not name.endswith('.tsx'):
                continue
            path = os.path.join(dirpath, name)
            code = _code_only(open(path, encoding='utf-8').read())
            for match in re.finditer(r'role="button"', code):
                # Клавиши могут стоять и до `role="button"` (календарь казны).
                # Хвост обрезаем по закрытию самого элемента, начало — нет:
                # иначе в окно попадут обработчики соседних элементов.
                before = code[max(0, match.start() - 900):match.start()]
                after = code[match.start():match.start() + 900].split('</', 1)[0]
                window = before + after
                if 'onKeyDown' in window or 'clickableProps' in window:
                    continue
                line = code[:match.start()].count('\n') + 1
                offenders.append(f'{os.path.relpath(path, SRC)}:{line}')
    assert not offenders, 'role="button" без onKeyDown/clickableProps:\n' + '\n'.join(offenders)


def test_character_panel_toggle_is_keyboard_ready():
    source = _code_only(_read(os.path.join('components', 'snapshots', 'CharacterPanel.tsx')))
    index = source.index('cph-toggle')
    window = source[index:index + 400]
    assert 'clickableProps' in window, 'переключатель снова без клавиш'
    assert 'aria-expanded' in window, 'потерян aria-expanded'
