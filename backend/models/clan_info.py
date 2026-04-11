import re
from datetime import datetime
from models import db


class ClanInfo(db.Model):
    __tablename__ = 'clan_info'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    logo_url = db.Column(db.String(300), default='')
    description = db.Column(db.Text, default='')
    leader_nick = db.Column(db.String(100), default='')
    leader_rank = db.Column(db.String(100), default='')
    clan_rank = db.Column(db.String(100), default='')
    clan_level = db.Column(db.Integer, default=0)
    step = db.Column(db.Integer, default=0)
    talents = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

    clan = db.relationship('ClanInfo', foreign_keys=[clan_id], primaryjoin='ClanMemberInfo.clan_id == ClanInfo.clan_id')

    def __repr__(self):
        return f'<ClanMemberInfo {self.nick}>'


class ClanHierarchy(db.Model):
    __tablename__ = 'clan_hierarchy'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True)
    role_name = db.Column(db.String(100), nullable=False)
    level = db.Column(db.Integer, default=0)
    color = db.Column(db.String(20), default='#00d4aa')
    icon = db.Column(db.String(10), default='')
    sort_order = db.Column(db.Integer, default=0)
    can_invite = db.Column(db.Boolean, default=False)
    can_kick = db.Column(db.Boolean, default=False)
    can_edit = db.Column(db.Boolean, default=False)
    can_analyze = db.Column(db.Boolean, default=True)
    min_level = db.Column(db.Integer, default=0)

    clan = db.relationship('ClanInfo', foreign_keys=[clan_id], primaryjoin='ClanHierarchy.clan_id == ClanInfo.clan_id')

    def __repr__(self):
        return f'<ClanHierarchy {self.role_name}>'
