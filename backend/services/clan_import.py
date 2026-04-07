import re
from utils.formatters import clean_html


def parse_clan_members_from_text(text, clan_id):
    members = []
    current_member = {}

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        nick_match = re.search(r'(?:Герой|Властелин боя|Вершитель|Магистр войны|Повелитель|Полководец|Легендарный завоеватель|Военный эксперт|Мастер войны|Элитный воин|Гладиатор|Чемпион|Избранник богов|Триумфатор|Высший магистр)\s+([^\[]+)\[(\d+)\](?:([^<\n]*))?', line)

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
