import re
import json
from urllib.parse import urlparse, parse_qs, unquote
import requests
from utils.formatters import clean_html


EQUIPMENT_KINDS = {
    'Шлем', 'Кираса', 'Кольчуга', 'Обувь', 'Наручи', 'Поножи',
    'Наплечники', 'Основное', 'Двуручное', 'Лук', 'Легкий щит',
    'Кольца', 'Амулет', 'Левая рука', 'Правая рука', 'Оправа',
    'Лак', 'Усиление', 'Магический символ', 'Символ', 'Аркат',
    'Знамя', 'Легендарный', 'Вещи стиля', 'Медальон', 'Браслет',
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


def parse_flashvars(html):
    flashvars_data = {}

    flashvars_match = re.search(r"flashvars\s*=\s*'([^']+)'", html)
    if flashvars_match:
        params = parse_qs(flashvars_match.group(1))
        for key, values in params.items():
            flashvars_data[key] = values[0] if len(values) == 1 else values

    par_match = re.search(r"var par\s*=\s*'([^']+)'", html)
    if par_match:
        params = parse_qs(par_match.group(1))
        for key, values in params.items():
            flashvars_data[key] = values[0] if len(values) == 1 else values

    return flashvars_data


def parse_stats_tables(html):
    all_stats = {}

    stats_tables = re.findall(
        r'<table class="coll w100 p10h p2v brd2-all"[^>]*>(.*?)</table>',
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

    return all_stats


def parse_clan_info(html):
    clan_match = re.search(
        r'<tr id="clan_info">.*?<table class="coll w100 p10h p2v brd2-all"[^>]*>(.*?)</table>',
        html, re.DOTALL
    )
    if not clan_match:
        return {}

    clan_rows = re.findall(
        r'<td[^>]*>(.*?)</td>\s*<td[^>]*align="right"[^>]*>(.*?)</td>',
        clan_match.group(1), re.DOTALL
    )
    clan_info = {}
    for label, value in clan_rows:
        label = clean_html(label)
        value = clean_html(value)
        if label and value:
            clan_info[label] = value

    clan_id_match = re.search(r'showClanInfo\((\d+)\)', html)
    if clan_id_match:
        clan_info['_clan_id'] = clan_id_match.group(1)

    return clan_info


def parse_profession_info(html):
    prof_match = re.search(
        r'<tr id="profession_info">.*?<table class="coll w100 p10h p2v brd2-all"[^>]*>(.*?)</table>',
        html, re.DOTALL
    )
    if not prof_match:
        return {}

    prof_rows = re.findall(
        r'<td[^>]*>(.*?)</td>\s*<td[^>]*align="right"[^>]*>(.*?)</td>',
        prof_match.group(1), re.DOTALL
    )
    professions = {}
    for label, value in prof_rows:
        label = clean_html(label)
        value = clean_html(value)
        if label and value:
            professions[label] = value
    return professions


def parse_personal_info(html):
    personal_match = re.search(
        r'<tr id="personal_info">.*?<table class="coll w100 p10h p2v brd2-all"[^>]*>(.*?)</table>',
        html, re.DOTALL
    )
    if not personal_match:
        return {}

    rows = re.findall(
        r'<td[^>]*>(.*?)</td>\s*<td[^>]*class=".*?redd.*?"[^>]*>(.*?)</td>',
        personal_match.group(1), re.DOTALL
    )
    personal_info = {}
    for label, value in rows:
        label = clean_html(label).replace(':', '').strip()
        value = clean_html(value)
        if label and value:
            personal_info[label] = value
    return personal_info


def parse_art_alt_data(html):
    artifacts = {}

    pattern = r'art_alt\["AA_(\d+)"\]\s*=\s*(\{.+?\});</script>'
    matches = re.findall(pattern, html, re.DOTALL)

    for artifact_id, json_str in matches:
        try:
            data = json.loads(json_str)
            data['artifact_id'] = artifact_id
            artifacts[f'AA_{artifact_id}'] = data
        except json.JSONDecodeError:
            continue

    return artifacts


def parse_equipment_from_flashvars(flashvars_data, artifacts):
    equipment = []

    arts_raw = flashvars_data.get('arts', '')
    if not arts_raw:
        return equipment

    items = arts_raw.split(',')
    for item_str in items:
        parts = item_str.split(':')
        if len(parts) < 8:
            continue

        artifact_id = parts[0]
        filename = parts[1]

        artifact_key = f'AA_{artifact_id}'
        artifact_data = artifacts.get(artifact_key, {})

        kind = artifact_data.get('kind', '')
        title = artifact_data.get('title', filename.replace('.gif', ''))

        quality = parts[7] if len(parts) > 7 else '0'

        equipment.append({
            'artifact_id': artifact_id,
            'title': title,
            'filename': filename,
            'kind': kind,
            'quality': quality,
            'enchant': parts[2] if len(parts) > 2 else '',
            'enchant2': parts[3] if len(parts) > 3 else '',
            'enchant3': parts[4] if len(parts) > 4 else '',
            'enchant4': parts[5] if len(parts) > 5 else '',
            'enchant5': parts[6] if len(parts) > 6 else '',
            'full_data': artifact_data,
        })

    return equipment


def parse_medals_from_art_alt(artifacts):
    medals = []
    for key, data in artifacts.items():
        if data.get('kind') == 'Орден':
            medals.append(data)
    return medals


def parse_temp_effects(html):
    temp_effects_match = re.search(
        r'var temp_effects\s*=\s*(\[.*?\]);',
        html, re.DOTALL
    )
    if temp_effects_match:
        try:
            return json.loads(temp_effects_match.group(1))
        except json.JSONDecodeError:
            pass
    return []


def parse_permanent_effects(artifacts):
    permanent = []
    for key, data in artifacts.items():
        if data.get('kind') == 'Эффекты':
            permanent.append(data)
    return permanent


def parse_manor(html):
    result = {}

    manor_match = re.search(r'<b>находится:</b>\s*<b class="redd">([^<]+)</b>', html)
    if manor_match:
        result['location'] = manor_match.group(1).strip()

    buildings = re.findall(r'<img src="images/data/buildings/([^"]+)"', html)
    result['buildings'] = buildings

    return result


def parse_character(html, session=None, nick=None):
    result = {}

    name_match = re.search(r'<div class="h-txt">\s*(.-?\S+?-?)\s*</div>', html)
    result['name'] = name_match.group(1).strip() if name_match else 'Unknown'

    result['stats'] = parse_stats_tables(html)

    result['clan'] = parse_clan_info(html)

    result['professions'] = parse_profession_info(html)

    result['personal_info'] = parse_personal_info(html)

    artifacts = parse_art_alt_data(html)

    flashvars = parse_flashvars(html)
    result['flashvars'] = flashvars

    result['equipment_raw'] = parse_equipment_from_flashvars(flashvars, artifacts)

    result['medals'] = parse_medals_from_art_alt(artifacts)

    result['permanent_effects'] = parse_permanent_effects(artifacts)

    result['temp_effects'] = parse_temp_effects(html)

    manor = parse_manor(html)
    result['manor_location'] = manor.get('location', '')
    result['manor_buildings'] = manor.get('buildings', [])

    has_stats = len(result['stats']) > 0
    has_equipment = len(result['equipment_raw']) > 0

    if not has_stats and not has_equipment and session and nick:
        closed_info = check_profile_closed(session, nick, html)
        if closed_info and closed_info['closed']:
            result['profile_closed'] = True
            result['closed_info'] = closed_info

    return result
