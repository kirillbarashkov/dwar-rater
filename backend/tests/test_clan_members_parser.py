"""A10: разбор состава клана — один живой путь, покрытый тестами.

В коде было три почти одинаковые функции разбора состава. Две из них мёртвые:
`clan_parser.parse_clan_members` никто не вызывал (и она падала
`re.PatternError: unbalanced parenthesis` на регэкспе ролей), а модуль
`shared/services/clan_import.py` не импортировался нигде. Живая — только
`parse_clan_members_from_management`, и она не была покрыта тестами.

Тест закрепляет поведение живой функции: если правку внесут в «похожую» копию
вместо неё, разбор состава сломается здесь, а не в проде.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.services.clan_parser import parse_clan_members_from_management

CLAN = 4242


def _row(nick, level, rank_title='', role='', cell4='', club=''):
    """Одна строка таблицы состава как на странице управления кланом."""
    rank_img = (
        f'<img src="/images/ranks/1.png" title="{rank_title}" align="absmiddle">'
        if rank_title else ''
    )
    return (
        '<tr class="row">'
        f'<td><a href="#" onclick="userToTag(\'{nick}\')">{nick}</a>'
        f'&nbsp;[{level}] {rank_img}</td>'
        f'<td>{role}</td>'
        '<td></td><td></td>'
        f'<td>{cell4}</td>'
        '</tr>'
    )


def _html(*rows):
    return '<table>' + ''.join(rows) + '</table>'


def test_nick_level_and_rank_are_parsed():
    html = _html(_row('Вася Пупкин', 19, rank_title='Герой'))
    members = parse_clan_members_from_management(html, CLAN)

    assert len(members) == 1, members
    assert members[0]['nick'] == 'Вася Пупкин'
    assert members[0]['level'] == 19
    assert members[0]['game_rank'] == 'Герой'
    assert members[0]['clan_id'] == CLAN


def test_clan_role_is_taken_from_second_cell():
    html = _html(_row('Гном', 20, role='Глава Ордена'))
    members = parse_clan_members_from_management(html, CLAN)
    assert members[0]['clan_role'] == 'Глава Ордена'


def test_join_date_and_trial_are_parsed():
    html = _html(
        _row('Старый', 18, cell4='принят в клан 03.05.2021'),
        _row('Новичок', 5, cell4='Исп. срок до 15.11.2026'),
    )
    members = parse_clan_members_from_management(html, CLAN)

    assert members[0]['join_date'] == '03.05.2021'
    assert members[0]['trial_until'] == ''
    assert members[1]['trial_until'] == '15.11.2026'
    assert members[1]['join_date'] == ''


def test_rows_without_user_to_tag_are_skipped():
    """Заголовок таблицы и служебные строки не должны давать «членов»."""
    html = _html(
        '<tr><th>Ник</th><th>Роль</th></tr>',
        _row('Настоящий', 10),
    )
    members = parse_clan_members_from_management(html, CLAN)
    assert [m['nick'] for m in members] == ['Настоящий']


def test_short_rows_are_skipped():
    html = '<table><tr><td>userToTag(\'Битый\')&nbsp;[5]</td><td>роль</td></tr></table>'
    assert parse_clan_members_from_management(html, CLAN) == []


def test_missing_level_defaults_to_one():
    html = _html(
        '<tr><td><a onclick="userToTag(\'БезУровня\')">x</a></td>'
        '<td>Рыцарь Ордена</td><td></td><td></td><td></td></tr>'
    )
    members = parse_clan_members_from_management(html, CLAN)
    assert members[0]['level'] == 1


def test_broken_duplicate_parser_is_gone():
    """Мёртвая копия падала PatternError — не должна вернуться молча."""
    import shared.services.clan_parser as cp

    assert not hasattr(cp, 'parse_clan_members'), (
        'вернулась мёртвая копия parse_clan_members, которая падает '
        're.PatternError на регэкспе ролей'
    )

    import importlib.util
    spec = importlib.util.find_spec('shared.services.clan_import')
    assert spec is None, 'вернулся неиспользуемый модуль clan_import'
