import re
import json
from urllib.parse import urlparse
import requests
from backend.utils.formatters import clean_html


EQUIPMENT_KINDS = {
    'Шлем', 'Кираса', 'Кольчуга', 'Обувь', 'Наручи', 'Поножи',
    'Наплечники', 'Основное', 'Двуручное', 'Лук', 'Легкий щит',
    'Кольца', 'Амулет'
}


def fetch_character_page(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }
    session = requests.Session()
    resp = session.get(url, headers=headers, timeout=15)
    resp.encoding = 'utf-8'
    html = resp.text

    if 'art_alt' in html and 'h-txt' in html:
        return html, session

    if 'Перейти к игровой информации' in html or 'noredir=' in html:
        redirect_match = re.search(r"location\.href='([^']+)'", html)
        if redirect_match:
            redirect_url = redirect_match.group(1)
            if 'rating_info' in redirect_url:
                return html, session
            if not redirect_url.startswith('http'):
                parsed = urlparse(url)
                if not redirect_url.startswith('/'):
                    redirect_url = '/' + redirect_url
                redirect_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
            resp2 = session.get(redirect_url, headers=headers, timeout=15)
            resp2.encoding = 'utf-8'
            return resp2.text, session

    return html, session


def check_profile_closed(session, nick, html):
    try:
        ep_url = 'https://w1.dwar.ru/entry_point.php'
        data = {
            'object': 'user',
            'action': 'user_info',
            'nick': nick,
            'json_mode_on': '1'
        }
        resp = session.post(ep_url, data=data, timeout=10)
        resp.encoding = 'utf-8'
        result = json.loads(resp.text)
        user_info = result.get('user|user_info', {})
        return {
            'closed': user_info.get('closed', False) or user_info.get('user_close_info', False),
            'level': user_info.get('level', ''),
            'rank': user_info.get('rank', ''),
            'picture': user_info.get('picture', ''),
            'description': user_info.get('description', ''),
            'premium_level': user_info.get('premium_level', ''),
        }
    except Exception:
        return None


def parse_character(html, session=None, nick=None):
    result = {}

    name_match = re.search(r'<div class="h-txt">\s*(.*?)\s*</div>', html)
    result['name'] = name_match.group(1).strip() if name_match else 'Unknown'

    all_stats = {}
    stats_tables = re.findall(
        r'<table class="coll w100 p10h p2v brd2-all" border="0">\s*<tbody>(.*?)</tbody>\s*</table>',
        html, re.DOTALL
    )

    for table_html in stats_tables:
        rows = re.findall(
            r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*align="right"[^>]*>(.*?)</td>\s*</tr>',
            table_html, re.DOTALL
        )
        for label, value in rows:
            label = clean_html(label)
            value = clean_html(value)
            if label and value:
                all_stats[label] = value

    result['stats'] = all_stats

    clan_section = re.search(r'id="clan_info".*?<table[^>]*>(.*?)</table>', html, re.DOTALL)
    if clan_section:
        clan_rows = re.findall(
            r'<td[^>]*>(.*?)</td>\s*<td[^>]*align="right"[^>]*>(.*?)</td>',
            clan_section.group(1), re.DOTALL
        )
        clan_info = {}
        for label, value in clan_rows:
            clan_info[clean_html(label)] = clean_html(value)
        result['clan'] = clan_info

    prof_section = re.search(r'id="profession_info".*?<table[^>]*>(.*?)</table>', html, re.DOTALL)
    if prof_section:
        prof_rows = re.findall(
            r'<td[^>]*>(.*?)</td>\s*<td[^>]*align="right"[^>]*>(.*?)</td>',
            prof_section.group(1), re.DOTALL
        )
        professions = {}
        for label, value in prof_rows:
            professions[clean_html(label)] = clean_html(value)
        result['professions'] = professions

    pattern = r'art_alt\["AA_(\d+)"\]\s*=\s*(\{.+?\});</script>'
    matches = re.findall(pattern, html, re.DOTALL)

    equipment = []
    medals = []
    permanent_effects = []

    for artifact_id, json_str in matches:
        try:
            data = json.loads(json_str)
            data['artifact_id'] = artifact_id
            kind = data.get('kind', '')
            if kind in EQUIPMENT_KINDS:
                equipment.append(data)
            elif kind == 'Орден':
                medals.append(data)
            elif kind == 'Эффекты':
                permanent_effects.append(data)
        except json.JSONDecodeError:
            continue

    result['equipment'] = equipment
    result['medals'] = medals
    result['permanent_effects'] = permanent_effects

    temp_effects_match = re.search(r'var temp_effects\s*=\s*(\[.*?\]);', html, re.DOTALL)
    if temp_effects_match:
        try:
            temp_effects = json.loads(temp_effects_match.group(1))
            result['temp_effects'] = temp_effects
        except Exception:
            result['temp_effects'] = []

    manor_match = re.search(r'<b>находится:</b>\s*<b class="redd">(.*?)</b>', html)
    if manor_match:
        result['manor_location'] = manor_match.group(1).strip()

    manor_buildings = re.findall(r'<img src="images/data/buildings/([^"]+)"', html)
    result['manor_buildings'] = manor_buildings

    has_stats = len(stats_tables) > 0
    has_equipment = len(equipment) > 0

    if not has_stats and not has_equipment and session and nick:
        closed_info = check_profile_closed(session, nick, html)
        if closed_info and closed_info['closed']:
            result['profile_closed'] = True
            result['closed_info'] = closed_info

    return result
