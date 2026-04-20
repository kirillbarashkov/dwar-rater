import json
from datetime import datetime
from models import db


class CompareCharacter(db.Model):
    __tablename__ = 'compare_character'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True, index=True)
    character_name = db.Column(db.String(255), nullable=False)
    snapshot_data = db.Column(db.Text, nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    sort_order = db.Column(db.Integer, default=0)

    owner = db.relationship('User', backref='compare_characters', foreign_keys=[user_id])

    def __repr__(self):
        return f'<CompareCharacter {self.character_name}>'

    def to_dict(self):
        data = json.loads(self.snapshot_data) if isinstance(self.snapshot_data, str) else self.snapshot_data
        return {
            'id': self.id,
            'name': self.character_name,
            'data': data,
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'sort_order': self.sort_order,
        }