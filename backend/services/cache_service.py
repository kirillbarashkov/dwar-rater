import json
from datetime import datetime
from models import db
from models.character_cache import CharacterCache
from models.character_snapshot import CharacterSnapshot
from models.analysis_log import AnalysisLog

CACHE_TTL_SECONDS = 3600


def get_cached_character(nick):
    cached = CharacterCache.query.filter_by(nick=nick).first()
    if cached and (datetime.utcnow() - cached.updated_at).total_seconds() < CACHE_TTL_SECONDS:
        return json.loads(cached.raw_data)
    return None


def save_character_cache(nick, raw_data):
    cached = CharacterCache.query.filter_by(nick=nick).first()
    if cached:
        cached.raw_data = json.dumps(raw_data, ensure_ascii=False)
        cached.updated_at = datetime.utcnow()
    else:
        cached = CharacterCache(nick=nick, raw_data=json.dumps(raw_data, ensure_ascii=False))
        db.session.add(cached)
    db.session.commit()


def create_snapshot(raw_data, user_id=None):
    snapshot = CharacterSnapshot(
        user_id=user_id,
        nick=raw_data.get('name', ''),
        name=raw_data.get('name', ''),
        race=raw_data.get('race', ''),
        rank=raw_data.get('rank', ''),
        clan=raw_data.get('clan', ''),
        snapshot_data=json.dumps(raw_data, ensure_ascii=False),
    )
    db.session.add(snapshot)
    db.session.flush()
    return snapshot.id


def create_named_snapshot(snapshot_data, snapshot_name, user_id, url=''):
    snapshot_data['snapshot_name'] = snapshot_name
    snapshot = CharacterSnapshot(
        user_id=user_id,
nick=snapshot_data.get('name', ''),
        name=snapshot_data.get('name', ''),
        race=snapshot_data.get('race', ''),
        rank=snapshot_data.get('rank', ''),
        clan=snapshot_data.get('clan', ''),
        snapshot_name=snapshot_name,
        snapshot_data=json.dumps(snapshot_data, ensure_ascii=False),
    )
    db.session.add(snapshot)
    db.session.flush()
    return snapshot.id


def log_analysis(user_id, nick, url, snapshot_id=None):
    log = AnalysisLog(user_id=user_id, nick=nick, url=url, snapshot_id=snapshot_id)
    db.session.add(log)
    db.session.commit()
