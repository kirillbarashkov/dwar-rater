from datetime import datetime
from shared.models import db


class CharacterCache(db.Model):
    __tablename__ = 'character_cache'
    id = db.Column(db.Integer, primary_key=True)
    nick = db.Column(db.String(100), nullable=False, unique=True, index=True)
    raw_data = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Cache {self.nick}>'
