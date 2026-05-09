"""Tests for services/url_validator — Spec (contract) tests.

Tests the validation rules (the "bouncer"): ensure invalid input is rejected
and valid input is accepted. Data-driven table tests.
"""

import pytest
from shared.services.url_validator.spec import UrlValidationInput, UrlValidationSuccess, UrlValidationError
from shared.services.url_validator.handler import UrlValidationHandler


@pytest.fixture
def handler():
    return UrlValidationHandler()


class TestUrlValidation:
    """Data-driven tests for URL validation rules."""

    VALID_CASES = [
        pytest.param('https://w1.dwar.ru/user_info.php?nick=TestNick', 'TestNick', True, id='full_url_w1'),
        pytest.param('https://w2.dwar.ru/user_info.php?nick=TestNick', 'TestNick', True, id='full_url_w2'),
        pytest.param('https://dwar.ru/user_info.php?nick=TestNick', 'TestNick', True, id='full_url_main'),
        pytest.param('http://w1.dwar.ru/user_info.php?nick=TestNick', 'TestNick', True, id='http_url'),
        pytest.param('TestNick', 'TestNick', False, id='nick_only'),
        pytest.param('nick=TestNick', 'TestNick', False, id='nick_param'),
        pytest.param('Игрок_1', 'Игрок_1', False, id='cyrillic_nick'),
        pytest.param('Player.Name-123', 'Player.Name-123', False, id='nick_with_dots_dashes'),
    ]

    INVALID_CASES = [
        pytest.param('', 'empty_url', id='empty_string'),
        pytest.param('   ', 'empty_url', id='whitespace_only'),
        pytest.param('nick=', 'invalid_nick', id='empty_nick_param'),
        pytest.param('a' * 51, 'invalid_nick', id='nick_too_long'),
        pytest.param('nick<script>', 'invalid_nick_chars', id='nick_with_html'),
        pytest.param('nick@bad!', 'invalid_nick_chars', id='nick_with_special'),
        pytest.param('https://evil.com/user_info.php?nick=Test', 'domain_not_allowed', id='wrong_domain'),
        pytest.param('https://w1.dwar.ru/other_page', 'invalid_path', id='wrong_path'),
        pytest.param('ftp://w1.dwar.ru/user_info.php?nick=Test', 'invalid_scheme', id='wrong_scheme'),
    ]

    @pytest.mark.parametrize('url,expected_nick,is_full_url', VALID_CASES)
    def test_valid_urls(self, handler, url, expected_nick, is_full_url):
        result = handler.validate(UrlValidationInput(url=url))
        assert isinstance(result, UrlValidationSuccess)
        assert result.nick == expected_nick
        assert result.is_full_url == is_full_url
        assert result.url  # URL is set

    @pytest.mark.parametrize('url,expected_code', INVALID_CASES)
    def test_invalid_urls(self, handler, url, expected_code):
        result = handler.validate(UrlValidationInput(url=url))
        assert isinstance(result, UrlValidationError)
        assert result.code == expected_code
        assert result.message  # Has human-readable message
        assert result.recoverable is True
