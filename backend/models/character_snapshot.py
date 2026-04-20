from datetime import datetime
from models import db


class CharacterSnapshot(db.Model):
    __tablename__ = 'character_snapshot'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True, index=True)
    nick = db.Column(db.String(100), nullable=False, index=True)
    name = db.Column(db.String(200), default='')
    race = db.Column(db.String(100), default='')
    rank = db.Column(db.String(100), default='')
    clan = db.Column(db.String(200), default='')
    snapshot_name = db.Column(db.String(200), default='')
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    snapshot_data = db.Column(db.Text, nullable=False)

    owner = db.relationship('User', backref='snapshots')

    def __repr__(self):
        return f'<Snapshot {self.nick} at {self.analyzed_at}>'