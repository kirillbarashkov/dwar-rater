"""A17: чтение JSON-полей клана не должно глушить всё подряд и молчать.

`get_council` / `get_clan_structure` раньше стояли с голым `except:`, который
ловил и `KeyboardInterrupt`/`SystemExit`, и любое повреждение данных — при этом
возвращался пустой список/словарь. Битое поле выглядело как «совета нет», и
именно на этом фоне A3 (не-JSON в `Text`) жил незамеченным.

Теперь ловятся только ожидаемые ошибки разбора, и они попадают в лог.
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models.clan_info import ClanInfo


def _clan(**kwargs):
    clan = ClanInfo(clan_id=4242, name='TestClan')
    for k, v in kwargs.items():
        setattr(clan, k, v)
    return clan


def test_valid_council_is_parsed():
    clan = _clan(council=json.dumps([{'nick': 'Гном'}], ensure_ascii=False))
    assert clan.get_council() == [{'nick': 'Гном'}]


def test_broken_council_returns_empty_list_and_logs(caplog):
    clan = _clan(council="{'nick': 'Гном'}")   # python-repr, не JSON (класс A3)

    with caplog.at_level(logging.WARNING):
        assert clan.get_council() == []

    assert any('get_council' in r.message for r in caplog.records), (
        'повреждённое поле прочитано молча — в логе ничего нет'
    )


def test_none_council_does_not_explode(caplog):
    clan = _clan(council=None)
    with caplog.at_level(logging.WARNING):
        assert clan.get_council() == []
    assert caplog.records, 'None в поле прочитан молча'


def test_valid_structure_is_parsed():
    clan = _clan(clan_structure=json.dumps({'leader': 'Гном'}, ensure_ascii=False))
    assert clan.get_clan_structure() == {'leader': 'Гном'}


def test_broken_structure_returns_empty_dict_and_logs(caplog):
    clan = _clan(clan_structure='not json at all')
    with caplog.at_level(logging.WARNING):
        assert clan.get_clan_structure() == {}
    assert any('get_clan_structure' in r.message for r in caplog.records)


def test_keyboard_interrupt_is_not_swallowed():
    """Главное отличие от голого `except:` — прерывания не превращаются в [].

    Ловим KeyboardInterrupt внутри теста: если модель проглотит его (как делал
    голый `except:`), pytest.raises не сработает и тест упадёт.
    """
    import pytest
    import shared.models.clan_info as clan_info_module

    clan = _clan(council=json.dumps([]))
    original = clan_info_module.json.loads

    def raiser(_value):
        raise KeyboardInterrupt

    clan_info_module.json.loads = raiser
    try:
        with pytest.raises(KeyboardInterrupt):
            clan.get_council()
    finally:
        clan_info_module.json.loads = original


def test_no_bare_except_left_in_model():
    """Страж: голый `except:` не должен вернуться в модель."""
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, 'shared', 'models', 'clan_info.py')
    lines = open(path, encoding='utf-8').read().split('\n')
    offenders = [n + 1 for n, l in enumerate(lines) if re.match(r'\s*except\s*:\s*$', l)]
    assert not offenders, f'голый except: в строках {offenders}'
