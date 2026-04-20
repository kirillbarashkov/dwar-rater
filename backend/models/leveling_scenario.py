from datetime import datetime
from models import db


class LevelingScenario(db.Model):
    __tablename__ = 'leveling_scenario'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    scenario_data = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='scenarios')

    def __repr__(self):
        return f'<Scenario {self.name}>'
