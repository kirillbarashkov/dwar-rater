import re
from urllib.parse import urlparse
import requests
from shared.utils.formatters import clean_html
from shared.services.data_logger import data_logger


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

    logo_match = re.search(r'<img[^>]+src="([^"]*(?:clan_logos|data/clans/)[^"]+)"', html)
    if logo_match:
        logo_path = logo_match.group(1)
        result['logo_url'] = logo_path
        if '/m/' in logo_path:
            result['logo_big'] = logo_path.replace('/m/', '/l/').replace('_m.', '_l.')
            result['logo_small'] = logo_path.replace('/m/', '/s/').replace('_m.', '_s.')
        else:
            result['logo_big'] = logo_path
            result['logo_small'] = logo_path
    else:
        result['logo_url'] = ''
        result['logo_big'] = ''
        result['logo_small'] = ''

    leader_pos = html.find('>Глава</td>')
    if leader_pos > 0:
        section = html[leader_pos:leader_pos+2500]
        nick_match = re.search(r'<b>([^<]+)&nbsp;\[(\d+)\]</b>', section)
        if nick_match:
            result['leader_nick'] = clean_html(nick_match.group(1)).replace('&nbsp;', ' ').strip()
            result['leader_rank'] = nick_match.group(2).strip()
        leader_rank_match = re.search(r'title="([^"]+)"[^>]*src="[^"]*rank\d+\.gif"', section)
        if leader_rank_match:
            result['leader_rank_title'] = leader_rank_match.group(1)

    status_pos = html.find('>Статус</td>')
    if status_pos > 0:
        section = html[status_pos:status_pos+2500]
        rank_match = re.search(r'title="([^"]+)"[^>]*src="[^"]*rank\d+\.gif"', section)
        if rank_match:
            result['clan_rank'] = rank_match.group(1).strip()
        level_match = re.search(r'\[(\d+)\]', section)
        if level_match:
            result['clan_level'] = int(level_match.group(1))
        step_match = re.search(r'title="([^"]+)"[^>]*src="[^"]*/steps/(\d+)\.png"', section)
        if step_match:
            result['step'] = int(step_match.group(2))

    talents_match = re.search(r'Развитие талантов клана:\s*(\d+)', html)
    if talents_match:
        result['talents'] = int(talents_match.group(1))

    result.setdefault('current_players', 0)
    result.setdefault('total_players', 0)

    return result


def parse_clan_members(html, clan_id):
    members = []
    current_member = {}
    lines = html.split('\n')

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        nick_match = re.search(r'(?:Герой.Властелин боя.Вершитель.Магистр войны.Повелитель.Полководец.Легендарный завоеватель.Военный эксперт.Мастер войны.Элитный воин.Гладиатор.Чемпион.Избранник богов.Триумфатор.Высший магистр)\s+([^\[]+)\[(\d+)\](?:([^<\n]*))?', line)

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

            rank_match = re.search(r'(Герой.Властелин боя.Вершитель.Магистр войны.Повелитель.Полководец.Легендарный завоеватель.Военный эксперт.Мастер войны.Элитный воин.Гладиатор.Чемпион.Избранник богов.Триумфатор.Высший магистр)', line)
            if rank_match:
                current_member['game_rank'] = rank_match.group(1)

            continue

        role_match = re.search(r'(Глава Ордена|Зам\. Главы.|Совесть.|Рыцарь Ордена.|Леди Ордена.|ГардеМаринкА.|Фея на метле.|Лентяй.|Пельмешка.|Dead.ok.|Воевода.|9-ть жЫзней.).|УлитЫчка.).|РудольФ.|Сосиска.)', line)
        if role_match and current_member.get('nick'):
            current_member['clan_role'] = role_match.group(1)
            continue

        if current_member.get('nick'):
            pos = html.find('принят в клан')
            if pos >= 0:
                segment = html[pos:pos+40]
                join_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', segment)
                if join_match:
                    current_member['join_date'] = join_match.group(1)

            trial_match = re.search(r'Исп\. срок до\s+(\d{2}\.\d{2}\.\d{4})', line)
            if trial_match:
                current_member['trial_until'] = trial_match.group(1)

    if current_member.get('nick'):
        members.append(current_member)

    return members


def fetch_clan_treasury_report(session=None, page=0, filters=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }
    
    url = f'https://w1.dwar.ru/clan_management.php?f=1&mode=clancell&submode=report&page={page}'
    data_logger.info(f'[PARSER] Fetching treasury report page={page}, url={url}')
    
    if session is None:
        session = requests.Session()
    
    resp = session.get(url, headers=headers, timeout=15)
    resp.encoding = 'utf-8'
    data_logger.info(f'[PARSER] Received response: status={resp.status_code}, content_length={len(resp.text)}')
    return resp.text, session


def parse_clan_treasury_operations(html):
    operations = []
    skipped_rows = []
    
    rows = re.findall(r'<tr(?:\s+class="bg_l")?>(.*?)</tr>', html, re.DOTALL)
    data_logger.info(f'[PARSER] Found {len(rows)} table rows in HTML')
    
    for i, row_html in enumerate(rows):
        cells = re.findall(r'<td[^>]*class="brd-all p6h"[^>]*>(.*?)</td>', row_html, re.DOTALL)
        
        if len(cells) < 5:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
        
        if len(cells) < 5:
            skipped_rows.append({'row': i, 'reason': f'cells={len(cells)} < 5', 'cells_preview': str(cells[:3])})
            continue
        
        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})', cells[0])
        if not date_match:
            skipped_rows.append({'row': i, 'reason': 'no date match', 'cell0': cells[0][:100]})
            continue
        
        date = date_match.group(1)
        
        nick_match = re.search(r'userToTag\(\'([^)]+)\'\)', cells[1])
        if not nick_match:
            nick_match = re.search(r'>([^<]+)\s*\[(\d+)\]</a>', cells[1])
        if not nick_match:
            art_match = re.search(r'"title":"([^"]+)"', cells[1])
            if art_match:
                nick = art_match.group(1)
            else:
                nick = clean_html(cells[1]).strip()
                if not nick:
                    skipped_rows.append({'row': i, 'reason': 'no nick match', 'cell1': cells[1][:100]})
                    continue
        else:
            nick = nick_match.group(1)
        
        operation_type = clean_html(cells[2]).strip()
        
        obj_match = re.search(r'<a[^>]*>([^<]+)</a>', cells[3])
        if not obj_match:
            obj_match = re.search(r'<b>([^<]+)</b>', cells[3])
        if not obj_match:
            obj_match = re.search(r'"title":"([^"]+)"', cells[3])
        obj_name = obj_match.group(1).strip() if obj_match else clean_html(cells[3]).strip()
        
        quantity_match = re.search(r'color:\s*(?:green|red)[^>]*>.*?(\d+)', cells[4])
        if not quantity_match:
            quantity_match = re.search(r'color:(?:green|red)[^>]*>.*?(\d+)', cells[4])
        
        if not quantity_match:
            clean_qty = clean_html(cells[4]).strip().replace('&nbsp;', '').strip()
            qty_num_match = re.search(r'(-?\d+)', clean_qty)
            if qty_num_match:
                quantity = int(qty_num_match.group(1))
            else:
                skipped_rows.append({'row': i, 'reason': 'no quantity match', 'cell4': clean_qty[:50]})
                continue
        else:
            quantity = int(quantity_match.group(1))
            if 'red' in cells[4]:
                quantity = -quantity
        
        operations.append({
            'date': date,
            'nick': nick,
            'operation_type': operation_type,
            'object_name': obj_name,
            'quantity': quantity,
        })
    
    data_logger.info(f'[PARSER] Parsed {len(operations)} operations, skipped {len(skipped_rows)} rows')
    if skipped_rows:
        data_logger.warning(f'[PARSER] Skipped {len(skipped_rows)} rows: {skipped_rows[:10]}')
    return operations


def _parse_date_to_comparable(date_str):
    """Convert 'DD.MM.YYYY HH:MM' to comparable string 'YYYYMMDDHHMM'."""
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})', date_str)
    if not m:
        return ''
    return f'{m.group(3)}{m.group(2)}{m.group(1)}{m.group(4)}{m.group(5)}'


def _date_str_to_comparable(date_str):
    """Convert 'DD.MM.YYYY' to comparable string 'YYYYMMDD'."""
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
    if not m:
        return ''
    return f'{m.group(3)}{m.group(2)}{m.group(1)}'


def is_login_redirect(html):
    """Check if HTML response is a login redirect page.

    Looks for the specific redirect script pattern, not just presence of keywords
    (which can appear in normal page links like /info/library/index.php).
    """
    if 'single_top_redirect' in html:
        return True
    if len(html) < 500 and ('login' in html.lower() or 'auth' in html.lower()):
        return True
    return False


def parse_total_pages(html):
    """Extract total page count from pagination HTML."""
    # Pattern: <a ...>N</a> at the end of pagination
    page_links = re.findall(r'<a[^>]*>(\d+)</a>', html)
    if page_links:
        return max(int(p) for p in page_links) + 1  # pages are 0-indexed
    return None


def fetch_all_pages_streaming(session, cutoff_date_str='01.01.2025', max_pages=500):
    """
    Generator that yields SSE-compatible progress events while fetching pages.

    Yields tuples: (event_type, data_dict)
    event_type: 'counting' | 'progress' | 'done' | 'error'
    """
    import time

    cutoff_comparable = _date_str_to_comparable(cutoff_date_str)
    all_operations = []
    start_time = time.time()
    total_pages = None

    # Step 1: Fetch page 0 to count total pages
    try:
        html, session = fetch_clan_treasury_report(session=session, page=0)
    except Exception as e:
        yield ('error', {'reason': 'fetch_error', 'message': f'Ошибка загрузки: {str(e)}'})
        return

    if is_login_redirect(html):
        yield ('error', {'reason': 'session_expired', 'message': 'Сессия истекла, обновите cookies'})
        return

    total_pages = parse_total_pages(html)
    if total_pages is None or total_pages > max_pages:
        total_pages = max_pages

    yield ('counting', {'total_pages': total_pages, 'cutoff_date': cutoff_date_str})

    # Step 2: Parse page 0 operations
    page_ops = parse_clan_treasury_operations(html)
    all_operations.extend(page_ops)

    yield ('progress', {
        'page': 0,
        'total_pages': total_pages,
        'ops_on_page': len(page_ops),
        'total_ops': len(all_operations),
        'elapsed': round(time.time() - start_time, 1),
    })

    # Step 3: Fetch remaining pages
    for page in range(1, total_pages):
        try:
            html, session = fetch_clan_treasury_report(session=session, page=page)
        except Exception as e:
            yield ('error', {'reason': 'fetch_error', 'message': f'Ошибка на странице {page}: {str(e)}'})
            return

        if is_login_redirect(html):
            yield ('error', {'reason': 'session_expired', 'message': 'Сессия истекла, обновите cookies'})
            return

        page_ops = parse_clan_treasury_operations(html)

        earliest_on_page = min((_parse_date_to_comparable(op['date']) for op in page_ops), default='')
        if earliest_on_page and earliest_on_page < cutoff_comparable:
            filtered = [op for op in page_ops if _parse_date_to_comparable(op['date']) >= cutoff_comparable]
            all_operations.extend(filtered)
            yield ('progress', {
                'page': page,
                'total_pages': total_pages,
                'ops_on_page': len(filtered),
                'total_ops': len(all_operations),
                'elapsed': round(time.time() - start_time, 1),
                'cutoff_reached': True,
            })
            break

        all_operations.extend(page_ops)
        yield ('progress', {
            'page': page,
            'total_pages': total_pages,
            'ops_on_page': len(page_ops),
            'total_ops': len(all_operations),
            'elapsed': round(time.time() - start_time, 1),
        })

    elapsed = round(time.time() - start_time, 1)
    yield ('done', {
        'total_ops': len(all_operations),
        'pages_fetched': min(total_pages, max_pages),
        'elapsed': elapsed,
        'operations': all_operations,
    })


def fetch_all_pages_until_date(session, cutoff_date_str='01.01.2025', max_pages=500):
    """
    Fetches pages 0..n from clan_management.php until:
    - Найдена операция с датой < cutoff_date
    - Страница пустая или содержит редирект на login
    - Достигнут max_pages

    Returns: dict with keys:
        success (bool), operations (list), pages_fetched (int),
        stopped_reason (str), error (str or None)
    """
    all_operations = []
    cutoff_comparable = _date_str_to_comparable(cutoff_date_str)
    pages_fetched = 0
    stopped_reason = None

    data_logger.info(f'[PARSER] fetch_all_pages: cutoff={cutoff_date_str}, max_pages={max_pages}')

    for page in range(max_pages):
        try:
            html, session = fetch_clan_treasury_report(session=session, page=page)
        except Exception as e:
            data_logger.error(f'[PARSER] fetch_all_pages: error on page {page}: {e}')
            return {
                'success': False,
                'operations': all_operations,
                'pages_fetched': pages_fetched,
                'stopped_reason': 'fetch_error',
                'error': str(e),
            }

        if is_login_redirect(html):
            data_logger.warning(f'[PARSER] fetch_all_pages: login redirect on page {page}')
            return {
                'success': False,
                'operations': all_operations,
                'pages_fetched': pages_fetched,
                'stopped_reason': 'session_expired',
                'error': 'Сессия истекла, обновите cookies',
            }

        page_ops = parse_clan_treasury_operations(html)
        pages_fetched += 1

        if not page_ops:
            data_logger.info(f'[PARSER] fetch_all_pages: no operations on page {page}, stopping')
            stopped_reason = 'no_more_data'
            break

        earliest_on_page = min(_parse_date_to_comparable(op['date']) for op in page_ops)
        if earliest_on_page and earliest_on_page < cutoff_comparable:
            filtered = [op for op in page_ops if _parse_date_to_comparable(op['date']) >= cutoff_comparable]
            all_operations.extend(filtered)
            data_logger.info(f'[PARSER] fetch_all_pages: cutoff reached on page {page}, kept {len(filtered)}/{len(page_ops)} ops')
            stopped_reason = 'cutoff_reached'
            break

        all_operations.extend(page_ops)
        data_logger.info(f'[PARSER] fetch_all_pages: page {page} done, {len(page_ops)} ops, total={len(all_operations)}')

    if stopped_reason is None:
        stopped_reason = 'max_pages_reached'

    data_logger.info(f'[PARSER] fetch_all_pages: finished. pages={pages_fetched}, ops={len(all_operations)}, reason={stopped_reason}')

    return {
        'success': True,
        'operations': all_operations,
        'pages_fetched': pages_fetched,
        'stopped_reason': stopped_reason,
        'error': None,
    }


# =============================================================================
# Clan membership parsing — management page and history
# =============================================================================

def fetch_clan_management_page(session, clan_id):
    """Fetch clan management page with current member list."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }
    url = f'https://w1.dwar.ru/clan_management.php?f=1&mode=management'
    data_logger.info(f'[PARSER] Fetching management page, url={url}')
    resp = session.get(url, headers=headers, timeout=15)
    resp.encoding = 'utf-8'
    data_logger.info(f'[PARSER] Management response: status={resp.status_code}, length={len(resp.text)}')
    return resp.text


def parse_clan_members_from_management(html, clan_id):
    """Parse current clan members from management page HTML.

    Returns: list[dict] with keys: nick, level, game_rank, profession,
             profession_level, clan_role, join_date, trial_until
    """
    members = []
    current_member = {}
    lines = html.split('\n')

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        nick_match = re.search(
            r'(?:Герой|Властелин боя|Вершитель|Магистр войны|Повелитель|Полководец|Легендарный завоеватель|Военный эксперт|Мастер войны|Элитный воин|Гладиатор|Чемпион|Избранник богов|Триумфатор|Высший магистр)\s+([^\[]+)\[(\d+)\](?:([^<\n]*))?',
            line
        )

        if nick_match:
            if current_member.get('nick'):
                members.append(current_member)

            raw_nick = nick_match.group(1).strip()
            # Try to extract nick from userToTag('...') first
            utag_match = re.search(r"userToTag\('([^']+)'\)", raw_nick)
            if utag_match:
                nick = utag_match.group(1)
            else:
                # Fallback: strip HTML tags
                nick = clean_html(raw_nick).strip()
                # Remove trailing non-breaking spaces and artifacts
                nick = re.sub(r'[\s\xa0]+$', '', nick)
                nick = re.sub(r'^[\s\xa0]+', '', nick)

            current_member = {
                'clan_id': clan_id,
                'nick': nick,
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

            rank_match = re.search(
                r'(Герой|Властелин боя|Вершитель|Магистр войны|Повелитель|Полководец|Легендарный завоеватель|Военный эксперт|Мастер войны|Элитный воин|Гладиатор|Чемпион|Избранник богов|Триумфатор|Высший магистр)',
                line
            )
            if rank_match:
                current_member['game_rank'] = rank_match.group(1)

            continue

        role_match = re.search(
            r'(Глава Ордена|Зам\. Главы|Совесть|Рыцарь Ордена|Леди Ордена|ГардеМаринкА|Фея на метле|Лентяй|Пельмешка|Dead\'ok|Воевода|9-ть жЫзней\)|УлитЫчка\)|РудольФ|Сосиска)',
            line
        )
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

    data_logger.info(f'[PARSER] Parsed {len(members)} members from management page')
    return members


def fetch_clan_history_page(session, clan_id, page=0):
    """Fetch clan history page (join/leave events)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }
    url = f'https://w1.dwar.ru/clan_info.php?clan_id={clan_id}&mode=history&page={page}'
    data_logger.info(f'[PARSER] Fetching history page={page}, url={url}')
    resp = session.get(url, headers=headers, timeout=15)
    resp.encoding = 'utf-8'
    data_logger.info(f'[PARSER] History response: status={resp.status_code}, length={len(resp.text)}')
    return resp.text


def parse_clan_history_events(html, clan_id):
    """Parse join/leave events from clan history page.

    Returns: list[dict] with keys: nick, event_type, event_date, leave_reason
    """
    events = []

    rows = re.findall(r'<tr(?:\s+class="[^"]*")?\s*>(.*?)</tr>', html, re.DOTALL)
    data_logger.info(f'[PARSER] Found {len(rows)} rows in history page')

    for row_html in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
        if len(cells) < 2:
            continue

        row_text = ' '.join(clean_html(cell) for cell in cells)

        nick_match = re.search(r'userToTag\(\'([^\']+)\'\)', row_html)
        if not nick_match:
            nick_match = re.search(r'>\s*([A-Za-zА-Яа-яЁё0-9_\-\'\.]+?)\s*\[\d+\]\s*<', row_html)
        if not nick_match:
            nick_match = re.search(r'(?:принят|покинул|исключен)[\s\w]*?([A-Za-zА-Яа-яЁё0-9_\-\'\.]+)', row_text)
        if not nick_match:
            continue

        nick = nick_match.group(1).strip()
        if not nick:
            continue

        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', row_text)
        if not date_match:
            continue
        event_date = date_match.group(1)

        if 'принят в клан' in row_text or 'принят' in row_text:
            event_type = 'joined'
            leave_reason = ''
        elif 'исключен' in row_text or 'исключён' in row_text:
            event_type = 'left'
            leave_reason = 'Исключен'
        elif 'покинул' in row_text:
            event_type = 'left'
            leave_reason = 'Вышел сам'
        else:
            continue

        events.append({
            'nick': nick,
            'event_type': event_type,
            'event_date': event_date,
            'leave_reason': leave_reason,
        })

    data_logger.info(f'[PARSER] Parsed {len(events)} events from history page')
    return events


def fetch_all_history_pages_streaming(session, clan_id, cutoff_date_str='01.01.2025', max_pages=100):
    """
    Generator that yields SSE-compatible progress events while fetching history pages.

    Yields tuples: (event_type, data_dict)
    event_type: 'counting' | 'progress' | 'done' | 'error'
    """
    import time

    cutoff_comparable = _date_str_to_comparable(cutoff_date_str)
    all_events = []
    start_time = time.time()
    total_pages = None

    try:
        html = fetch_clan_history_page(session, clan_id, page=0)
    except Exception as e:
        yield ('error', {'reason': 'fetch_error', 'message': f'Ошибка загрузки: {str(e)}'})
        return

    if is_login_redirect(html):
        yield ('error', {'reason': 'session_expired', 'message': 'Сессия истекла, обновите cookies'})
        return

    total_pages = parse_total_pages(html)
    if total_pages is None or total_pages > max_pages:
        total_pages = max_pages

    yield ('counting', {'total_pages': total_pages, 'cutoff_date': cutoff_date_str})

    page_events = parse_clan_history_events(html, clan_id)
    all_events.extend(page_events)

    yield ('progress', {
        'page': 0,
        'total_pages': total_pages,
        'events_on_page': len(page_events),
        'total_events': len(all_events),
        'elapsed': round(time.time() - start_time, 1),
    })

    for page in range(1, total_pages):
        try:
            html = fetch_clan_history_page(session, clan_id, page=page)
        except Exception as e:
            yield ('error', {'reason': 'fetch_error', 'message': f'Ошибка на странице {page}: {str(e)}'})
            return

        if is_login_redirect(html):
            yield ('error', {'reason': 'session_expired', 'message': 'Сессия истекла, обновите cookies'})
            return

        page_events = parse_clan_history_events(html, clan_id)

        earliest_on_page = min(
            (_date_str_to_comparable(ev['event_date']) for ev in page_events),
            default=''
        )
        if earliest_on_page and earliest_on_page < cutoff_comparable:
            filtered = [
                ev for ev in page_events
                if _date_str_to_comparable(ev['event_date']) >= cutoff_comparable
            ]
            all_events.extend(filtered)
            yield ('progress', {
                'page': page,
                'total_pages': total_pages,
                'events_on_page': len(filtered),
                'total_events': len(all_events),
                'elapsed': round(time.time() - start_time, 1),
                'cutoff_reached': True,
            })
            break

        all_events.extend(page_events)
        yield ('progress', {
            'page': page,
            'total_pages': total_pages,
            'events_on_page': len(page_events),
            'total_events': len(all_events),
            'elapsed': round(time.time() - start_time, 1),
        })

    elapsed = round(time.time() - start_time, 1)
    yield ('done', {
        'total_events': len(all_events),
        'pages_fetched': min(total_pages, max_pages),
        'elapsed': elapsed,
        'events': all_events,
    })
