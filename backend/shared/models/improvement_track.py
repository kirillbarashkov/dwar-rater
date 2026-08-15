import json
from datetime import datetime
from shared.models import db


def _character_summary(character):
    """Compact source/target summary for API responses."""
    if not character:
        return {'name': '', 'level': '', 'main_stats': {}, 'hp': '', 'power': 0}
    main_stats = character.get('main_stats', {})
    top3 = dict(sorted(main_stats.items(), key=lambda kv: _parse_num(kv[1]), reverse=True)[:3])
    return {
        'name': character.get('name', ''),
        'level': str(character.get('level', '')),
        'main_stats': top3,
        'hp': str(character.get('flashvars_extra', {}).get('hpMax', '')),
        'power': character.get('_power', 0),
    }


def _parse_num(val):
    try:
        return int(str(val).replace(' ', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0


class ImprovementTrack(db.Model):
    __tablename__ = 'improvement_track'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=False)
    character_nick = db.Column(db.String(100), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey('leveling_scenario.id'), nullable=True)
    track_data = db.Column(db.Text, nullable=False)
    total_progress = db.Column(db.Float, default=0.0)
    target_type = db.Column(db.String(20), nullable=False, default='scenario')
    target_ref = db.Column(db.String(512), nullable=True)
    source_snapshot = db.Column(db.Text, nullable=True)
    target_snapshot = db.Column(db.Text, nullable=True)
    power_gap = db.Column(db.Float, nullable=True, default=0.0)
    phases_data = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship('User', backref='tracks')

    def __repr__(self):
        return f'<Track {self.character_nick}>'

    def to_dict(self, include_snapshots=False):
        steps = json.loads(self.track_data) if self.track_data else []
        phases = json.loads(self.phases_data) if self.phases_data else []
        source = json.loads(self.source_snapshot) if self.source_snapshot else None
        target = json.loads(self.target_snapshot) if self.target_snapshot else None
        result = {
            'id': self.id,
            'character_nick': self.character_nick,
            'scenario_id': self.scenario_id,
            'target_type': self.target_type,
            'target_ref': self.target_ref,
            'steps': steps,
            'phases': phases,
            'total_progress': self.total_progress,
            'power_gap': self.power_gap or 0.0,
            'source_summary': _character_summary(source),
            'target_summary': _character_summary(target),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_snapshots:
            result['source_snapshot'] = source
            result['target_snapshot'] = target
        return result
