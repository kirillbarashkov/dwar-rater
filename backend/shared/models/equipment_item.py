from datetime import datetime
from shared.models import db


class EquipmentItem(db.Model):
    __tablename__ = 'equipment_item'
    id = db.Column(db.Integer, primary_key=True)
    snapshot_id = db.Column(db.Integer, db.ForeignKey('character_snapshot.id'), nullable=False, index=True)

    slot_type = db.Column(db.String(50), nullable=False)

    title = db.Column(db.String(255), default='')
    quality_name = db.Column(db.String(50), default='')
    quality_color = db.Column(db.String(20), default='')
    item_level = db.Column(db.String(20), default='')
    durability = db.Column(db.String(50), default='')

    set_name = db.Column(db.String(100), default='')

    rune = db.Column(db.String(255), default='')
    rune2 = db.Column(db.String(255), default='')
    runic_setting = db.Column(db.String(255), default='')
    plate = db.Column(db.String(255), default='')
    lacquer = db.Column(db.String(255), default='')
    enhancement = db.Column(db.String(255), default='')

    symbol_1 = db.Column(db.String(100), default='')
    symbol_2 = db.Column(db.String(100), default='')
    symbol_3 = db.Column(db.String(100), default='')
    symbol_4 = db.Column(db.String(100), default='')

    other = db.Column(db.Text, default='')

    skills_json = db.Column(db.Text, default='[]')
    skills_e_json = db.Column(db.Text, default='[]')
    enchants_json = db.Column(db.Text, default='[]')

    snapshot = db.relationship('CharacterSnapshot', backref='equipment_items')

    def __repr__(self):
        return f'<EquipmentItem {self.slot_type}: {self.title}>'