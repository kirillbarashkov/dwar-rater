from urllib.parse import urlparse


ALLOWED_DOMAINS = {'w1.dwar.ru', 'w2.dwar.ru', 'w3.dwar.ru', 'w4.dwar.ru', 'dwar.ru'}


def validate_dwar_url(url):
    if not url or not url.strip():
        return False, 'URL не указан'
    if not url.startswith('http'):
        return True, None
    parsed = urlparse(url)
    if parsed.netloc not in ALLOWED_DOMAINS:
        return False, 'Разрешены только ссылки на dwar.ru'
    return True, None
