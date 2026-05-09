"""Tests for services/parser.py using pre-saved JSON fixtures.

No live HTTP requests to dwar.ru — all data comes from tests/fixtures/.
"""

from shared.services.parser import parse_character


def test_parse_full_profile(fixture_data):
    data = fixture_data('parse_full_profile')
    html = _build_html_from_fixture(data)

    result = parse_character(html)

    assert result['name'] == 'ТестовыйПерсонаж'
    assert result['stats']['Уровень'] == '42'
    assert result['stats']['Ранг'] == 'Мастер'
    assert result['clan']['Клан'] == 'Тестовый Клан'
    assert result['professions']['Основная'] == 'Воин'
    assert result.get('profile_closed') is not True


def test_parse_closed_profile(fixture_data):
    data = fixture_data('parse_closed_profile')
    html = _build_html_from_fixture(data)

    result = parse_character(html)

    assert result['name'] == 'ЗакрытыйПерсонаж'
    assert len(result['stats']) == 0
    assert len(result['equipment_raw']) == 0


def test_parse_empty_html():
    result = parse_character('<html><body></body></html>')

    assert result['name'] == 'Unknown'
    assert result['stats'] == {}
    assert result['equipment_raw'] == []
    assert result['medals'] == []


def _build_html_from_fixture(data):
    """Build minimal HTML that the parser can extract fixture data from."""
    name = data.get('name', 'Unknown')
    stats_rows = ''.join(
        f'<tr><td>{k}</td><td align="right">{v}</td></tr>'
        for k, v in data.get('stats', {}).items()
    )
    clan_rows = ''.join(
        f'<td>{k}</td><td align="right">{v}</td>'
        for k, v in data.get('clan', {}).items()
        if not k.startswith('_')
    )
    prof_rows = ''.join(
        f'<tr><td>{k}</td><td align="right">{v}</td></tr>'
        for k, v in data.get('professions', {}).items()
    )

    return f'''
    <html>
    <div class="h-txt">{name}</div>
    <table class="coll w100 p10h p2v brd2-all">{stats_rows}</table>
    <tr id="clan_info">
    <table class="coll w100 p10h p2v brd2-all">{clan_rows}</table>
    </tr>
    <tr id="profession_info">
    <table class="coll w100 p10h p2v brd2-all">{prof_rows}</table>
    </tr>
    <script>var temp_effects = [];</script>
    </html>
    '''
