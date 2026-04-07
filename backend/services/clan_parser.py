import re
from urllib.parse import urlparse
import requests
from utils.formatters import clean_html


def fetch_clan_page(clan_id, mode='news'):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }
    url = f'https://w1.dwar.ru/clan_info.php?clan_id={clan_id}&mode={mode}'
    session = requests.Session()
    resp = session.get(url, headers=headers, timeout=15)
    resp.encoding = 'utf-8'
    return resp.text, session


def parse_clan_info(html, clan_id):
    result = {'clan_id': clan_id}

    name_match = re.search(r'<div class="h-txt">\s*(.*?)\s*</div>', html)
    result['name'] = clean_html(name_match.group(1)) if name_match else ''

    logo_match = re.search(r'<img src="([^"]*clan_logos/[^"]+)"', html)
    result['logo_url'] = logo_match.group(1) if logo_match else ''

    desc_match = re.search(r'<table class="coll w100 p6v p10h p2v brd2-all">\s*<tbody>\s*<tr class="bg_l">\s*<td[^>]*>(.*?)</td>', html, re.DOTALL)
    if desc_match:
        desc_html = desc_match.group(1)
        desc_html = re.sub(r'<a[^>]*>Читать далее</a>', '', desc_html)
        result['description'] = clean_html(desc_html).strip()

    leader_match = re.search(r'Глава.*?<a[^>]*><b>(.*?)\s*\[(\d+)\]</b>', html, re.DOTALL)
    if leader_match:
        result['leader_nick'] = leader_match.group(1).strip()
        result['leader_rank'] = leader_match.group(2).strip()

    status_match = re.search(r'<img[^>]*title="([^"]+)"[^>]*src="/images/ranks/rank\d+\.gif"[^>]*>\s*(.*?)\s*\[(\d+)\].*?src="/images/clans/steps/(\d+)\.png"', html, re.DOTALL)
    if status_match:
        result['clan_rank'] = status_match.group(1).strip()
        level_match = re.search(r'\[(\d+)\]', status_match.group(0))
        result['clan_level'] = int(level_match.group(1)) if level_match else 0
        result['step'] = int(status_match.group(4))

    talents_match = re.search(r'Развитие талантов клана:\s*(\d+)', html)
    if talents_match:
        result['talents'] = int(talents_match.group(1))

    return result


def parse_clan_members(html, clan_id):
    members = []

    blocks = re.split(r'\n{2,}', html)

    current_member = {}
    for line in html.split('\n'):
        line = line.strip()
        if not line:
            continue

        nick_match = re.search(r'(?:Герой|Властелин боя|Вершитель|Магистр войны|Повелитель|Полководец|Легендарный завоеватель|Военный эксперт|Мастер войны|Элитный воин|Гладиатор|Чемпион|Избранник богов|Триумфатор|Высший магистр|Глава Ордена|Зам\. Главы|Совесть|Рыцарь Ордена|Леди Ордена|ГардеМаринкА|Фея на метле|Лентяй|Пельмешка|Dead\'ok|Воевода|9-ть жЫзней\)|УлитЫчка\)|РудольФ|Сосиска)\s+([^\[]+)\[(\d+)\](?:([^<\n]*))?', line)

        if nick_match:
            if current_member.get('nick'):
                members.append(current_member)
            current_member = {
                'clan_id': clan_id,
                'nick': nick_match.group(1).strip(),
                'level': int(nick_match.group(2)),
                'game_rank': '',
                'profession': '',
                'profession_level': 0,
                'clan_role': '',
                'join_date': '',
                'trial_until': '',
            }
            prof_part = nick_match.group(3) or ''
            prof_match = re.search(r'([А-Яа-яЁё]+):\s*(\d+)', prof_part)
            if prof_match:
                current_member['profession'] = prof_match.group(1).strip()
                current_member['profession_level'] = int(prof_match.group(2))

            rank_match = re.search(r'(Герой|Властелин боя|Вершитель|Магистр войны|Повелитель|Полководец|Легендарный завоеватель|Военный эксперт|Мастер войны|Элитный воин|Гладиатор|Чемпион|Избранник богов|Триумфатор|Высший магистр)', line)
            if rank_match:
                current_member['game_rank'] = rank_match.group(1)

            continue

        role_match = re.search(r'(Глава Ордена|Зам\. Главы|Совесть|Рыцарь Ордена|Леди Ордена|ГардеМаринкА|Фея на метле|Лентяй|Пельмешка|Dead\'ok|Воевода|9-ть жЫзней\)|УлитЫчка\)|РудольФ|Сосиска)', line)
        if role_match and current_member.get('nick'):
            current_member['clan_role'] = role_match.group(1)
            continue

        if current_member.get('nick'):
            join_match = re.search(r'принят в клан\s+(\d{2}\.\d{2}\.\d{4})', line)
            if join_match:
                current_member['join_date'] = join_match.group(1)
                continue

            trial_match = re.search(r'Исп\. срок до\s+(\d{2}\.\d{2}\.\d{4})', line)
            if trial_match:
                current_member['trial_until'] = trial_match.group(1)
                continue

    if current_member.get('nick'):
        members.append(current_member)

    return members
