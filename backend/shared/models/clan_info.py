import re
import json
from datetime import datetime
from shared.models import db


class ClanInfo(db.Model):
    __tablename__ = 'clan_info'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    logo_url = db.Column(db.String(300), default='')
    logo_big = db.Column(db.String(300), default='')
    logo_small = db.Column(db.String(300), default='')
    description = db.Column(db.Text, default='')
    leader_nick = db.Column(db.String(100), default='')
    leader_rank = db.Column(db.String(100), default='')
    clan_rank = db.Column(db.String(100), default='')
    clan_level = db.Column(db.Integer, default=0)
    step = db.Column(db.Integer, default=0)
    talents = db.Column(db.Integer, default=0)
    total_players = db.Column(db.Integer, default=0)
    current_players = db.Column(db.Integer, default=0)
    council = db.Column(db.Text, default='[]')
    clan_structure = db.Column(db.Text, default='{}')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_council(self):
        try:
            return json.loads(self.council)
        except:
            return []

    def set_council(self, value):
        self.council = json.dumps(value, ensure_ascii=False)

    def get_clan_structure(self):
        try:
            return json.loads(self.clan_structure)
        except:
            return {}

    def set_clan_structure(self, value):
        self.clan_structure = json.dumps(value, ensure_ascii=False)

    def __repr__(self):
        return f'<ClanInfo {self.name}>'


class ClanMemberInfo(db.Model):
    __tablename__ = 'clan_member_info'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True)
    nick = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(10), default='')
    game_rank = db.Column(db.String(100), default='')
    level = db.Column(db.Integer, default=0)
    profession = db.Column(db.String(100), default='')
    profession_level = db.Column(db.Integer, default=0)
    clan_role = db.Column(db.String(100), default='')
    join_date = db.Column(db.String(20), default='')
    trial_until = db.Column(db.String(20), default='')
    is_deleted = db.Column(db.Boolean, default=False)
    left_date = db.Column(db.String(20), default='')
    leave_reason = db.Column(db.String(200), default='')

    clan = db.relationship('ClanInfo', foreign_keys=[clan_id], primaryjoin='ClanMemberInfo.clan_id == ClanInfo.clan_id')
    
    def __repr__(self):
        return f'<ClanMemberInfo {self.nick}>'


class TreasuryOperation(db.Model):
    __tablename__ = 'treasury_operations'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True)
    date = db.Column(db.String(20), default='')
    nick = db.Column(db.String(100), default='')
    operation_type = db.Column(db.String(100), default='')
    object_name = db.Column(db.String(200), default='')
    quantity = db.Column(db.Integer, default=0)
    compensation_flag = db.Column(db.Boolean, default=False)
    compensation_comment = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    clan = db.relationship('ClanInfo', foreign_keys=[clan_id], primaryjoin='TreasuryOperation.clan_id == ClanInfo.clan_id')

    def __repr__(self):
        return f'<TreasuryOperation {self.date} {self.nick}>'
