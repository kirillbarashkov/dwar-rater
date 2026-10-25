"""A44: `<Button>` без `type` был кнопкой отправки формы.

HTML-дефолт для `<button>` внутри `<form>` — `type="submit"`. Общий компонент
`Button` не задавал `type` вообще, то есть 77 из 81 использования полагались на
этот дефолт: любая кнопка, добавленная в форму, начала бы её отправлять.

Перед правкой проверено (и это важно, потому что от этого зависит
безопасность изменения): все 7 форм в приложении используют **нативные**
`<button type="submit">`, а единственный `<Button>` внутри формы
(`ProfilePage`) уже задаёт `type` явно — `submit` для сохранения и `button` для
отвязки персонажа. Значит смена дефолта ничего не ломает.

Тесты статические: они проверяют и сам дефолт, и то, что кнопки внутри форм
объявляют тип явно.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')
BUTTON = os.path.join(SRC, 'components', 'ui', 'Button.tsx')


def test_default_type_is_button():
    source = open(BUTTON, encoding='utf-8').read()
    assert re.search(r"type\s*=\s*'button'", source), 'у Button нет дефолта type="button"'
    assert 'type={type}' in source, 'дефолт не пробрасывается в <button>'


def test_button_still_accepts_an_explicit_type():
    source = open(BUTTON, encoding='utf-8').read()
    assert 'type =' in source.split('{')[-1] or "type = 'button'" in source
    assert 'ButtonHTMLAttributes' in source, 'проп `type` должен остаться в интерфейсе'


def _form_blocks():
    """Куски текста между <form ...> и </form> для всех компонентов."""
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for name in filenames:
            if not name.endswith('.tsx'):
                continue
            path = os.path.join(dirpath, name)
            text = open(path, encoding='utf-8').read()
            for match in re.finditer(r'<form\b.*?</form>', text, re.S):
                yield os.path.relpath(path, SRC), match.group(0)


def test_buttons_inside_forms_declare_their_type():
    offenders = []
    for rel, block in _form_blocks():
        for tag in re.findall(r'<Button\b[^>]*>', block):
            if 'type=' not in tag:
                offenders.append(f'{rel}: {tag[:80]}')
    assert not offenders, (
        'кнопка внутри формы без явного type — после A44 это `button`, то есть форма '
        'не отправится, если именно это задумано:\n' + '\n'.join(offenders)
    )


def test_forms_have_a_submit_control():
    """Форма без единой кнопки submit просто не работает — это тоже нужно ловить."""
    broken = []
    for rel, block in _form_blocks():
        has_submit = (
            re.search(r'<button[^>]*type="submit"', block)
            or re.search(r'<Button[^>]*type="submit"', block)
            or re.search(r'<input[^>]*type="submit"', block)
        )
        if not has_submit:
            broken.append(rel)
    assert not broken, f'у формы нет кнопки отправки: {broken}'
