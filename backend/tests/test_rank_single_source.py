"""A43: список рангов игры должен существовать в одном экземпляре.

До правки в проекте жили **три** копии: массив из 15 значений в
`ClanMembersTable` (выпадающий список «Добавить участника») и две одинаковые
карты «уровень → ранг» из 20 значений (`ClosedProfilesTab`,
`ClosedProfileBanner`).

Последствие было функциональным, а не косметическим: форма добавления не
предлагала ранги «Рекрут», «Солдат», «Боец», «Воин» и «Победоносец» — участника
с таким рангом нельзя было завести, хотя в остальном приложении он
отображался.

Тесты статические: у фронтенда нет своего раннера, а проверяемое здесь —
структура кода и содержимое единственного источника.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'frontend', 'src')
RANKS = os.path.join(SRC, 'utils', 'ranks.ts')

EXPECTED = [
    'Рекрут', 'Солдат', 'Боец', 'Воин', 'Элитный воин', 'Чемпион', 'Гладиатор',
    'Полководец', 'Мастер войны', 'Герой', 'Военный эксперт', 'Магистр войны',
    'Вершитель', 'Высший магистр', 'Повелитель', 'Легендарный завоеватель',
    'Властелин боя', 'Победоносец', 'Триумфатор', 'Избранник богов',
]


def _sources():
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for name in filenames:
            if name.endswith(('.ts', '.tsx')):
                yield os.path.join(dirpath, name)


def test_ranks_are_defined_in_exactly_one_file():
    definitions = []
    for path in _sources():
        text = open(path, encoding='utf-8').read()
        if re.search(r"(const|let)\s+GAME_RANKS(_BY_LEVEL)?\b[^=]*=\s*[\[{]", text):
            definitions.append(os.path.relpath(path, SRC))
    assert definitions == [os.path.join('utils', 'ranks.ts')], (
        f'список рангов определён не в одном месте: {definitions}'
    )


def test_source_contains_all_twenty_ranks():
    text = open(RANKS, encoding='utf-8').read()
    for rank in EXPECTED:
        assert f"'{rank}'" in text, f'в едином источнике нет ранга {rank!r}'


def test_ranks_are_keyed_by_level_one_to_twenty():
    text = open(RANKS, encoding='utf-8').read()
    levels = sorted(int(n) for n in re.findall(r'^\s*(\d+):', text, re.M))
    assert levels == list(range(1, 21)), f'уровни не 1..20: {levels}'


def test_dropdown_list_is_derived_from_the_map():
    """Массив для выпадающих списков выводится, а не дублируется руками."""
    text = open(RANKS, encoding='utf-8').read()
    assert 'export const GAME_RANKS:' in text, 'нет массива для выпадающих списков'
    # Режем по объявлению массива (с двоеточием): иначе маркер совпадёт с
    # `GAME_RANKS_BY_LEVEL` и проверка увидит не тот участок файла.
    array_body = text.split('export const GAME_RANKS:')[1]
    assert 'GAME_RANKS_BY_LEVEL' in array_body, (
        'массив не выводится из карты — копии снова разойдутся'
    )


def test_clan_members_form_offers_previously_missing_ranks():
    """Список в форме добавления — общий, значит содержит и «Рекрут», и «Воин»."""
    table = open(os.path.join(SRC, 'components', 'clan', 'ClanMembersTable.tsx'),
                 encoding='utf-8').read()
    assert "from '../../utils/ranks'" in table, 'форма не использует общий список'
    assert "const GAME_RANKS = [" not in table, 'в форме снова локальная копия'


def test_both_profiles_components_use_the_shared_map():
    for rel in (
        os.path.join('components', 'analysis', 'ClosedProfilesTab.tsx'),
        os.path.join('components', 'snapshots', 'ClosedProfileBanner.tsx'),
    ):
        text = open(os.path.join(SRC, rel), encoding='utf-8').read()
        assert "from '../../utils/ranks'" in text, f'{rel}: не использует общий источник'
        assert "Record<number, string> = {" not in text, f'{rel}: осталась локальная карта'
