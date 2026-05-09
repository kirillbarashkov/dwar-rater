"""URL Validator — Handler (Implementation)

Implements the UrlValidationSpec contract.
This is the "adapter": it contains the actual validation logic.
NEVER raises exceptions — always returns a Result type.
"""

from urllib.parse import urlparse

from shared.services.url_validator.spec import (
    UrlValidationInput,
    UrlValidationResult,
    UrlValidationSuccess,
    UrlValidationError,
    UrlValidationSpec,
    ALLOWED_DOMAINS,
    NICK_PATTERN,
)


class UrlValidationHandler(UrlValidationSpec):
    """Validates dwar.ru character URLs."""

    def validate(self, input: UrlValidationInput) -> UrlValidationResult:
        url = input.url.strip() if input.url else ''

        if not url:
            return UrlValidationError('empty_url', 'URL не указан')

        if '://' in url:
            return self._validate_full_url(url)

        return self._validate_nick(url)

    def _validate_nick(self, raw: str) -> UrlValidationResult:
        nick = raw
        if 'nick=' in nick:
            nick = nick.split('nick=')[1].split('&')[0]

        if not nick or len(nick) > 50:
            return UrlValidationError('invalid_nick', 'Некорректный ник')

        if not NICK_PATTERN.match(nick):
            return UrlValidationError('invalid_nick_chars', 'Ник содержит недопустимые символы')

        return UrlValidationSuccess(
            url=f'https://w1.dwar.ru/user_info.php?nick={nick}',
            nick=nick,
            is_full_url=False,
        )

    def _validate_full_url(self, url: str) -> UrlValidationResult:
        parsed = urlparse(url)

        if parsed.scheme not in ('http', 'https'):
            return UrlValidationError('invalid_scheme', 'Разрешены только HTTP и HTTPS ссылки')

        if parsed.netloc not in ALLOWED_DOMAINS:
            return UrlValidationError('domain_not_allowed', 'Разрешены только ссылки на dwar.ru')

        if 'user_info.php' not in parsed.path:
            return UrlValidationError('invalid_path', 'Некорректный URL профиля')

        nick = parsed.query
        if 'nick=' in nick:
            nick = nick.split('nick=')[1].split('&')[0]

        return UrlValidationSuccess(
            url=url,
            nick=nick,
            is_full_url=True,
        )
