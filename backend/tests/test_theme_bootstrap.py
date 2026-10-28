"""TD-11: тема применяется на входе приложения, а не в `Header`.

Дефект: `data-theme` на `<html>` выставлял только `Header`. Самостоятельные
страницы (`/admin`, до фикса — `/about`) его не рендерят, поэтому при сохранённой
светлой теме `/admin` отдавал `data-theme=null` и тёмный фон `rgb(10,14,20)`.
На `/about` лечение оказалось копией той же логики в самой странице — то есть
третья копия `getInitialTheme` (Header, AboutPage, и обе читали `localStorage`
и `matchMedia` по-своему).

Правило, которое закрепляет тест: источник темы один — `utils/theme.ts`,
применение одно — вызов `initTheme()` в `main.tsx` до первого рендера.
Страница или компонент не должны ни читать `localStorage.theme`, ни писать
`data-theme`: иначе очередная «новая страница» снова окажется тёмной.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')
THEME = os.path.join(SRC, 'utils', 'theme.ts')
MAIN = os.path.join(SRC, 'main.tsx')

ATTRIBUTE = "setAttribute('data-theme'"
STORAGE = re.compile(r'localStorage\.(?:get|set)Item\(\s*(?:\'theme\'|STORAGE_KEY)')
MEDIA_QUERY = "prefers-color-scheme: light"


def _read(path):
    return open(path, encoding='utf-8').read()


def _code_only(text):
    without_block = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(
        line for line in without_block.split('\n')
        if not line.strip().startswith('//')
    )


def _sources():
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for name in filenames:
            if name.endswith('.ts') or name.endswith('.tsx'):
                yield os.path.join(dirpath, name)


def test_theme_module_is_the_single_source():
    source = _code_only(_read(THEME))
    assert 'export function initTheme' in source, 'нет точки входа initTheme()'
    assert 'export function applyTheme' in source, 'нет applyTheme()'
    assert 'export function preferredTheme' in source, 'нет preferredTheme()'
    assert ATTRIBUTE in source, f'тема в utils/theme.ts не содержит {ATTRIBUTE}'
    assert STORAGE.search(source), 'utils/theme.ts не хранит выбор пользователя'
    assert MEDIA_QUERY in source, 'нет системной настройки по умолчанию'


def test_theme_applied_before_first_render():
    source = _code_only(_read(MAIN))
    assert 'initTheme' in source, 'main.tsx не применяет тему'
    init_at = source.index('initTheme(')
    render_at = source.index('createRoot(')
    assert init_at < render_at, (
        'initTheme() вызывается после createRoot(): первый кадр отрисуется '
        'в теме по умолчанию и мигнёт'
    )


def test_no_page_or_component_writes_the_attribute():
    offenders = []
    for path in _sources():
        if os.path.abspath(path) == os.path.abspath(THEME):
            continue
        if ATTRIBUTE in _code_only(_read(path)):
            offenders.append(os.path.relpath(path, SRC))
    assert not offenders, (
        'data-theme выставляется в обход utils/theme.ts: ' + ', '.join(offenders)
        + ' — страница без Header снова останется в теме по умолчанию'
    )


def test_no_page_or_component_reads_storage_or_media_query():
    offenders = []
    for path in _sources():
        if os.path.abspath(path) == os.path.abspath(THEME):
            continue
        source = _code_only(_read(path))
        found = []
        if STORAGE.search(source):
            found.append('localStorage(theme)')
        if MEDIA_QUERY in source:
            found.append(MEDIA_QUERY)
        if found:
            offenders.append(f'{os.path.relpath(path, SRC)}: {", ".join(found)}')
    assert not offenders, (
        'логика выбора темы продублирована:\n' + '\n'.join(offenders)
    )
