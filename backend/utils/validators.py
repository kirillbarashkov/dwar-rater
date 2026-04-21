import re
from urllib.parse import urlparse


ALLOWED_DOMAINS = {'w1.dwar.ru', 'w2.dwar.ru', 'w3.dwar.ru', 'w4.dwar.ru', 'dwar.ru'}
NICK_PATTERN = re.compile(r'^[a-zA-Z0-9а-яА-ЯёЁ._\-]+$')


def validate_dwar_url(url):
    if not url or not url.strip():
        return False, 'URL не указан'

    url = url.strip()

    if not url.startswith('http'):
        nick = url
        if 'nick=' in nick:
            nick = nick.split('nick=')[1].split('&')[0]
        if not nick or len(nick) > 50:
            return False, 'Некорректный ник'
        if not NICK_PATTERN.match(nick):
            return False, 'Ник содержит недопустимые символы'
        return True, None

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False, 'Разрешены только HTTP и HTTPS ссылки'
    if parsed.netloc not in ALLOWED_DOMAINS:
        return False, 'Разрешены только ссылки на dwar.ru'
    if 'user_info.php' not in parsed.path:
        return False, 'Некорректный URL профиля'
    return True, None
