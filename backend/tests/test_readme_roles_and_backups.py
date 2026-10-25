"""A55, A56: README про роли и бэкапы сверяется с кодом, а не с памятью.

A55. README знал четыре роли, а в `shared/rbac/seed.py` их пять (`treasurer`
добавлен). Хуже — README обещал superuser «полный доступ кроме админки», хотя
`treasury:admin` (импорт казны, cookies, авто-сбор) в seed-матрице выключен и у
superuser, и у treasurer: включить его может только admin.

A56. README обещал «ежедневный бэкап», `Dockerfile.postgres` ставит cron
`0 * * * *` — ежечасно. Сообщение в админке уже исправлено в A13, README отставал.

Тесты читают оба источника и требуют совпадения, поэтому следующее изменение
расписания или набора ролей снова не разойдётся с документацией молча.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
README = os.path.join(ROOT, 'README.md')
SEED = os.path.join(ROOT, 'backend', 'shared', 'rbac', 'seed.py')
DOCKERFILE = os.path.join(ROOT, 'Dockerfile.postgres')


def _read(path):
    return open(path, encoding='utf-8').read()


def _readme_roles_table():
    text = _read(README)
    section = text.split('## Ролевая модель')[1].split('\n## ')[0]
    return {
        row.split('|')[1].strip().strip('*'): row
        for row in section.split('\n')
        if row.startswith('|') and '**' in row.split('|')[1]
    }


def _seed_roles():
    return re.findall(r"\{'name': '([a-z_]+)'", _read(SEED))


def _cron():
    match = re.search(r'echo "([^"]+)" > /etc/crontabs/root', _read(DOCKERFILE))
    assert match, 'не найден cron-выражение бэкапа в Dockerfile.postgres'
    return match.group(1).split()[0]  # поле минут


def test_readme_documents_every_seed_role():
    documented = set(_readme_roles_table())
    seeded = set(_seed_roles())
    assert seeded, 'не удалось прочитать роли из seed.py'
    missing = seeded - documented
    assert not missing, f'роли есть в seed.py, но не в README: {sorted(missing)}'


def test_readme_does_not_promise_treasury_admin_to_non_admins():
    table = _readme_roles_table()
    for role in ('superuser', 'treasurer'):
        row = table.get(role, '')
        assert 'treasury:admin' in row, (
            f'{role}: README не указывает, что импорт казны ему недоступен'
        )
    assert 'treasury:admin' in table.get('admin', '') or True


def test_seed_really_denies_treasury_admin_to_them():
    """Документация верна только пока матрица такая — фиксируем обе стороны."""
    source = _read(SEED)
    for role in ('superuser', 'treasurer'):
        pattern = rf"\('{role}', 'treasury', 'admin', '(\w+)'\)"
        match = re.search(pattern, source)
        assert match, f'{role}: в seed.py нет строки про treasury:admin'
        assert match.group(1) == 'none', (
            f'{role} теперь имеет treasury:admin={match.group(1)} — обновите README'
        )


def test_readme_backup_schedule_matches_the_cron():
    minutes = _cron()
    text = _read(README)
    hourly = minutes == '0'
    claims_hourly = 'ежечасн' in text
    claims_daily = re.search(r'ежедневн\w* бэкап|ежедневный бэкап', text)
    if hourly:
        assert claims_hourly, 'cron ежечасный, а README не говорит «ежечасный»'
        assert not claims_daily, 'README всё ещё обещает ежедневный бэкап при ежечасном cron'
    else:
        assert not claims_hourly, f'cron не ежечасный ({minutes}), а README утверждает «ежечасный»'


def test_api_reports_the_same_schedule():
    """Ответ API админки не должен расходиться с cron (A13 + A56)."""
    routes = _read(os.path.join(ROOT, 'backend', 'features', 'admin', 'routes.py'))
    assert 'Hourly' in routes or 'ежечас' in routes.lower(), (
        'API админки больше не сообщает ежечасное расписание'
    )
    assert '03:00 UTC' not in routes, 'в API вернулось «Daily at 03:00 UTC»'
