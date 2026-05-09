"""Cyrillic to Latin transliteration utility.

Rules:
- Standard GOST-style transliteration
- Only a-z, 0-9 in output
- Spaces, special chars removed
- Result lowercased
"""

TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd',
    'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
    'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
    'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
    'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch',
    'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '',
    'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def transliterate(text: str) -> str:
    """Transliterate Cyrillic text to Latin. Only a-z, 0-9 in output."""
    result = []
    for char in text.lower():
        if char in TRANSLIT_MAP:
            result.append(TRANSLIT_MAP[char])
        elif 'a' <= char <= 'z' or '0' <= char <= '9':
            result.append(char)
        # Everything else (spaces, special chars, etc.) is dropped
    return ''.join(result)


def ensure_unique_username(nick: str, existing: set[str], min_len: int = 3, max_len: int = 25) -> str:
    """Transliterate nick, enforce length constraints, ensure uniqueness.

    - Transliterates Cyrillic to Latin
    - Truncates to max_len
    - If < min_len, appends incrementing number
    - If duplicate, appends incrementing number
    """
    base = transliterate(nick)[:max_len]

    if len(base) < min_len:
        suffix = 1
        while True:
            candidate = f"{base}{suffix}"
            if candidate not in existing:
                return candidate
            suffix += 1

    if base not in existing:
        return base

    suffix = 1
    while True:
        candidate = f"{base}{suffix}"
        if len(candidate) <= max_len and candidate not in existing:
            return candidate
        suffix += 1
        # Fallback: truncate base to make room for suffix
        if len(candidate) > max_len:
            truncated = base[:max_len - len(str(suffix))]
            candidate = f"{truncated}{suffix}"
            if candidate not in existing:
                return candidate
