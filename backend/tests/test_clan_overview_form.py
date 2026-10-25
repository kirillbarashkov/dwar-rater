"""A48: форма структуры клана не должна заполняться эффектом на `info`.

Было:

```tsx
useEffect(() => {
  if (info?.clan_structure) {
    setEditStructure(JSON.parse(JSON.stringify(info.clan_structure)));
    setCouncilSlots(info.clan_structure.council_slots || 4);
  }
}, [info]);
```

а `handleSaveStructure` после сохранения делает `setInfo(refreshed)` — то есть
**сам** меняет `info` и тем самым перезаписывает форму. Итог: несохранённая
правка структуры стирается в момент, когда инфо о клане перезагрузилось —
классический «derived-on-read затирает ввод пользователя».

Решение: серверные данные копируются в форму в обработчике входа в правку
(`startEditingStructure`), а не эффектом. Отмена и сохранение по-прежнему
перезасевают форму сами.

Тесты статические: у фронтенда нет раннера, а проверяемое здесь — структура
кода.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OVERVIEW = os.path.join(
    ROOT, 'frontend', 'src', 'components', 'clan', 'ClanOverview.tsx'
)


def _source():
    return open(OVERVIEW, encoding='utf-8').read()


def _effects(text):
    """Все useEffect-блоки целиком, с массивом зависимостей."""
    blocks = []
    for match in re.finditer(r'useEffect\(\(\) => \{', text):
        start = match.start()
        depth, index = 0, text.index('{', start)
        while index < len(text):
            if text[index] == '{':
                depth += 1
            elif text[index] == '}':
                depth -= 1
                if depth == 0:
                    break
            index += 1
        tail = text[index:index + 80]
        deps = re.search(r'\}, \[([^\]]*)\]', tail)
        blocks.append((text[start:index], deps.group(1) if deps else ''))
    return blocks


def test_no_effect_reseeds_the_structure_form():
    offenders = []
    for body, deps in _effects(_source()):
        if 'setEditStructure' in body or 'setCouncilSlots' in body:
            offenders.append(deps or '<нет зависимостей>')
    assert not offenders, (
        'форма структуры заполняется эффектом — несохранённые правки будут стёрты '
        f'при обновлении info: зависимости {offenders}'
    )


def test_form_is_seeded_on_entering_edit_mode():
    source = _source()
    assert 'const startEditingStructure' in source, 'нет обработчика входа в правку'
    handler = source.split('const startEditingStructure')[1].split('const handleCancelEdit')[0]
    assert 'setEditStructure' in handler, 'обработчик не заполняет форму'
    assert 'setEditingStructure(true)' in handler, 'обработчик не включает режим правки'
    assert 'clan_structure' in handler, 'форма заполняется не серверными данными'


def test_edit_button_calls_the_handler():
    source = _source()
    assert 'onClick={startEditingStructure}' in source, (
        'кнопка «Редактировать» больше не использует общий обработчик'
    )
    assert 'onClick={() => setEditingStructure(true)}' not in source, (
        'остался прямой вход в правку без засева формы'
    )


def test_save_refreshes_info_and_that_is_now_safe():
    """Сохранение обновляет `info` — это законно, пока форма не зависит от эффекта."""
    source = _source()
    save = source.split('const handleSaveStructure')[1].split('const startEditingStructure')[0]
    assert 'setInfo(' in save, 'сохранение больше не обновляет инфо о клане'
    for body, _deps in _effects(source):
        assert 'setEditStructure' not in body, 'эффект снова трогает форму'
