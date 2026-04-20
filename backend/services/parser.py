import re
import json
from urllib.parse import urlparse, parse_qs, unquote
import requests
from utils.formatters import clean_html
import logging
from functools import lru_cache

# Pre-compile regex patterns for better performance
FLASHVARS_PATTERN = re.compile(r"flashvars\s*=\s*'([^']+)'")
PAR_PATTERN = re.compile(r"var par\s*=\s*'([^']+)'")
STATS_TABLE_PATTERN = re.compile(r'<table class="coll w100 p10h p2v brd2-all"[^>]*>(.*?)</table>', re.DOTALL)
STATS_ROW_PATTERN = re.compile(r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*align="right"[^>]*>(.*?)</td>\s*</tr>', re.DOTALL)
CLAN_INFO_PATTERN = re.compile(r'<tr id="clan_info">.*?<table class="coll w100 p10h p2v brd2-all"[^>]*>(.*?)</table>', re.DOTALL)
CLAN_ROW_PATTERN = re.compile(r'<td[^>]*>(.*?)</td>\s*<td[^>]*align="right"[^>]*>(.*?)</td>', re.DOTALL)
PROFESSION_INFO_PATTERN = re.compile(r'<tr id="profession_info">.*?<table class="coll w100 p10h p2v brd2-all"[^>]*>(.*?)</table>', re.DOTALL)
PROFESSION_ROW_PATTERN = re.compile(r'<td[^>]*>(.*?)</td>\s*<td[^>]*align="right"[^>]*>(.*?)</td>', re.DOTALL)
PERSONAL_INFO_PATTERN = re.compile(r'<tr id="personal_info">.*?<table class="coll w100 p10h p2v brd2-all"[^>]*>(.*?)</table>', re.DOTALL)
PERSONAL_ROW_PATTERN = re.compile(r'<td[^>]*>(.*?)</td>\s*<td[^>]*class=".*?redd.*?"[^>]*>(.*?)</td>', re.DOTALL)
ART_ALT_PATTERN = re.compile(r'art_alt\["AA_(\d+)"\]\s*=\s*(\{.+?\});</script>', re.DOTALL)
TEMP_EFFECTS_PATTERN = re.compile(r'var temp_effects\s*=\s*(\[.*?\]);', re.DOTALL)
CLAN_ID_PATTERN = re.compile(r'showClanInfo\((\d+)\)')
NAME_PATTERN = re.compile(r'<div class="h-txt">\s*([^<]+)\s*</div>')
MANOR_LOCATION_PATTERN = re.compile(r'<b>находится:</b>\s*<b class="redd">([^<]+)</b>')
MANOR_BUILDINGS_PATTERN = re.compile(r'<img src="images/data/buildings/([^"]+)"')
REDIRECT_PATTERN = re.compile(r"location\.href='([^']+)'")
CLOSED_PROFILE_PATTERN = re.compile(r'Перейти к игровой информации|noredir=')

# Valid equipment qualities
VALID_QUALITIES = {'0', '1', '2', '3', '4', '5'}

# Equipment kinds for validation
EQUIPMENT_KINDS = {
    'Шлем', 'Кираса', 'Кольчуга', 'Обувь', 'Наручи', 'Поножи',
    'Наплечники', 'Основное', 'Двуручное', 'Лук', 'Легкий щит',
    'Кольца', 'Амулет', 'Левая рука', 'Правая рука', 'Оправа',
    'Лак', 'Усиление', 'Магический символ', 'Символ', 'Аркат',
    'Знамя', 'Легендарный', 'Вещи стиля', 'Стиль', 'Медальон', 'Браслет',
}


def fetch_character_page(url):
    """
    Fetch character page with proper error handling and logging
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }
    session = requests.Session()
    
    try:
        resp = session.get(url, headers=headers, timeout=15)
        resp.raise_for_status()  # Raises HTTPError for bad responses
        resp.encoding = 'utf-8'
        html = resp.text

        # Check if we got a valid character page
        if 'art_alt' in html and 'h-txt' in html:
            logging.debug(f"Successfully fetched character page: {url}")
            return html, session

        # Handle redirects
        if CLOSED_PROFILE_PATTERN.search(html):
            redirect_match = REDIRECT_PATTERN.search(html)
            if redirect_match:
                redirect_url = redirect_match.group(1)
                if 'rating_info' in redirect_url:
                    logging.debug(f"Redirect to rating info page: {url}")
                    return html, session
                if not redirect_url.startswith('http'):
                    parsed = urlparse(url)
                    if not redirect_url.startswith('/'):
                        redirect_url = '/' + redirect_url
                    redirect_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                
                logging.debug(f"Following redirect: {redirect_url}")
                resp2 = session.get(redirect_url, headers=headers, timeout=15)
                resp2.raise_for_status()
                resp2.encoding = 'utf-8'
                return resp2.text, session

        logging.debug(f"Fetched page (may need further processing): {url}")
        return html, session
        
    except requests.Timeout:
        logging.error(f"Timeout fetching character page: {url}")
        raise
    except requests.RequestException as e:
        logging.error(f"Request error fetching character page {url}: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error fetching character page {url}: {str(e)}")
        raise


def check_profile_closed(session, nick, html):
    """
    Check if a profile is closed with proper error handling
    """
    try:
        ep_url = 'https://w1.dwar.ru/entry_point.php'
        data = {
            'object': 'user',
            'action': 'user_info',
            'nick': nick,
            'json_mode_on': '1'
        }
        resp = session.post(ep_url, data=data, timeout=10)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        result = json.loads(resp.text)
        user_info = result.get('user|user_info', {})
        return {
            'closed': bool(user_info.get('closed', False) or user_info.get('user_close_info', False)),
            'level': str(user_info.get('level', '')),
            'rank': str(user_info.get('rank', '')),
            'picture': str(user_info.get('picture', '')),
            'description': str(user_info.get('description', '')),
            'premium_level': str(user_info.get('premium_level', '')),
        }
    except requests.Timeout:
        logging.error(f"Timeout checking profile closed for nick: {nick}")
        return None
    except requests.RequestException as e:
        logging.error(f"Request error checking profile closed for nick {nick}: {str(e)}")
        return None
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logging.error(f"Data parsing error checking profile closed for nick {nick}: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error checking profile closed for nick {nick}: {str(e)}")
        return None


def parse_flashvars(html):
    """
    Parse flashvars and par variables from HTML with improved performance
    """
    flashvars_data = {}

    try:
        # Parse flashvars
        flashvars_match = FLASHVARS_PATTERN.search(html)
        if flashvars_match:
            params = parse_qs(flashvars_match.group(1))
            for key, values in params.items():
                flashvars_data[key] = values[0] if len(values) == 1 else values

        # Parse par variables
        par_match = PAR_PATTERN.search(html)
        if par_match:
            params = parse_qs(par_match.group(1))
            for key, values in params.items():
                flashvars_data[key] = values[0] if len(values) == 1 else values

        logging.debug(f"Parsed flashvars: {list(flashvars_data.keys())}")
        return flashvars_data
    except Exception as e:
        logging.error(f"Error parsing flashvars: {str(e)}")
        return flashvars_data  # Return what we have so far


def validate_stats_value(value):
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(' ', '').replace(',', '.')
        try:
            return int(float(cleaned))
        except (ValueError, AttributeError):
            return 0
    return 0


def parse_stats_tables(html):
    """
    Parse statistics tables from HTML with data validation
    """
    all_stats = {}

    try:
        stats_tables = STATS_TABLE_PATTERN.findall(html)

        for table_html in stats_tables:
            rows = STATS_ROW_PATTERN.findall(table_html)
            for label, value in rows:
                label = clean_html(label)
                value = clean_html(value)
                if label and value:
                    all_stats[label] = value

        logging.debug(f"Parsed {len(all_stats)} stats")
        return all_stats
    except Exception as e:
        logging.error(f"Error parsing stats tables: {str(e)}")
        return all_stats


def parse_clan_info(html):
    """
    Parse clan information from HTML with data validation
    """
    clan_info = {}

    try:
        clan_match = CLAN_INFO_PATTERN.search(html)
        if not clan_match:
            logging.debug("No clan info found in HTML")
            return clan_info

        clan_rows = CLAN_ROW_PATTERN.findall(clan_match.group(1))
        for label, value in clan_rows:
            label = clean_html(label)
            value = clean_html(value)
            if label and value:
                clan_info[label] = value

        clan_id_match = CLAN_ID_PATTERN.search(html)
        if clan_id_match:
            clan_info['_clan_id'] = clan_id_match.group(1)

        logging.debug(f"Parsed clan info with {len(clan_info)} fields")
        return clan_info
    except Exception as e:
        logging.error(f"Error parsing clan info: {str(e)}")
        return clan_info  # Return what we have so far


def parse_profession_info(html):
    """
    Parse profession information from HTML with data validation
    """
    professions = {}

    try:
        prof_match = PROFESSION_INFO_PATTERN.search(html)
        if not prof_match:
            logging.debug("No profession info found in HTML")
            return professions

        prof_rows = PROFESSION_ROW_PATTERN.findall(prof_match.group(1))
        for label, value in prof_rows:
            label = clean_html(label)
            value = clean_html(value)
            if label and value:
                professions[label] = value

        logging.debug(f"Parsed {len(professions)} professions")
        return professions
    except Exception as e:
        logging.error(f"Error parsing profession info: {str(e)}")
        return professions  # Return what we have so far


def parse_personal_info(html):
    """
    Parse personal information from HTML with data validation
    """
    personal_info = {}

    try:
        personal_match = PERSONAL_INFO_PATTERN.search(html)
        if not personal_match:
            logging.debug("No personal info found in HTML")
            return personal_info

        rows = PERSONAL_ROW_PATTERN.findall(personal_match.group(1))
        for label, value in rows:
            label = clean_html(label).replace(':', '').strip()
            value = clean_html(value)
            if label and value:
                personal_info[label] = value

        logging.debug(f"Parsed {len(personal_info)} personal info fields")
        return personal_info
    except Exception as e:
        logging.error(f"Error parsing personal info: {str(e)}")
        return personal_info  # Return what we have so far


def parse_art_alt_data(html):
    """
    Parse art_alt data from HTML with improved error handling
    """
    artifacts = {}

    try:
        matches = ART_ALT_PATTERN.findall(html)

        for artifact_id, json_str in matches:
            try:
                data = json.loads(json_str)
                data['artifact_id'] = artifact_id
                artifacts[f'AA_{artifact_id}'] = data
            except json.JSONDecodeError as e:
                logging.warning(f"JSON decode error for artifact AA_{artifact_id}: {str(e)}")
                continue

        logging.debug(f"Parsed {len(artifacts)} artifacts from art_alt data")
        return artifacts
    except Exception as e:
        logging.error(f"Error parsing art_alt data: {str(e)}")
        return artifacts  # Return what we have so far


def parse_equipment_from_flashvars(flashvars_data, artifacts):
    """
    Parse equipment from flashvars data with validation
    """
    equipment = []

    try:
        arts_raw = flashvars_data.get('arts', '')
        if not arts_raw:
            logging.debug("No arts data found in flashvars")
            return equipment

        items = arts_raw.split(',')
        for item_str in items:
            parts = item_str.split(':')
            if len(parts) < 8:
                logging.debug(f"Skipping invalid equipment item: {item_str}")
                continue

            artifact_id = parts[0]
            filename = parts[1]

            artifact_key = f'AA_{artifact_id}'
            artifact_data = artifacts.get(artifact_key, {})

            kind = artifact_data.get('kind', '')
            title = artifact_data.get('title', filename.replace('.gif', ''))
            
            # Log ALL kinds for debugging
            logging.info(f"Artifact {artifact_id}: kind='{kind}', title='{title}'")
            
            # Validate kind against known equipment kinds
            if kind and kind not in EQUIPMENT_KINDS:
                logging.warning(f"Unknown equipment kind '{kind}' for artifact {artifact_id} title '{title}'")
                # Keep the original kind but log it

            quality = parts[7] if len(parts) > 7 else '0'
            # Validate quality
            if quality not in VALID_QUALITIES:
                logging.warning(f"Invalid quality '{quality}' for artifact {artifact_id}, defaulting to '0'")
                quality = '0'

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

        logging.debug(f"Parsed {len(equipment)} equipment items from flashvars")
        return equipment
    except Exception as e:
        logging.error(f"Error parsing equipment from flashvars: {str(e)}")
        return equipment  # Return what we have so far


def parse_medals_from_art_alt(artifacts):
    """
    Parse medals from artifacts data
    """
    medals = []
    try:
        for key, data in artifacts.items():
            if isinstance(data, dict) and data.get('kind') == 'Орден':
                medals.append(data)
        
        logging.debug(f"Parsed {len(medals)} medals from artifacts")
        return medals
    except Exception as e:
        logging.error(f"Error parsing medals from artifacts: {str(e)}")
        return medals  # Return what we have so far


def parse_temp_effects(html):
    """
    Parse temporary effects from HTML
    """
    try:
        temp_effects_match = TEMP_EFFECTS_PATTERN.search(html)
        if temp_effects_match:
            try:
                return json.loads(temp_effects_match.group(1))
            except json.JSONDecodeError as e:
                logging.warning(f"JSON decode error in temp_effects: {str(e)}")
                return []
        return []
    except Exception as e:
        logging.error(f"Error parsing temp effects: {str(e)}")
        return []


def parse_permanent_effects(artifacts):
    """
    Parse permanent effects from artifacts data
    """
    permanent = []
    try:
        for key, data in artifacts.items():
            if isinstance(data, dict) and data.get('kind') == 'Эффекты':
                permanent.append(data)
        
        logging.debug(f"Parsed {len(permanent)} permanent effects from artifacts")
        return permanent
    except Exception as e:
        logging.error(f"Error parsing permanent effects from artifacts: {str(e)}")
        return permanent  # Return what we have so far


def parse_manor(html):
    """
    Parse manor information from HTML
    """
    result = {}
    try:
        manor_match = MANOR_LOCATION_PATTERN.search(html)
        if manor_match:
            result['location'] = manor_match.group(1).strip()

        buildings = MANOR_BUILDINGS_PATTERN.findall(html)
        result['buildings'] = buildings

        logging.debug(f"Parsed manor location: {result.get('location', 'None')}, {len(result.get('buildings', []))} buildings")
        return result
    except Exception as e:
        logging.error(f"Error parsing manor info: {str(e)}")
        return result  # Return what we have so far


def parse_character(html, session=None, nick=None):
    """
    Parse character data from HTML with comprehensive error handling and validation
    """
    result = {}
    
    try:
        # Extract name with validation
        name_match = NAME_PATTERN.search(html)
        result['name'] = name_match.group(1).strip() if name_match else 'Unknown'
        
        # Parse all data components
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
        
        # Check for closed profile if essential data is missing
        has_stats = len(result['stats']) > 0
        has_equipment = len(result['equipment_raw']) > 0
        
        if not has_stats and not has_equipment and session and nick:
            closed_info = check_profile_closed(session, nick, html)
            if closed_info and closed_info.get('closed'):
                result['profile_closed'] = True
                result['closed_info'] = closed_info
        
        logging.debug(f"Successfully parsed character: {result.get('name', 'Unknown')}")
        return result
        
    except Exception as e:
        logging.error(f"Error parsing character: {str(e)}")
        # Return partial results if possible
        if not result.get('name'):
            result['name'] = 'Unknown'
        if 'stats' not in result:
            result['stats'] = {}
        if 'clan' not in result:
            result['clan'] = {}
        if 'professions' not in result:
            result['professions'] = {}
        if 'personal_info' not in result:
            result['personal_info'] = {}
        if 'flashvars' not in result:
            result['flashvars'] = {}
        if 'equipment_raw' not in result:
            result['equipment_raw'] = []
        if 'medals' not in result:
            result['medals'] = []
        if 'permanent_effects' not in result:
            result['permanent_effects'] = []
        if 'temp_effects' not in result:
            result['temp_effects'] = []
        if 'manor_location' not in result:
            result['manor_location'] = ''
        if 'manor_buildings' not in result:
            result['manor_buildings'] = []
            
        return result
