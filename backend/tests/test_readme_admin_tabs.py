"""A54: число вкладок админки в README считается из кода, а не по памяти.

История дефекта: README утверждал «5 вкладок» в списке и «4 таба» в дереве
проекта, а в `AdminPage.tsx` их было шесть — шестой стала «API (Swagger)».
Список поправили в A21, а комментарий в дереве остался врать.

Чтобы это не повторилось при добавлении седьмой вкладки, тест не сверяет
«6 == 6», а читает `ALL_TABS` из компонента и требует, чтобы README с ним
совпадал.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
README = os.path.join(ROOT, 'README.md')
ADMIN_PAGE = os.path.join(ROOT, 'frontend', 'src', 'pages', 'admin', 'AdminPage.tsx')


def _tabs():
    source = open(ADMIN_PAGE, encoding='utf-8').read()
    block = source.split('ALL_TABS')[1].split('];')[0]
    return re.findall(r"label: '([^']+)'", block)


def test_component_has_tabs_to_compare():
    tabs = _tabs()
    assert len(tabs) >= 6, f'ожидалось не меньше шести вкладок, найдено {tabs}'


def test_readme_tab_count_matches_the_component():
    tabs = _tabs()
    readme = open(README, encoding='utf-8').read()
    counts = re.findall(r'Админ-панель \((\d+)\s+(?:таб\w*|вклад\w*)\)', readme)
    assert counts, 'README больше не указывает число вкладок админки в дереве'
    for value in counts:
        assert int(value) == len(tabs), (
            f'README говорит {value} вкладок, в AdminPage.tsx их {len(tabs)}'
        )


def test_readme_lists_every_tab():
    tabs = _tabs()
    readme = open(README, encoding='utf-8').read()
    section = readme.split('### Табы')[1].split('## ')[0] if '### Табы' in readme else ''
    assert section, 'в README нет раздела «Табы»'
    missing = [label for label in tabs if label not in section]
    assert not missing, f'в README не описаны вкладки: {missing}'


def test_no_stale_tab_numbers_anywhere():
    readme = open(README, encoding='utf-8').read()
    for number in re.findall(r'(\d+)\s+(?:таб\w*|вклад\w*)', readme):
        assert int(number) == len(_tabs()), f'README утверждает {number} вкладок'
