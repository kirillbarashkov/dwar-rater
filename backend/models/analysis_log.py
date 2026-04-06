from datetime import datetime
from models import db


class AnalysisLog(db.Model):
    __tablename__ = 'analysis_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    nick = db.Column(db.String(100), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    snapshot_id = db.Column(db.Integer, db.ForeignKey('character_snapshot.id'), nullable=True)
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    snapshot = db.relationship('CharacterSnapshot', backref='analyses')

    def __repr__(self):
        return f'<Log {self.nick} at {self.analyzed_at}>'
