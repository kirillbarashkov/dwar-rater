"""A28: `shared/services/cache_service.py` не был покрыт ни одним тестом.

Кэш персонажа — это TTL-логика, то есть единственное место, где ошибка тихая:
устаревшие данные возвращаются как свежие, и заметить это можно только по
странному поведению приложения. Тесты держат границу TTL и перезапись записи.

Снимки (`create_snapshot`, `create_named_snapshot`) тоже тестируются: у них
одинаковая форма, но разные поля, и их легко «починить» так, что в слепке
окажется не то имя.
"""

import json
import os
import sys

import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.character_cache import CharacterCache
from shared.models.character_snapshot import CharacterSnapshot
from shared.services.cache_service import (
    CACHE_TTL_SECONDS,
    get_cached_character,
    save_character_cache,
    create_snapshot,
    create_named_snapshot,
)

NICK = 'a28_cached_hero'


def _purge():
    CharacterCache.query.filter_by(nick=NICK).delete()
    CharacterSnapshot.query.filter(CharacterSnapshot.nick.like('a28%')).delete()
    db.session.commit()


@pytest.fixture(autouse=True)
def _clean_snapshots(app):
    """A28: `_truncate_all()` в conftest — no-op, поэтому чистим сами.

    Иначе созданные здесь слепки попадают в `test_snapshots_empty_list`, и он
    падает «из-за чужого теста» — проверено на полном прогоне.
    """
    with app.app_context():
        _purge()
    yield
    with app.app_context():
        _purge()


def test_missing_nick_returns_none(app):
    with app.app_context():
        _purge()
        assert get_cached_character(NICK) is None


def test_saved_character_is_returned_as_the_same_object(app):
    with app.app_context():
        _purge()
        raw = {'name': NICK, 'level': 20, 'stats': {'Сила': 100}}
        save_character_cache(NICK, raw)

        assert get_cached_character(NICK) == raw, 'кэш вернул не то, что положили'


def test_fresh_entry_is_served(app):
    with app.app_context():
        _purge()
        save_character_cache(NICK, {'name': NICK})
        assert get_cached_character(NICK) is not None


def test_entry_older_than_ttl_is_not_served(app):
    with app.app_context():
        _purge()
        save_character_cache(NICK, {'name': NICK})
        row = CharacterCache.query.filter_by(nick=NICK).first()
        row.updated_at = datetime.utcnow() - timedelta(seconds=CACHE_TTL_SECONDS + 60)
        db.session.commit()

        assert get_cached_character(NICK) is None, 'устаревшая запись отдана как свежая'


def test_entry_just_inside_ttl_is_still_served(app):
    """Граница: 60 секунд до истечения — данные ещё валидны."""
    with app.app_context():
        _purge()
        save_character_cache(NICK, {'name': NICK})
        row = CharacterCache.query.filter_by(nick=NICK).first()
        row.updated_at = datetime.utcnow() - timedelta(seconds=CACHE_TTL_SECONDS - 60)
        db.session.commit()

        assert get_cached_character(NICK) is not None


def test_second_save_overwrites_instead_of_duplicating(app):
    with app.app_context():
        _purge()
        save_character_cache(NICK, {'name': NICK, 'level': 1})
        save_character_cache(NICK, {'name': NICK, 'level': 2})

        rows = CharacterCache.query.filter_by(nick=NICK).all()
        assert len(rows) == 1, f'дубли записей кэша: {len(rows)}'
        assert get_cached_character(NICK)['level'] == 2


def test_non_ascii_survives_the_cache_round_trip(app):
    """`ensure_ascii=False` в save — иначе кириллица приходит экранированной."""
    with app.app_context():
        _purge()
        raw = {'name': NICK, 'rank': 'Воин', 'clan': 'Гномы'}
        save_character_cache(NICK, raw)
        stored = CharacterCache.query.filter_by(nick=NICK).first().raw_data
        assert 'Воин' in stored, 'данные записаны escaped-последовательностями'
        assert get_cached_character(NICK)['rank'] == 'Воин'


def test_create_snapshot_copies_identity_fields(app):
    with app.app_context():
        _purge()
        raw = {'name': 'a28_snapshot', 'race': 'Гном', 'rank': 'Воин', 'clan': 'Тест'}
        snapshot_id = create_snapshot(raw)
        db.session.commit()

        snapshot = CharacterSnapshot.query.get(snapshot_id)
        assert snapshot.nick == 'a28_snapshot'
        assert snapshot.race == 'Гном'
        assert snapshot.clan == 'Тест'
        assert json.loads(snapshot.snapshot_data)['rank'] == 'Воин'


def test_named_snapshot_keeps_both_name_and_payload(app):
    with app.app_context():
        _purge()
        raw = {'name': 'a28_named', 'race': 'Гном'}
        snapshot_id = create_named_snapshot(raw, 'Перед рейдом', user_id=1)
        db.session.commit()

        snapshot = CharacterSnapshot.query.get(snapshot_id)
        assert snapshot.snapshot_name == 'Перед рейдом'
        assert json.loads(snapshot.snapshot_data)['snapshot_name'] == 'Перед рейдом'
        assert json.loads(snapshot.snapshot_data)['name'] == 'a28_named'
