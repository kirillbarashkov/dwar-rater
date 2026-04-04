from flask import Flask, request, jsonify, render_template, abort, g
from functools import wraps
import requests
import re
import json
import os
import hashlib
import time
import secrets
from urllib.parse import unquote, urlparse, parse_qs
from datetime import datetime, timedelta

from config import Config
from models import db, User, CharacterCache, CharacterSnapshot, AnalysisLog

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(Config)

db.init_app(app)

# Cache TTL: 1 hour (avoid hitting dwar.ru too often)
CACHE_TTL_SECONDS = 3600

# Authentication
AUTH_ENABLED = Config.AUTH_ENABLED
USERS = {}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
users_file = os.path.join(BASE_DIR, 'users.json')
if os.path.exists(users_file):
    with open(users_file, 'r') as f:
        USERS = json.load(f)
else:
    admin_user = Config.ADMIN_USER
    admin_pass = Config.ADMIN_PASS
    if admin_pass != 'admin' or not AUTH_ENABLED:
        USERS[admin_user] = {
            'password_hash': hashlib.sha256(admin_pass.encode()).hexdigest(),
            'role': 'admin'
        }

# Rate limiting
rate_limit_store = {}
RATE_LIMIT_MAX = Config.RATE_LIMIT_MAX
RATE_LIMIT_WINDOW = Config.RATE_LIMIT_WINDOW

QUALITY_MAP = {
    '0': {'name': 'Серый', 'color': '#e0e0e0', 'emoji': '⚪'},
    '1': {'name': 'Зелёный', 'color': '#339900', 'emoji': '🟢'},
    '2': {'name': 'Синий', 'color': '#3300ff', 'emoji': '🔵'},
    '3': {'name': 'Фиолетовый', 'color': '#990099', 'emoji': '🟣'},
    '4': {'name': 'Красный', 'color': '#016e71', 'emoji': '🔴'},
    '5': {'name': 'Оранжевый', 'color': '#ff0000', 'emoji': '🟠'},
    '6': {'name': 'Уникальный', 'color': '#f55e27', 'emoji': '🌟'},
}

EQUIPMENT_KINDS = {
    'Шлем', 'Кираса', 'Кольчуга', 'Обувь', 'Наручи', 'Поножи',
    'Наплечники', 'Основное', 'Двуручное', 'Лук', 'Легкий щит',
    'Кольца', 'Амулет'
}

SLOT_ORDER = [
    'Шлем', 'Наплечники', 'Кираса', 'Кольчуга', 'Наручи', 'Поножи', 'Обувь',
    'Основное', 'Двуручное', 'Лук', 'Легкий щит', 'Кольца', 'Амулет'
]


# --- Security middleware ---

def check_rate_limit():
    ip = request.remote_addr
    now = time.time()
    key = f"rl:{ip}"
    if key not in rate_limit_store:
        rate_limit_store[key] = []
    rate_limit_store[key] = [t for t in rate_limit_store[key] if now - t < RATE_LIMIT_WINDOW]
    if len(rate_limit_store[key]) >= RATE_LIMIT_MAX:
        return False
    rate_limit_store[key].append(now)
    return True


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not AUTH_ENABLED:
            g.current_user = User.query.filter_by(username=Config.ADMIN_USER).first()
            if not g.current_user:
                g.current_user = User(username=Config.ADMIN_USER, password_hash=hashlib.sha256(Config.ADMIN_PASS.encode()).hexdigest(), role='admin')
                db.session.add(g.current_user)
                try:
                    db.session.commit()
                except:
                    db.session.rollback()
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_credentials(auth.username, auth.password):
            return jsonify({'error': 'Требуется авторизация'}), 401
        g.current_user = User.query.filter_by(username=auth.username).first()
        if not g.current_user:
            # Auto-create user from users.json if not in DB
            user_data = USERS.get(auth.username, {})
            g.current_user = User(
                username=auth.username,
                password_hash=user_data.get('password_hash', hashlib.sha256(auth.password.encode()).hexdigest()),
                role=user_data.get('role', 'user')
            )
            db.session.add(g.current_user)
            try:
                db.session.commit()
            except:
                db.session.rollback()
        return f(*args, **kwargs)
    return decorated


def check_credentials(username, password):
    if username not in USERS:
        return False
    return USERS[username]['password_hash'] == hashlib.sha256(password.encode()).hexdigest()


@app.before_request
def security_checks():
    if request.path == '/api/login' or request.path == '/':
        return
    if request.path.startswith('/static/'):
        return
    if not check_rate_limit():
        return jsonify({'error': 'Слишком много запросов. Подождите.'}), 429
    if request.method == 'POST':
        content_type = request.content_type or ''
        if 'application/json' not in content_type:
            abort(415)


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline';"
    return response


# --- Helpers ---

def clean_html(text):
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-z]+;', '', text)
    text = re.sub(r'&#\d+;', '', text)
    return text.strip()


def fmt_num(n):
    try:
        return f"{int(n):,}".replace(',', ' ')
    except (ValueError, TypeError):
        return str(n)


def get_cached_character(nick):
    """Get character data from cache if not expired"""
    cached = CharacterCache.query.filter_by(nick=nick).first()
    if cached and (datetime.utcnow() - cached.updated_at).total_seconds() < CACHE_TTL_SECONDS:
        return json.loads(cached.raw_data)
    return None


def save_character_cache(nick, raw_data):
    """Save character data to cache"""
    cached = CharacterCache.query.filter_by(nick=nick).first()
    if cached:
        cached.raw_data = json.dumps(raw_data, ensure_ascii=False)
        cached.updated_at = datetime.utcnow()
    else:
        cached = CharacterCache(nick=nick, raw_data=json.dumps(raw_data, ensure_ascii=False))
        db.session.add(cached)
    db.session.commit()


def save_snapshot(raw_data):
    """
    Save a permanent snapshot of character analysis.
    The entire processed result is stored as JSON for future-proofing.
    Returns the snapshot id.
    """
    snapshot = CharacterSnapshot(
        nick=raw_data.get('name', ''),
        name=raw_data.get('name', ''),
        race=raw_data.get('race', ''),
        rank=raw_data.get('rank', ''),
        clan=raw_data.get('clan', ''),
        snapshot_data=json.dumps(raw_data, ensure_ascii=False),
    )
    db.session.add(snapshot)
    db.session.flush()
    return snapshot.id


def log_analysis(nick, url, snapshot_id=None):
    """Log an analysis request, linked to a snapshot"""
    log = AnalysisLog(nick=nick, url=url, snapshot_id=snapshot_id)
    db.session.add(log)
    db.session.commit()


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
    except:
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
        except:
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


def format_skills(skills):
    if not skills:
        return []
    result = []
    for s in skills:
        title = s.get('title', '')
        value = clean_html(s.get('value', ''))
        result.append({'title': title, 'value': value})
    return result


def format_enchants(item):
    enchants = []
    if 'enchant' in item:
        enchants.append({'type': 'Руна', 'value': clean_html(item['enchant'].get('value', ''))})
    if 'enchant2' in item:
        enchants.append({'type': 'Руна 2', 'value': clean_html(item['enchant2'].get('value', ''))})
    if 'enchant_mod' in item:
        enchants.append({'type': 'Встроено', 'value': clean_html(item['enchant_mod'].get('value', ''))})
    if 'enchant3' in item:
        enchants.append({'type': 'Оправа', 'value': clean_html(item['enchant3'].get('value', ''))})
    if 'enchant4' in item:
        enchants.append({'type': 'Лак', 'value': clean_html(item['enchant4'].get('value', ''))})
    if 'enchant5' in item:
        enchants.append({'type': 'Усиление', 'value': clean_html(item['enchant5'].get('value', ''))})
    if 'symbols' in item:
        for i, sym in enumerate(item['symbols'], 1):
            enchants.append({'type': f'Символ {i}', 'value': clean_html(sym.get('value', ''))})
    return enchants


def process_character(raw_data):
    if raw_data.get('profile_closed'):
        closed_info = raw_data.get('closed_info', {})
        return {
            'profile_closed': True,
            'name': raw_data['name'],
            'closed_info': {
                'level': closed_info.get('level', ''),
                'rank': closed_info.get('rank', ''),
                'picture': closed_info.get('picture', ''),
                'description': closed_info.get('description', ''),
                'premium_level': closed_info.get('premium_level', ''),
            }
        }

    stats = raw_data['stats']
    wins = int(stats.get('Побед', 0))
    losses = int(stats.get('Поражений', 0))
    total = wins + losses
    wr = round(wins / total * 100, 2) if total > 0 else 0

    vb_wins = int(stats.get('Победы в Великих битвах', 0))
    vb_total = int(stats.get('Участие в Великих битвах', 0))
    vb_wr = round(vb_wins / vb_total * 100, 2) if vb_total > 0 else 0

    kill_key = 'Убито магмаров' if 'Убито магмаров' in stats else 'Убито людей'

    equipment = raw_data['equipment']
    equipment_by_kind = {}
    for item in equipment:
        kind = item.get('kind', 'Другое')
        if kind not in equipment_by_kind:
            equipment_by_kind[kind] = []
        equipment_by_kind[kind].append({
            'title': item.get('title', ''),
            'quality': QUALITY_MAP.get(item.get('quality', '0'), QUALITY_MAP['0']),
            'level': item.get('lev', {}).get('value', '—') if 'lev' in item else '—',
            'trend': item.get('trend', ''),
            'durability': f"{item.get('dur', '?')}/{item.get('dur_max', '?')}" if 'dur' in item else '∞',
            'skills': format_skills(item.get('skills', [])),
            'skills_e': format_skills(item.get('skills_e', [])),
            'enchants': format_enchants(item),
            'set': clean_html(item.get('set', {}).get('value', '')) if 'set' in item else '',
        })

    sets = {}
    for item in equipment:
        if 'set' in item:
            set_name = clean_html(item['set'].get('value', ''))
            if set_name not in sets:
                sets[set_name] = []
            sets[set_name].append(item.get('title', ''))

    medals = []
    for i, medal in enumerate(raw_data['medals'], 1):
        desc = medal.get('desc', '')
        rep_name = ''

        clan_match = re.search(r'class="redd">(.+?)</a>', desc)
        if not clan_match:
            clan_match = re.search(r'<a[^>]*>(.+?)</a>', desc)
        if clan_match:
            rep_name = clean_html(clan_match.group(1))

        if not rep_name:
            m = re.search(r'перед\s+(.+?)(?:\.\s|<br| и\s)', desc)
            if m:
                rep_name = clean_html(m.group(1))

        if not rep_name:
            m = re.search(r'воина\s+(?:перед\s+)?(.+?)\.\s', desc)
            if m:
                rep_name = clean_html(m.group(1))

        if not rep_name:
            m = re.search(r'заслуги\s+(.+?)(?:и\s+достижение|\.)', desc, re.DOTALL)
            if m:
                rep_name = clean_html(m.group(1))

        rep_name = re.sub(r'\.\s*Е[йё]ю\s+.*$', '', rep_name)
        rep_name = re.sub(r'\.\s*Можно\s+.*$', '', rep_name)
        rep_name = re.sub(r'\s*<br\s*/?>.*$', '', rep_name)
        rep_name = rep_name.strip()
        rep_name = re.sub(r'^(перед|воина\s+перед|заслуги\s+перед|заслуги\s+)\s*', '', rep_name)
        rep_name = re.sub(r'^(среди|расой|орденом|кланом)\s+', '', rep_name)
        rep_name = rep_name.strip('«»"\'')

        rep_mapping = {
            'гномами небесной долины': 'Репутация гномов Небесной долины',
            'гномы небесной долины': 'Репутация гномов Небесной долины',
            'каменный лотос': 'Репутация «Каменного лотоса»',
            'хранителей красоты': 'Репутация Хранителей Красоты',
            'крадущиеся в ночи': 'Репутация «Крадущихся в ночи»',
            'вершителями судеб': 'Репутация вершителей судеб',
            'вершители судеб': 'Репутация вершителей судеб',
            'орденом подземных рыцарей': 'Репутация подземных рыцарей',
            'подземных рыцарей': 'Репутация подземных рыцарей',
            'джаггернаутов': 'Репутация Джаггернаутов',
            'джаггернауты': 'Репутация Джаггернаутов',
            'жителей мистрас': 'Репутация среди жителей Мистрас',
            'искателей мудрости': 'Репутация Искателей Мудрости',
            'великих битвах': 'Репутация участника Великих битв',
            'охотниками за нежитью': 'Репутация охотника на нежить',
            'охотники за нежитью': 'Репутация охотника на нежить',
            'охотников за нежитью': 'Репутация охотника на нежить',
            'красные топоры': 'Репутация «Красных топоров»',
            'искателями реликтов': 'Репутация искателя реликтов',
            'искатели реликтов': 'Репутация искателя реликтов',
            'искателей реликтов': 'Репутация искателя реликтов',
            'исследователями лабиринта': 'Репутация Исследователей Лабиринта',
            'флаундинов': 'Репутация Флаундинов',
            'богом мертвых и проклятых': 'Репутация бога мертвых и проклятых',
            'ловцами фортуны': 'Репутация ловцов фортуны',
            'ловцы фортуны': 'Репутация ловцов фортуны',
            'борцами с хаосом': 'Репутация борца с Хаосом',
            'борцы с хаосом': 'Репутация борца с Хаосом',
            'великим драконом': 'Репутация великого Дракона',
            'великий дракон': 'Репутация великого Дракона',
            'богиней аладеей': 'Репутация богини Аладеи',
            'богиня аладеи': 'Репутация богини Аладеи',
            'искателями реликтов': 'Репутация искателя реликтов',
            'искатели реликтов': 'Репутация искателя реликтов',
            'братством добродетели': 'Репутация Братства Добродетели',
            'братство добродетели': 'Репутация Братства Добродетели',
            'вершителей зла': 'Репутация вершителя Зла',
            'вершитель зла': 'Репутация вершителя Зла',
            'егеря': 'Репутация егеря',
            'мистика': 'Репутация мистика',
            'охотников за трофеями': 'Репутация Охотников за трофеями',
            'кладоискателей': 'Репутация Кладоискателей',
            'красных топоров': 'Репутация «Красных топоров»',
            'дартронга': 'Репутация Дартронга',
        }

        rep_lower = rep_name.lower()
        matched = False
        for key, canonical in rep_mapping.items():
            if key in rep_lower:
                rep_name = canonical
                matched = True
                break

        if not matched and rep_name:
            rep_name = 'Репутация ' + rep_name[0].upper() + rep_name[1:]

        rep_name = rep_name.strip()
        if not rep_name or len(rep_name) < 5:
            rep_name = 'Общая'

        medals.append({
            'num': i,
            'title': medal.get('title', ''),
            'quality': QUALITY_MAP.get(medal.get('quality', '0'), QUALITY_MAP['0']),
            'reputation': rep_name,
            'description': clean_html(medal.get('desc', '')),
        })

    permanent_effects = []
    for eff in raw_data.get('permanent_effects', []):
        skills = []
        for s in eff.get('skills', []):
            skills.append({
                'title': s.get('title', ''),
                'value': clean_html(s.get('value', '')),
            })
        permanent_effects.append({
            'title': eff.get('title', ''),
            'quality': QUALITY_MAP.get(eff.get('quality', '0'), QUALITY_MAP['0']),
            'skills': skills,
            'desc': clean_html(eff.get('desc', '')),
            'image': eff.get('image', ''),
        })

    temp_effects = []
    for eff in raw_data.get('temp_effects', []):
        skills = []
        for s in eff.get('skills', []):
            skills.append({
                'title': s.get('title', ''),
                'value': clean_html(s.get('value', '')),
            })

        kind_id = eff.get('kind_id', '')
        flags = int(eff.get('flags', 0)) if eff.get('flags') else 0
        del_after = eff.get('del_after_fight', 0)

        if kind_id == '65':
            if 'проклят' in eff.get('title', '').lower() or flags > 100000:
                category = 'debuff'
            else:
                category = 'buff'
        elif kind_id == '22':
            category = 'elixir'
        elif kind_id == '103':
            category = 'mount'
        else:
            category = 'other'

        temp_effects.append({
            'title': eff.get('title', ''),
            'time_left': eff.get('time_left', ''),
            'time_left_sec': int(eff.get('time_left_sec', 0)),
            'quality': QUALITY_MAP.get(eff.get('quality', '0'), QUALITY_MAP['0']),
            'skills': skills,
            'desc': clean_html(eff.get('desc', '')),
            'category': category,
            'kind_id': kind_id,
            'del_after_fight': bool(del_after),
            'picture': eff.get('picture', ''),
        })

    category_order = {'buff': 0, 'elixir': 1, 'mount': 2, 'debuff': 3, 'other': 4}
    temp_effects.sort(key=lambda e: (category_order.get(e['category'], 4), -e['time_left_sec']))

    return {
        'name': raw_data['name'],
        'race': stats.get('Раса', ''),
        'rank': stats.get('Звание', ''),
        'clan': raw_data.get('clan', {}).get('Клан', ''),
        'clan_rank': raw_data.get('clan', {}).get('Звание', ''),
        'wins': fmt_num(wins),
        'losses': fmt_num(losses),
        'winrate': wr,
        'kills': fmt_num(stats.get(kill_key, 0)),
        'main_stats': {k: fmt_num(stats.get(k, 0)) for k in ['Живучесть', 'Защита', 'Интуиция', 'Ловкость', 'Сила']},
        'combat_stats': {k: fmt_num(stats.get(k, 0)) for k in ['Инициатива', 'Стойкость']},
        'magic_stats': {k: fmt_num(stats.get(k, 0)) for k in ['Воля', 'Интеллект', 'Концентрация', 'Мудрость', 'Подавление']},
        'social': {'Популярность': fmt_num(stats.get('Популярность', 0))},
        'achievements': {k: fmt_num(stats.get(k, 0)) for k in ['«Золотые Атши»', 'Сдано «Орочьих Голов»', '[Юбилейный свиток] текущий уровень', 'Подарено браслетов']},
        'great_battles': {
            'wins': fmt_num(vb_wins),
            'total': fmt_num(vb_total),
            'winrate': vb_wr,
        },
        'combat_records': {k: fmt_num(stats.get(k, 0)) for k in [
            'Максимальное количество критов', 'Максимальное количество блоков', 'Максимальный крит',
            'Максимальное количество уворотов', 'Максимальное количество смертей', 'Максимальное количество убийств',
            'Максимальное количество ударов', 'Максимально полученный крит',
            'Максимальное количество промахов', 'Максимальное количество ударов в блок',
        ]},
        'professions': raw_data.get('professions', {}),
        'equipment_by_kind': equipment_by_kind,
        'sets': sets,
        'medals': medals,
        'permanent_effects': permanent_effects,
        'temp_effects': temp_effects,
        'manor_location': raw_data.get('manor_location', ''),
        'manor_buildings': raw_data.get('manor_buildings', []),
    }


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/login', methods=['POST'])
def login():
    auth = request.authorization
    if not auth:
        return jsonify({'error': 'Неверный логин или пароль'}), 401
    if not check_credentials(auth.username, auth.password):
        return jsonify({'error': 'Неверный логин или пароль'}), 401
    return jsonify({'status': 'ok'})


@app.route('/api/analyze', methods=['POST'])
@require_auth
def analyze():
    data = request.json
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL не указан'}), 400

    parsed = urlparse(url)
    allowed_domains = ['w1.dwar.ru', 'w2.dwar.ru', 'w3.dwar.ru', 'w4.dwar.ru', 'dwar.ru']
    if parsed.netloc not in allowed_domains:
        return jsonify({'error': 'Разрешены только ссылки на dwar.ru'}), 403

    if not url.startswith('http'):
        nick = url
        if 'nick=' in nick:
            nick = nick.split('nick=')[1].split('&')[0]
        url = f'https://w1.dwar.ru/user_info.php?nick={nick}'
    else:
        nick = parse_qs(urlparse(url).query).get('nick', [''])[0]

    # Check cache first
    cached = get_cached_character(nick)
    if cached:
        log_analysis(nick, url)
        return jsonify(process_character(cached))

    # Fetch fresh data
    try:
        html, session = fetch_character_page(url)
        raw = parse_character(html, session=session, nick=nick)

        # Save to cache (short-term, 1 hour TTL)
        save_character_cache(nick, raw)

        # Save permanent snapshot
        processed = process_character(raw)
        snapshot_id = save_snapshot(processed)

        # Log analysis linked to snapshot
        log_analysis(nick, url, snapshot_id=snapshot_id)

        return jsonify(processed)
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Таймаут запроса к серверу dwar.ru'}), 504
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Ошибка загрузки страницы: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Ошибка обработки: {str(e)}'}), 500


@app.route('/api/snapshots', methods=['GET'])
@require_auth
def list_snapshots():
    """List saved character snapshots. Admin sees all, users see only their own."""
    nick = request.args.get('nick', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    user = g.current_user

    query = CharacterSnapshot.query
    if user.role != 'admin':
        query = query.filter_by(user_id=user.id)
    if nick:
        query = query.filter(CharacterSnapshot.nick.ilike(f'%{nick}%'))

    query = query.order_by(CharacterSnapshot.analyzed_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
        'snapshots': [{
            'id': s.id,
            'nick': s.nick,
            'name': s.name,
            'race': s.race,
            'rank': s.rank,
            'clan': s.clan,
            'snapshot_name': s.snapshot_name,
            'analyzed_at': s.analyzed_at.isoformat(),
        } for s in pagination.items]
    })


@app.route('/api/snapshots/<int:snapshot_id>', methods=['GET'])
@require_auth
def get_snapshot(snapshot_id):
    """Get a specific snapshot. Admin can access any, users only their own."""
    user = g.current_user
    snapshot = CharacterSnapshot.query.get_or_404(snapshot_id)
    if user.role != 'admin' and snapshot.user_id != user.id:
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = json.loads(snapshot.snapshot_data)
    data['snapshot_id'] = snapshot.id
    data['snapshot_name'] = snapshot.snapshot_name
    data['analyzed_at'] = snapshot.analyzed_at.isoformat()
    return jsonify(data)


@app.route('/api/snapshots/<int:snapshot_id>', methods=['DELETE'])
@require_auth
def delete_snapshot(snapshot_id):
    """Delete a snapshot. Admin can delete any, users only their own."""
    user = g.current_user
    snapshot = CharacterSnapshot.query.get_or_404(snapshot_id)
    if user.role != 'admin' and snapshot.user_id != user.id:
        return jsonify({'error': 'Доступ запрещён'}), 403
    db.session.delete(snapshot)
    db.session.commit()
    return jsonify({'status': 'deleted'})


@app.route('/api/save-snapshot', methods=['POST'])
@require_auth
def save_snapshot_endpoint():
    """Save analysis result as a named snapshot, linked to current user."""
    data = request.json
    snapshot_data = data.get('snapshot_data')
    snapshot_name = data.get('snapshot_name', '')
    url = data.get('url', '')
    user = g.current_user

    if not snapshot_data:
        return jsonify({'error': 'Нет данных для сохранения'}), 400

    snapshot_data['snapshot_name'] = snapshot_name

    snapshot = CharacterSnapshot(
        user_id=user.id,
        nick=snapshot_data.get('name', ''),
        name=snapshot_data.get('name', ''),
        race=snapshot_data.get('race', ''),
        rank=snapshot_data.get('rank', ''),
        clan=snapshot_data.get('clan', ''),
        snapshot_name=snapshot_name,
        snapshot_data=json.dumps(snapshot_data, ensure_ascii=False),
    )
    db.session.add(snapshot)
    db.session.flush()

    log_analysis(snapshot_data.get('name', ''), url, snapshot_id=snapshot.id)

    return jsonify({
        'status': 'saved',
        'snapshot_id': snapshot.id,
        'analyzed_at': snapshot.analyzed_at.isoformat(),
    })


# --- Init DB ---

def init_db():
    with app.app_context():
        db.create_all()

        # Create admin user if not exists
        if not User.query.filter_by(username=Config.ADMIN_USER).first():
            admin = User(
                username=Config.ADMIN_USER,
                password_hash=hashlib.sha256(Config.ADMIN_PASS.encode()).hexdigest(),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print(f"Admin user created: {Config.ADMIN_USER}")


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
