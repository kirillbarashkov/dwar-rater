"""URL Validator — Spec (Contract)

Defines the input/output/error schemas for validating dwar.ru character URLs.
This is the "port" in the port-adapter pattern: it describes WHAT the service does,
not HOW it does it.
"""

import re
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Optional


ALLOWED_DOMAINS = frozenset({
    'w1.dwar.ru', 'w2.dwar.ru', 'w3.dwar.ru', 'w4.dwar.ru', 'dwar.ru'
})
NICK_PATTERN = re.compile(r'^[a-zA-Z0-9а-яА-ЯёЁ._\-]+$')


@dataclass(frozen=True)
class UrlValidationInput:
    """Input: raw URL string or nick from the user."""
    url: str


@dataclass(frozen=True)
class UrlValidationError:
    """Error: validation failed with a human-readable message."""
    code: str
    message: str

    @property
    def recoverable(self) -> bool:
        return True


@dataclass(frozen=True)
class UrlValidationSuccess:
    """Success: URL is valid. Contains the normalized URL and extracted nick."""
    url: str
    nick: str
    is_full_url: bool


UrlValidationResult = UrlValidationSuccess | UrlValidationError


class UrlValidationSpec:
    """Contract: validate a dwar.ru character URL.

    Input: UrlValidationInput(url)
    Output: UrlValidationSuccess | UrlValidationError
    """

    def validate(self, input: UrlValidationInput) -> UrlValidationResult:
        raise NotImplementedError
