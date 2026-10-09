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


class ClanMembershipEvent(db.Model):
    __tablename__ = 'clan_membership_events'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True)
    nick = db.Column(db.String(100), nullable=False)
    event_type = db.Column(db.String(10), nullable=False)
    event_date = db.Column(db.String(20), default='')
    source = db.Column(db.String(10), default='diff')
    leave_reason = db.Column(db.String(200), default='')
    synced = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    clan = db.relationship('ClanInfo', foreign_keys=[clan_id], primaryjoin='ClanMembershipEvent.clan_id == ClanInfo.clan_id')

    def __repr__(self):
        return f'<ClanMembershipEvent {self.event_type} {self.nick} {self.event_date}>'


class ClanCookie(db.Model):
    __tablename__ = 'clan_cookies'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, nullable=False, index=True)
    cookie_string = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_valid = db.Column(db.Boolean, default=True, server_default='1')

    def __repr__(self):
        return f'<ClanCookie clan_id={self.clan_id} valid={self.is_valid}>'


class TreasurySourceWindow(db.Model):
    """Oldest treasury operation date dwar still serves for a clan.

    dwar purges operations after roughly six months and never says so — the
    report simply ends. The boundary is LEARNED from import attempts, never
    probed: when the estimate walks to the end of the report while the
    requested start date is still older, the oldest date actually seen is
    stored here.

    Consumers:
      - the import UI tags periods older than this and freezes their
        selection, so nobody waits for data that cannot arrive;
      - the estimate / auto-fetch routes answer with an explicit error
        instead of an empty but "successful" result.
    """

    __tablename__ = 'treasury_source_window'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, nullable=False, unique=True, index=True)
    # DD.MM.YYYY of the oldest operation the source returned.
    oldest_date = db.Column(db.String(20), default='')
    # Total pages the report had when the boundary was learned.
    total_pages = db.Column(db.Integer, default=0)
    learned_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f'<TreasurySourceWindow clan={self.clan_id} oldest={self.oldest_date}>'


class TaxCarryover(db.Model):
    """Review ledger for tax overpayments carried to the next month.

    A proposal lives here with ``status='pending'`` until a treasurer confirms
    or cancels it. The excess is NOT materialised as a synthetic
    ``treasury_operations`` row: cancelling must not delete anything from the
    treasury, an overpayment is not money received, and a cancelled proposal
    must be remembered so recomputation does not bring it back.

    ``source_month`` / ``source_year`` are the month the member overpaid;
    the credit applies to the following month (derived, never stored, so the
    two cannot drift apart).
    """

    __tablename__ = 'tax_carryover'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(
        db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True
    )
    nick = db.Column(db.String(100), nullable=False)
    source_month = db.Column(db.Integer, nullable=False)
    source_year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(12), nullable=False, default='pending')
    comment = db.Column(db.String(500), default='')
    created_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            'clan_id', 'nick', 'source_month', 'source_year',
            name='uq_tax_carryover_source',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'clan_id': self.clan_id,
            'nick': self.nick,
            'source_month': self.source_month,
            'source_year': self.source_year,
            'amount': self.amount,
            'status': self.status,
            'comment': self.comment or '',
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
        }

    def __repr__(self):
        return (
            f'<TaxCarryover clan={self.clan_id} {self.nick} '
            f'{self.source_month:02d}.{self.source_year} {self.amount} {self.status}>'
        )


class ClanLevelChangeEvent(db.Model):
    __tablename__ = 'clan_level_change_events'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True)
    nick = db.Column(db.String(100), nullable=False)
    old_level = db.Column(db.Integer, default=0)
    new_level = db.Column(db.Integer, nullable=False)
    event_date = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    clan = db.relationship('ClanInfo', foreign_keys=[clan_id], primaryjoin='ClanLevelChangeEvent.clan_id == ClanInfo.clan_id')

    def __repr__(self):
        return f'<ClanLevelChangeEvent {self.nick} {self.old_level}->{self.new_level} {self.event_date}>'


class TreasuryMonthClose(db.Model):
    """An explicit «месяц закрыт» decision for a clan's treasury.

    ``tax_engine.is_month_closed()`` only means "the month has passed on the
    calendar"; this row is the treasurer actually freezing it. A frozen month
    refuses manual writes (corrections, re-attributions, compensations and
    imports) until it is explicitly reopened, so a month the clan already settled
    cannot be re-shaken retroactively. Both decisions land in the audit log — the
    row simply carries the current state.
    """

    __tablename__ = 'treasury_month_close'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(
        db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True
    )
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(200), default='')
    closed_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    closed_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            'clan_id', 'month', 'year', name='uq_treasury_month_close'
        ),
    )

    def to_dict(self):
        return {
            'month': self.month,
            'year': self.year,
            'note': self.note or '',
            'closed_by': self.closed_by,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
        }

    def __repr__(self):
        return f'<TreasuryMonthClose clan={self.clan_id} {self.month:02d}.{self.year}>'


class TreasuryAnomalyMute(db.Model):
    """A treasurer's «это нормально» on one category of finding.

    A ghost nick (a member who left the clan) and a prepayment above the norm are
    legitimate, so the report keeps naming them until someone says «I know». The
    decision is stored per clan — it belongs to the clan, not to the browser that
    happened to make it, and every treasurer should stop seeing the same noise.

    ``ref`` is the specific nick the decision applies to, or '' for the whole
    category.
    """

    __tablename__ = 'treasury_anomaly_mute'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(
        db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True
    )
    code = db.Column(db.String(40), nullable=False)
    ref = db.Column(db.String(100), nullable=False, default='')
    created_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('clan_id', 'code', 'ref', name='uq_treasury_anomaly_mute'),
    )

    def to_dict(self):
        return {
            'code': self.code,
            'ref': self.ref or '',
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<TreasuryAnomalyMute clan={self.clan_id} {self.code}/{self.ref}>'
