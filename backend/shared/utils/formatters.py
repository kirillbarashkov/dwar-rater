def fmt_num(n):
    try:
        return f"{int(n):,}".replace(',', ' ')
    except (ValueError, TypeError):
        return str(n)


def clean_html(text):
    import re
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-z]+;', '', text)
    text = re.sub(r'&#\d+;', '', text)
    return text.strip()
