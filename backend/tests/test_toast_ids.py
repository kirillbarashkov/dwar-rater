"""A42: идентификатор тоста не должен браться из `Date.now()`.

`ToastProvider` присваивал тосту `id = Date.now()`. Два уведомления, поднятых в
одну миллисекунду (а это обычное дело: обработчик показал успех и сразу ошибку
по следующей строке), получали ОДИН id. Дальше таймер первого тоста делал
`filter(t => t.id !== id)` и удалял **оба** — второй исчезал, не успев
показаться. Плюс в React совпадали ключи в списке.

Статическая проверка: у фронтенда нет тестовой инфраструктуры, а гонка лежит в
таймингах — воспроизвести её тестом без `vitest`/jsdom нельзя. Поэтому тест
стережёт именно причину (источник id), а не следствие.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOAST = os.path.join(ROOT, 'frontend', 'src', 'components', 'ui', 'Toast.tsx')


def _source():
    return open(TOAST, encoding='utf-8').read()


def _code_only(source):
    """Без комментариев: в них `Date.now()` упомянут по делу."""
    without_block = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
    return '\n'.join(
        line for line in without_block.split('\n') if not line.strip().startswith('//')
    )


def test_toast_id_is_not_taken_from_the_clock():
    code = _code_only(_source())
    assert 'Date.now()' not in code, (
        'идентификатор тоста снова берётся из Date.now(): два тоста в одну '
        'миллисекунду получат один id, и первый таймер удалит оба'
    )


def test_toast_id_comes_from_a_counter():
    code = _code_only(_source())
    assert re.search(r'let\s+nextToastId\s*=\s*0', code), 'нет модульного счётчика id'
    assert re.search(r'const\s+id\s*=\s*\+\+nextToastId', code), (
        'id тоста не инкрементируется — уникальность не гарантирована'
    )


def test_counter_is_used_in_the_removal_filter():
    """Удаление по id обязано сравнивать с тем же значением, что и добавление."""
    code = _code_only(_source())
    assert 't.id !== id' in code, 'фильтр удаления больше не сверяется с id тоста'


def test_other_date_now_usages_are_not_identifiers():
    """`Date.now()` сам по себе не запрещён — запрещён именно как id.

    Например, в `CharacterPageWrapper` он измеряет возраст кэша — это законно.
    """
    wrapper = os.path.join(ROOT, 'frontend', 'src', 'pages', 'character', 'CharacterPageWrapper.tsx')
    text = _code_only(open(wrapper, encoding='utf-8').read())
    for line in text.split('\n'):
        if 'Date.now()' in line:
            assert 'id' not in line.split('Date.now()')[0].split('=')[0], (
                f'Date.now() похож на источник id: {line.strip()}'
            )
