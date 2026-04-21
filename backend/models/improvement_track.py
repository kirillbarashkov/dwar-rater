from datetime import datetime
from models import db


class ImprovementTrack(db.Model):
    __tablename__ = 'improvement_track'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=False)
    character_nick = db.Column(db.String(100), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey('leveling_scenario.id'), nullable=True)
    track_data = db.Column(db.Text, nullable=False)
    total_progress = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = db.relationship('User', backref='tracks')

    def __repr__(self):
        return f'<Track {self.character_nick}>'
