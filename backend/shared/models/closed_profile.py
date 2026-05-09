from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from datetime import datetime, timezone
from shared.models import db


class ClosedProfile(db.Model):
    __tablename__ = 'closed_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nick = Column(String(100), unique=True, nullable=False, index=True)
    first_seen_closed = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    last_checked = Column(DateTime, nullable=True)
    check_count = Column(Integer, default=0)
    status = Column(String(20), default='closed')
    level = Column(String(20), nullable=True)
    rank = Column(String(20), nullable=True)
    clan = Column(String(200), nullable=True)
    snapshot_id = Column(Integer, ForeignKey('character_snapshot.id'), nullable=True)
    notes = Column(Text, nullable=True)
    is_scanned_open = Column(Boolean, default=False)
    scanned_open_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'nick': self.nick,
            'first_seen_closed': self.first_seen_closed.isoformat() if self.first_seen_closed else None,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'check_count': self.check_count,
            'status': self.status,
            'level': self.level,
            'rank': self.rank,
            'clan': self.clan,
            'snapshot_id': self.snapshot_id,
            'notes': self.notes,
            'is_scanned_open': self.is_scanned_open,
            'scanned_open_at': self.scanned_open_at.isoformat() if self.scanned_open_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
