from datetime import datetime
from models import db


class Clan(db.Model):
    __tablename__ = 'clan'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', foreign_keys=[created_by])

    def __repr__(self):
        return f'<Clan {self.name}>'


class ClanMember(db.Model):
    __tablename__ = 'clan_member'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, db.ForeignKey('clan.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=False)
    role = db.Column(db.String(20), default='member')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('clan_id', 'user_id'),)

    clan = db.relationship('Clan', backref='members')
    user = db.relationship('User', backref='clan_memberships')

    def __repr__(self):
        return f'<ClanMember user={self.user_id} clan={self.clan_id}>'


class ClanChatRoom(db.Model):
    __tablename__ = 'clan_chat_room'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, db.ForeignKey('clan.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    clan = db.relationship('Clan', backref='chat_rooms')

    def __repr__(self):
        return f'<ClanChatRoom {self.name}>'


class ClanChatMessage(db.Model):
    __tablename__ = 'clan_chat_message'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('clan_chat_room.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)

    room = db.relationship('ClanChatRoom', backref='messages')
    user = db.relationship('User', backref='chat_messages')

    def __repr__(self):
        return f'<ClanChatMessage {self.id}>'
