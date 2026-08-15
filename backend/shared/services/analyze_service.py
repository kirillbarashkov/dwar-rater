"""Analyze pipeline as a reusable service.

Extracted from features/analyze/routes.py so that features/tracks (track
generation with a live-URL target) can reuse the exact same
fetch → parse → process → cache → log pipeline without duplication.
"""

from urllib.parse import urlparse, parse_qs

from shared.services.parser import fetch_character_page, parse_character
from shared.services.processor import process_character
from shared.services.cache_service import get_cached_character, save_character_cache, log_analysis
from shared.utils.validators import validate_dwar_url


class AnalyzeError(Exception):
    """Raised when the analyze pipeline fails; message is user-facing."""

    def __init__(self, message, status_code=500):
        super().__init__(message)
        self.status_code = status_code


def normalize_url(url):
    """Validate a dwar URL (or bare nick) and return (url, nick, error)."""
    valid, error = validate_dwar_url(url)
    if not valid:
        return None, None, error

    if not url.startswith('http'):
        nick = url
        if 'nick=' in nick:
            nick = nick.split('nick=')[1].split('&')[0]
        url = f'https://w1.dwar.ru/user_info.php?nick={nick}'
    else:
        nick = parse_qs(urlparse(url).query).get('nick', [''])[0]

    return url, nick, None


def analyze_character_url(url, force_refresh=False, user=None):
    """Full analyze pipeline for a character URL (or bare nick).

    Cache-first unless force_refresh. Returns the processed character dict.
    Raises AnalyzeError with a user-facing message on failure.
    """
    url, nick, error = normalize_url(url)
    if error:
        raise AnalyzeError(error, 400)

    user_id = user.id if user is not None else None

    cached = get_cached_character(nick)
    if cached and not force_refresh:
        log_analysis(user_id, nick, url)
        return process_character(cached)

    try:
        html, session = fetch_character_page(url)
        raw = parse_character(html, session=session, nick=nick)
        save_character_cache(nick, raw)
        processed = process_character(raw)
        log_analysis(user_id, nick, url)
        return processed
    except AnalyzeError:
        raise
    except Exception as e:
        error_msg = str(e)
        if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
            raise AnalyzeError('Таймаут запроса к серверу dwar.ru', 504)
        if 'request' in error_msg.lower():
            raise AnalyzeError(f'Ошибка загрузки страницы: {error_msg}', 500)
        raise AnalyzeError(f'Ошибка обработки: {error_msg}', 500)
