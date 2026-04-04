from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """Пользователи системы"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<User {self.username}>'


class CharacterCache(db.Model):
    """Кэш данных персонажей (TTL 1 час, чтобы не парсить сайт каждый раз)"""
    nick = db.Column(db.String(100), primary_key=True)
    raw_data = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Cache {self.nick}>'


class CharacterSnapshot(db.Model):
    """
    Долгосрочное хранение слепков персонажей.

    Архитектура: весь результат парсера сохраняется как JSON в snapshot_data.
    Это делает схему гибкой — любые новые поля, которые добавятся в парсер,
    автоматически попадут в БД без миграций.

    user_id связывает слепок с владельцем. Админ видит все слепки.
    snapshot_name — пользовательское имя слепка.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
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


class AnalysisLog(db.Model):
    """
    Журнал анализов. Связывает пользователя со слепком персонажа.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    nick = db.Column(db.String(100), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    snapshot_id = db.Column(db.Integer, db.ForeignKey('character_snapshot.id'), nullable=True)
    analyzed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    snapshot = db.relationship('CharacterSnapshot', backref='analyses')

    def __repr__(self):
        return f'<Log {self.nick} at {self.analyzed_at}>'
