"""A57: подпись поля связана с самим полем.

Было:

```tsx
{label && <label className="input-label">{label}</label>}
<input className={...} {...props} />
```

У `<label>` нет `htmlFor`, у `<input>` нет `id`. Последствия реальные, хотя и не
видны в коде: клик по подписи не фокусирует поле, а скринридер объявляет поле без
имени — то есть форма из восьми полей читается как «поле ввода» восемь раз.

Решение: `id` берётся из пропа, а если его нет — из `useId()`. `htmlFor` ссылается
на тот же id, текст ошибки получает свой id и привязывается через
`aria-describedby` + `aria-invalid`, чтобы ошибка тоже читалась вместе с полем.

Тесты статические: в проекте нет раннера для React-компонентов, а проверяется
здесь именно разметка.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT = os.path.join(ROOT, 'frontend', 'src', 'components', 'ui', 'Input.tsx')


def _source():
    return open(INPUT, encoding='utf-8').read()


def _code_only(text):
    without_block = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(
        line for line in without_block.split('\n')
        if not line.strip().startswith('//') and not line.strip().startswith('*')
    )


def test_every_label_has_html_for():
    labels = re.findall(r'<label[^>]*>', _code_only(_source()))
    assert labels, 'в компоненте больше нет <label>'
    for tag in labels:
        assert 'htmlFor=' in tag, f'подпись без htmlFor: {tag}'


def test_input_gets_an_id():
    tags = re.findall(r'<input[^>]*>', _source(), flags=re.S)
    assert tags, 'в компоненте больше нет <input>'
    assert any('id={inputId}' in tag for tag in tags), 'поле не получает id'


def test_id_comes_from_prop_or_is_generated():
    code = _code_only(_source())
    assert 'useId()' in code, 'id не генерируется'
    assert 'id ?? generatedId' in code, 'переданный снаружи id не учитывается'
    assert re.search(r'function Input\(\{[^}]*\bid\b', code, re.S), (
        'проп id не вынут из props — он попадёт в spread и перезапишет сгенерированный'
    )


def test_error_is_announced_with_the_field():
    code = _code_only(_source())
    assert 'aria-describedby={error ? errorId : undefined}' in code, (
        'текст ошибки не связан с полем'
    )
    assert "aria-invalid={error ? true : undefined}" in code, 'поле не помечается невалидным'
    assert 'id={errorId}' in code, 'у текста ошибки нет id, на который ссылается aria-describedby'


def test_labels_and_fields_use_the_same_variable():
    """Одна переменная на оба конца связи — иначе id разъедется."""
    code = _code_only(_source())
    assert code.count('inputId') >= 3, 'htmlFor и id должны брать одно значение'
    for tag in re.findall(r'<label[^>]*>', code):
        assert 'htmlFor={inputId}' in tag
