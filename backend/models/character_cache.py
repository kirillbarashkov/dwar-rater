from datetime import datetime
from backend.models import db


class CharacterCache(db.Model):
    __tablename__ = 'character_cache'
    nick = db.Column(db.String(100), primary_key=True)
    raw_data = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Cache {self.nick}>'
