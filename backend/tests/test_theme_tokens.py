"""A59: цвета в коде берутся из токенов темы, а не из литералов.

Реальный дефект был узкий, но показательный: в одном и том же объекте

```tsx
const priorityColors = {
  high: '#dc3545',      // литерал
  medium: 'var(--gold)', // токен
  low: 'var(--text-muted)',
};
```

`high` не менялся вместе с темой: в `tokens.css` определена светлая тема
(строки ~95), где `--red: #ef4444`, а приоритет «высокий» оставался тёмно-красным
из Bootstrap. Теперь `var(--red)`.

Второй дефект — каст кастомного свойства:
`style={{ '--prof-color': … } as React.CSSProperties}`. Приведение глушило
проверку имён, и опечатка в `--prof-colour` просто не применилась бы. Заменено на
`cssVars()` (`frontend/src/utils/cssVars.ts`), ключ типизирован как `--${string}`.

Остальные цветовые литералы в `.tsx` — это **данные**, а не оформление: цвета
качества предмета в `EquipmentTab`, палитра профессий в `ClanMembersTable`,
градиенты HP/маны. Их нельзя перевести в токены, не потеряв смысл, поэтому тест
фиксирует их число как baseline: вырасти оно не должно.

Инлайн-стили с вычисляемыми размерами (`width: ${p}%`, `transform`) дефектом не
являются — это значения, известные только в рантайме.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')
TRACK = os.path.join(SRC, 'components', 'analysis', 'ImprovementTrack.tsx')
CSS_VARS = os.path.join(SRC, 'utils', 'cssVars.ts')

# Палитры-данные: цвет здесь — смысл (качество предмета, профессия), не тема.
BASELINE_COLOR_LITERALS = 15

HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')


def _tsx_files():
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for name in filenames:
            if name.endswith('.tsx'):
                yield os.path.join(dirpath, name)


def test_priority_colors_come_from_tokens():
    source = open(TRACK, encoding='utf-8').read()
    block = source.split('priorityColors')[1].split('};')[0]
    literals = HEX.findall(block)
    assert not literals, f'приоритет шага снова с литералом: {literals}'
    for token in ("'var(--red)'", "'var(--gold)'", "'var(--text-muted)'"):
        assert token in block, f'потерян токен {token}'


def test_no_css_property_casts_outside_the_helper():
    offenders = []
    for path in _tsx_files():
        source = open(path, encoding='utf-8').read()
        if 'as React.CSSProperties' in source or 'as CSSProperties' in source:
            offenders.append(os.path.relpath(path, SRC))
    assert not offenders, (
        'каст кастомного свойства в обход cssVars(): ' + ', '.join(offenders)
    )


def test_helper_restricts_keys_to_custom_properties():
    source = open(CSS_VARS, encoding='utf-8').read()
    assert 'Record<`--${string}`' in source, 'ключ не ограничен кастомными свойствами'
    assert 'CSSProperties' in source


def test_color_literals_do_not_grow():
    total = 0
    per_file = {}
    for path in _tsx_files():
        found = HEX.findall(open(path, encoding='utf-8').read())
        if found:
            per_file[os.path.relpath(path, SRC)] = len(found)
            total += len(found)
    assert total <= BASELINE_COLOR_LITERALS, (
        f'цветовых литералов стало {total} (baseline {BASELINE_COLOR_LITERALS}) — '
        'новый цвет оформления должен быть токеном в tokens.css\n'
        + '\n'.join(f'{name}: {count}' for name, count in sorted(per_file.items()))
    )
