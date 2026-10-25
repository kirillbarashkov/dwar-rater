"""A45: DTO не должны дублироваться — у типа одно объявление на весь проект.

До правки шесть семейств типов существовали в двух-трёх экземплярах
(`DateCoverage`, `ParsedTreasuryOperation`, `CompareCharacter`, `ClanInfoData`,
`SubCategory`/`EquipCategory`, `SortConfig`/`SortDirection`) — 16 объявлений на
8 имён.

Замер уточнил аудит: копии `DateCoverage`, `ParsedTreasuryOperation`,
`CompareCharacter`, `SubCategory`, `SortConfig` были **идентичны**, расходились
две:

* `DateCoverage` — в `types/` было поле `source_window?`, в `api/` его не было,
  хотя бэкенд это поле возвращает (`routes.py`, date-coverage). Канон взяли из
  `types/` как надмножество;
* `ClanInfoData` — это вообще **две разные сущности**: DTO ответа API
  (`types/clanInfo.ts`) и результат разбора HTML-страницы
  (`utils/parseMembers.ts`, где все поля необязательны и есть `current_players`
  и `clan_structure`). Их нельзя было слить — вторая переименована в
  `ParsedClanInfo`, чтобы имя не вводило в заблуждение.

Тест стережёт именно это: одно объявление на имя и наличие канона там, где его
ожидают.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')

SINGLE = [
    'DateCoverage',
    'ParsedTreasuryOperation',
    'CompareCharacter',
    'ClanInfoData',
    'ParsedClanInfo',
    'SubCategory',
    'EquipCategory',
    'SortConfig',
    'SortDirection',
]


def _sources():
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for name in filenames:
            if name.endswith(('.ts', '.tsx')):
                yield os.path.join(dirpath, name)


def _declarations(type_name):
    # Объявление — только с начала строки: иначе `import { type X }` и
    # `type Alias = X` ловятся как повторное объявление (проверено).
    pattern = re.compile(
        rf"^(export\s+)?(interface|type)\s+{type_name}\b(?!\w)", re.M
    )
    found = []
    for path in _sources():
        text = open(path, encoding='utf-8').read()
        if pattern.search(text):
            found.append(os.path.relpath(path, SRC).replace('\\', '/'))
    return found


def test_each_dto_is_declared_exactly_once():
    duplicates = {name: _declarations(name) for name in SINGLE}
    offenders = {name: where for name, where in duplicates.items() if len(where) != 1}
    assert not offenders, f'тип объявлен не один раз: {offenders}'


def test_canonical_files_hold_the_types():
    expected = {
        'DateCoverage': 'types/clanInfo.ts',
        'ParsedTreasuryOperation': 'types/clanInfo.ts',
        'CompareCharacter': 'types/compare.ts',
        'ClanInfoData': 'types/clanInfo.ts',
        'ParsedClanInfo': 'utils/parseMembers.ts',
        'SubCategory': 'types/character.ts',
        'EquipCategory': 'types/character.ts',
        'SortConfig': 'types/clan.ts',
        'SortDirection': 'types/clan.ts',
    }
    wrong = {}
    for name, path in expected.items():
        if _declarations(name) != [path]:
            wrong[name] = _declarations(name)
    assert not wrong, f'канон не там, где ожидается: {wrong}'


def test_date_coverage_keeps_source_window():
    """Поле есть в ответе бэкенда — оно не должно пропасть при слиянии копий.

    Блок вырезается по балансу скобок: у `DateCoverage` вложенные
    `Record<string, {...}>`, поэтому `split('}')` обрезает объявление на первой
    внутренней скобке (на этом тест и падал).
    """
    text = open(os.path.join(SRC, 'types', 'clanInfo.ts'), encoding='utf-8').read()
    start = text.index('interface DateCoverage')
    depth, index = 0, text.index('{', start)
    while index < len(text):
        if text[index] == '{':
            depth += 1
        elif text[index] == '}':
            depth -= 1
            if depth == 0:
                break
        index += 1
    block = text[start:index + 1]
    assert 'source_window' in block, 'потеряно поле source_window'


def test_api_layer_reexports_instead_of_redeclaring():
    """API-модуль может отдавать тип наружу, но объявлять его заново — нет."""
    api_clan = open(os.path.join(SRC, 'api', 'clanInfo.ts'), encoding='utf-8').read()
    assert "from '../types/clanInfo'" in api_clan, 'api/clanInfo.ts не берёт типы из types/'
    api_compare = open(os.path.join(SRC, 'api', 'compare.ts'), encoding='utf-8').read()
    assert "from '../types/compare'" in api_compare, 'api/compare.ts не берёт тип из types/'
