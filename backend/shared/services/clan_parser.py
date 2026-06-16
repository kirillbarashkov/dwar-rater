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


def _date_str_to_comparable_with_time(date_str):
    """Convert 'DD.MM.YYYY' or 'DD.MM.YYYY HH:MM' to comparable string 'YYYYMMDDHHMM'."""
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})', date_str)
    if m:
        return f'{m.group(3)}{m.group(2)}{m.group(1)}{m.group(4)}{m.group(5)}'
    m = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
    if m:
        return f'{m.group(3)}{m.group(2)}{m.group(1)}2359'
    return ''


def estimate_pages_in_range(session, start_date_str, end_date_str, max_pages=500):
    """
    Binary search to estimate page count in a date range without downloading all pages.

    Returns dict with:
      - start_page: first page with data >= start_date (newer boundary)
      - end_page: last page with data <= end_date (older boundary)
      - estimated_pages: number of pages in range
      - total_pages: total pages available
      - sample_dates: {page_0_latest, page_0_earliest, start_page_latest, end_page_earliest}
    """
    # Fetch page 0 to get total pages and date range
    html, session = fetch_clan_treasury_report(session=session, page=0)
    if is_login_redirect(html):
        return {'error': 'session_expired', 'message': 'Сессия истекла'}

    total_pages = parse_total_pages(html)
    if total_pages is None or total_pages > max_pages:
        total_pages = max_pages

    page_ops = parse_clan_treasury_operations(html)
    if not page_ops:
        return {
            'start_page': 0,
            'end_page': 0,
            'estimated_pages': 0,
            'total_pages': total_pages,
            'sample_dates': {},
        }

    start_comparable = _date_str_to_comparable_with_time(start_date_str)
    end_comparable = _date_str_to_comparable_with_time(end_date_str)

    # Check if page 0 has any data in range
    latest_on_page_0 = max((_parse_date_to_comparable(op['date']) for op in page_ops), default='')
    earliest_on_page_0 = min((_parse_date_to_comparable(op['date']) for op in page_ops), default='')

    # If even the newest op is older than start_date → no data in range
    if latest_on_page_0 and latest_on_page_0 < start_comparable:
        return {
            'start_page': 0,
            'end_page': 0,
            'estimated_pages': 0,
            'total_pages': total_pages,
            'sample_dates': {
                'page_0_latest': latest_on_page_0,
                'page_0_earliest': earliest_on_page_0,
            },
        }

    # Binary search: find the page where latest op <= end_date (upper boundary)
    # Pages go newest → oldest, so we search for the first page where ALL ops are <= end_date
    def find_end_boundary(low, high):
        """Find first page where latest_on_page <= end_comparable."""
        result = high
        while low <= high:
            mid = (low + high) // 2
            try:
                mid_html, _ = fetch_clan_treasury_report(session=session, page=mid)
                if is_login_redirect(mid_html):
                    return result
                mid_ops = parse_clan_treasury_operations(mid_html)
                if not mid_ops:
                    high = mid - 1
                    continue
                mid_latest = max((_parse_date_to_comparable(op['date']) for op in mid_ops), default='')
                if mid_latest and mid_latest <= end_comparable:
                    result = mid
                    high = mid - 1
                else:
                    low = mid + 1
            except Exception:
                break
        return result

    # Binary search: find the page where earliest op >= start_date (lower boundary)
    def find_start_boundary(low, high):
        """Find last page where earliest_on_page >= start_comparable."""
        result = low
        while low <= high:
            mid = (low + high) // 2
            try:
                mid_html, _ = fetch_clan_treasury_report(session=session, page=mid)
                if is_login_redirect(mid_html):
                    return result
                mid_ops = parse_clan_treasury_operations(mid_html)
                if not mid_ops:
                    low = mid + 1
                    continue
                mid_earliest = min((_parse_date_to_comparable(op['date']) for op in mid_ops), default='')
                if mid_earliest and mid_earliest >= start_comparable:
                    result = mid
                    low = mid + 1
                else:
                    high = mid - 1
            except Exception:
                break
        return result

    # Find boundaries
    end_page = find_end_boundary(0, total_pages - 1)
    start_page = find_start_boundary(end_page, total_pages - 1)

    estimated_pages = start_page - end_page + 1

    # Get sample dates from boundary pages
    sample_dates = {
        'page_0_latest': latest_on_page_0,
        'page_0_earliest': earliest_on_page_0,
    }

    try:
        end_html, _ = fetch_clan_treasury_report(session=session, page=end_page)
        end_ops = parse_clan_treasury_operations(end_html)
        if end_ops:
            sample_dates['end_page_latest'] = max((_parse_date_to_comparable(op['date']) for op in end_ops), default='')
            sample_dates['end_page_earliest'] = min((_parse_date_to_comparable(op['date']) for op in end_ops), default='')
    except Exception:
        pass

    try:
        start_html, _ = fetch_clan_treasury_report(session=session, page=start_page)
        start_ops = parse_clan_treasury_operations(start_html)
        if start_ops:
            sample_dates['start_page_latest'] = max((_parse_date_to_comparable(op['date']) for op in start_ops), default='')
            sample_dates['start_page_earliest'] = min((_parse_date_to_comparable(op['date']) for op in start_ops), default='')
    except Exception:
        pass

    return {
        'start_page': end_page,
        'end_page': start_page,
        'estimated_pages': max(0, estimated_pages),
        'total_pages': total_pages,
        'sample_dates': sample_dates,
    }


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


def fetch_all_pages_streaming(session, cutoff_date_str='01.01.2025', end_date_str=None, max_pages=500, start_page=0, end_page=None, total_pages_override=None):
    """
    Generator that yields SSE-compatible progress events while fetching pages.
    Downloads pages starting from start_page (default 0 = newest) and stops when:
    - All operations on a page are older than cutoff_date_str
    - All operations on a page are older than end_date_str (if provided)
    - Page exceeds end_page (if provided, for optimized range imports)

    If end_date_str is provided, operations newer than end_date_str are excluded.

    Yields tuples: (event_type, data_dict)
    event_type: 'counting' | 'progress' | 'done' | 'error'
    """
    import time

    cutoff_comparable = _date_str_to_comparable(cutoff_date_str)
    end_comparable = _date_str_to_comparable_with_time(end_date_str) if end_date_str else None
    all_operations = []
    start_time = time.time()
    total_pages = total_pages_override

    # If we have a pre-computed start_page, skip directly to it
    if start_page > 0 and total_pages is not None:
        data_logger.info(f'[PARSER] Optimized range import: pages {start_page}-{end_page or "end"}')
        yield ('counting', {'total_pages': total_pages, 'cutoff_date': cutoff_date_str, 'end_date': end_date_str, 'start_page': start_page, 'end_page': end_page})
    else:
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

        yield ('counting', {'total_pages': total_pages, 'cutoff_date': cutoff_date_str, 'end_date': end_date_str})

        # Step 2: Parse page 0 operations, filter by cutoff and end_date
        page_ops = parse_clan_treasury_operations(html)
        filtered_ops = []
        for op in page_ops:
            op_comparable = _parse_date_to_comparable(op['date'])
            if op_comparable >= cutoff_comparable:
                if end_comparable is None or op_comparable <= end_comparable:
                    filtered_ops.append(op)
        all_operations.extend(filtered_ops)

        yield ('progress', {
            'page': 0,
            'total_pages': total_pages,
            'ops_on_page': len(filtered_ops),
            'total_ops': len(all_operations),
            'elapsed': round(time.time() - start_time, 1),
        })

        # Check if page 0 already has all operations older than cutoff
        earliest_on_page_0 = min((_parse_date_to_comparable(op['date']) for op in page_ops), default='')
        if earliest_on_page_0 and earliest_on_page_0 < cutoff_comparable and not filtered_ops:
            data_logger.info(f'[PARSER] Page 0 already older than cutoff {cutoff_date_str}, stopping')
            elapsed = round(time.time() - start_time, 1)
            yield ('done', {
                'total_ops': len(all_operations),
                'pages_fetched': 1,
                'elapsed': elapsed,
                'operations': all_operations,
            })
            return

    # Step 3: Fetch pages from start_page (or 1) to end_page (or total_pages)
    loop_start = start_page if start_page > 0 else 1
    loop_end = end_page if end_page is not None else total_pages
    pages_fetched = len(all_operations) > 0 and start_page == 0

    for page in range(loop_start, loop_end):
        try:
            html, session = fetch_clan_treasury_report(session=session, page=page)
        except Exception as e:
            yield ('error', {'reason': 'fetch_error', 'message': f'Ошибка на странице {page}: {str(e)}'})
            return

        if is_login_redirect(html):
            yield ('error', {'reason': 'session_expired', 'message': 'Сессия истекла, обновите cookies'})
            return

        page_ops = parse_clan_treasury_operations(html)
        if not page_ops:
            break

        earliest_on_page = min((_parse_date_to_comparable(op['date']) for op in page_ops), default='')
        latest_on_page = max((_parse_date_to_comparable(op['date']) for op in page_ops), default='')

        # EARLY EXIT: If the freshest op on this page is already older than end_date,
        # we've scrolled past the entire target range. Stop immediately.
        if end_comparable and latest_on_page and latest_on_page < end_comparable:
            data_logger.info(f'[PARSER] Page {page}: latest op {latest_on_page} < end_date {end_comparable}, stopping early')
            break

        # Early exit: all ops on this page (and all subsequent pages) are older than cutoff
        if latest_on_page and latest_on_page < cutoff_comparable:
            data_logger.info(f'[PARSER] Page {page}: latest op {latest_on_page} < cutoff {cutoff_comparable}, stopping early')
            break

        if earliest_on_page and earliest_on_page < cutoff_comparable:
            filtered = []
            for op in page_ops:
                op_comparable = _parse_date_to_comparable(op['date'])
                if op_comparable >= cutoff_comparable:
                    if end_comparable is None or op_comparable <= end_comparable:
                        filtered.append(op)
            all_operations.extend(filtered)
            pages_fetched += 1
            yield ('progress', {
                'page': page,
                'total_pages': total_pages,
                'ops_on_page': len(filtered),
                'total_ops': len(all_operations),
                'elapsed': round(time.time() - start_time, 1),
                'cutoff_reached': True,
            })
            break

        # Filter by end_date even when not at cutoff
        if end_comparable is not None:
            filtered = [op for op in page_ops if _parse_date_to_comparable(op['date']) <= end_comparable]
            all_operations.extend(filtered)
            pages_fetched += 1
            yield ('progress', {
                'page': page,
                'total_pages': total_pages,
                'ops_on_page': len(filtered),
                'total_ops': len(all_operations),
                'elapsed': round(time.time() - start_time, 1),
            })
        else:
            all_operations.extend(page_ops)
            pages_fetched += 1
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
        'pages_fetched': pages_fetched,
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

    Management page has a different structure than clan_info.php:
    Each member is in a <tr> with cells:
      Cell 0: nick [level] + rank img (title="Rank Name")
      Cell 1: clan role
      Cell 4: join date or trial period

    Returns: list[dict] with keys: nick, level, game_rank, profession,
             profession_level, clan_role, join_date, trial_until
    """
    members = []

    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

    for row_html in rows:
        if 'userToTag' not in row_html:
            continue

        cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
        if len(cells) < 5:
            continue

        cell0 = cells[0]

        # Extract nick from userToTag('nick')
        nick_match = re.search(r"userToTag\('([^']+)'\)", cell0)
        if not nick_match:
            continue
        nick = nick_match.group(1).strip()
        if not nick:
            continue

        # Extract level from nick&nbsp;[level]
        level_match = re.search(r'\[(\d+)\]', cell0)
        level = int(level_match.group(1)) if level_match else 1

        # Extract game_rank from rank img title
        rank_match = re.search(r'/images/ranks/[^"]*"[^>]*title="([^"]+)"', cell0)
        if not rank_match:
            rank_match = re.search(r'title="([^"]+)"[^>]*align="absmiddle"', cell0)
        game_rank = rank_match.group(1) if rank_match else ''

        # Extract clan role from cell 1
        clan_role = clean_html(cells[1]).strip() if len(cells) > 1 else ''

        # Extract join_date / trial_until from cell 4
        # Replace <br/> with space before stripping HTML — dwar.ru splits text across <br/>
        cell4_raw = cells[4] if len(cells) > 4 else ''
        cell4_raw = re.sub(r'<br\s*/?>', ' ', cell4_raw)
        cell4 = clean_html(cell4_raw)
        join_date = ''
        trial_until = ''

        join_match = re.search(r'принят в клан\s+(\d{2}\.\d{2}\.\d{4})', cell4)
        if join_match:
            join_date = join_match.group(1)

        trial_match = re.search(r'Исп\. срок до\s+(\d{2}\.\d{2}\.\d{4})', cell4)
        if trial_match:
            trial_until = trial_match.group(1)

        members.append({
            'clan_id': clan_id,
            'nick': nick,
            'level': level,
            'game_rank': game_rank,
            'profession': '',
            'profession_level': 0,
            'clan_role': clan_role,
            'join_date': join_date,
            'trial_until': trial_until,
        })

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


def parse_level_change_events(html):
    """
    Parse level change events from clan_info.php history page.
    Pattern: "Nick [level] достиг N-го уровня."
    Returns list of dicts: {nick, new_level, event_date}
    """
    events = []
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) < 2:
            continue

        # Strip HTML and &nbsp;
        clean_cells = []
        for c in cells:
            text = re.sub(r'<[^>]+>', '', c)
            text = text.replace('&nbsp;', ' ')
            text = text.strip()
            clean_cells.append(text)

        if not clean_cells[0]:
            continue

        date_match = re.match(r'(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})', clean_cells[0])
        if not date_match:
            continue

        event_date = date_match.group(1)
        full_text = ' '.join(clean_cells)

        # Pattern: "Nick [current_level] достиг N-го уровня."
        level_match = re.search(r'(.+?)\s*\[(\d+)\]\s*достиг\s+(\d+)-го\s+уровня', full_text)
        if not level_match:
            level_match = re.search(r'(.+?)\s*\[(\d+)\]\s*достиг\s+(\d+)-й\s+уровень', full_text)
        if not level_match:
            level_match = re.search(r'(.+?)\s*\[(\d+)\]\s*достиг\s+(\d+)\s+уровень', full_text)

        if level_match:
            nick = level_match.group(1).strip()
            current_level = int(level_match.group(2))
            new_level = int(level_match.group(3))
            old_level = new_level - 1

            events.append({
                'nick': nick,
                'old_level': old_level,
                'new_level': new_level,
                'event_date': event_date,
            })

    data_logger.info(f'[PARSER] Parsed {len(events)} level change events')
    return events


def fetch_level_history_page(session, clan_id=2315, filter_type=5, page=0):
    """Fetch clan history page with event type filter via GET URL."""
    url = f'https://w1.dwar.ru/clan_info.php?clan_id={clan_id}&mode=history&filter%5Btype%5D={filter_type}&filter%5Bmember%5D=&filter%5Bstart_date%5D=&filter%5Bend_date%5D=&page={page}'
    resp = session.get(url, timeout=15)
    return resp.text


def fetch_level_events_streaming(session, clan_id=2315, max_pages=500):
    """
    Generator that yields SSE-compatible progress events while fetching level change events.
    """
    import time
    all_events = []
    start_time = time.time()
    total_pages = None

    # Step 1: Fetch page 0 to count total pages
    try:
        html = fetch_level_history_page(session, clan_id=clan_id, filter_type=5, page=0)
    except Exception as e:
        yield ('error', {'reason': 'fetch_error', 'message': f'Ошибка загрузки: {str(e)}'})
        return

    if is_login_redirect(html):
        yield ('error', {'reason': 'session_expired', 'message': 'Сессия истекла, обновите cookies'})
        return

    total_pages = parse_total_pages(html)
    if total_pages is None or total_pages > max_pages:
        total_pages = max_pages

    yield ('counting', {'total_pages': total_pages})

    # Step 2: Parse page 0 events
    page_events = parse_level_change_events(html)
    all_events.extend(page_events)

    yield ('progress', {
        'page': 0,
        'total_pages': total_pages,
        'events_on_page': len(page_events),
        'total_events': len(all_events),
        'elapsed': round(time.time() - start_time, 1),
    })

    # Step 3: Fetch remaining pages
    for page in range(1, total_pages):
        try:
            html = fetch_level_history_page(session, clan_id=clan_id, filter_type=5, page=page)
        except Exception as e:
            yield ('error', {'reason': 'fetch_error', 'message': f'Ошибка на странице {page}: {str(e)}'})
            return

        if is_login_redirect(html):
            yield ('error', {'reason': 'session_expired', 'message': 'Сессия истекла, обновите cookies'})
            return

        page_events = parse_level_change_events(html)
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
