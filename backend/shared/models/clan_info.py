import re
import json
import logging

_log = logging.getLogger(__name__)
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
        """Совет клана или [] — но повреждение поля видно в логе.

        A17: раньше здесь стоял голый `except:`, который ловил всё, включая
        KeyboardInterrupt/SystemExit, и молча отдавал пустой список: битое
        поле выглядело как «совета нет». Теперь ловятся только ожидаемые
        ошибки разбора, и они логируются.
        """
        try:
            return json.loads(self.council)
        except (json.JSONDecodeError, TypeError) as exc:
            _log.warning(
                'ClanInfo(%s).get_council: повреждённое поле council: %r (%s)',
                getattr(self, 'clan_id', '?'), self.council, exc,
            )
            return []

    def set_council(self, value):
        self.council = json.dumps(value, ensure_ascii=False)

    def get_clan_structure(self):
        """Структура клана или {} — повреждение поля логируется (A17)."""
        try:
            return json.loads(self.clan_structure)
        except (json.JSONDecodeError, TypeError) as exc:
            _log.warning(
                'ClanInfo(%s).get_clan_structure: повреждённое поле clan_structure: %r (%s)',
                getattr(self, 'clan_id', '?'), self.clan_structure, exc,
            )
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
    # A12: те же составные индексы, что создаёт миграция 018. Держим модель и
    # миграции в согласии: create_all() (dev/SQLite и тестовая БД) не должен
    # давать схему, отличную от прод. Уникального ключа нет намеренно — импорт
    # пишет вторую строку при другой сумме (см. docstring миграции).
    __table_args__ = (
        db.Index('ix_treasury_operations_clan_date', 'clan_id', 'date'),
        db.Index('ix_treasury_operations_clan_nick', 'clan_id', 'nick'),
    )
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True)
    date = db.Column(db.String(20), default='')
    nick = db.Column(db.String(100), default='')
    operation_type = db.Column(db.String(100), default='')
    object_name = db.Column(db.String(200), default='')
    quantity = db.Column(db.Integer, default=0)
    compensation_flag = db.Column(db.Boolean, default=False)
    compensation_comment = db.Column(db.String(500), default='')
    # Классификация: денормализованное отражение подтверждённых пар. Источник истины —
    # TreasuryOperationPair, эти поля пересчитывает сервис. По умолчанию tax, поэтому
    # до классификации цифры не меняются.
    op_class = db.Column(db.String(20), default='tax')       # tax | neutral
    class_kind = db.Column(db.String(20), default='')        # exchange | loan | ''
    class_source = db.Column(db.String(20), default='')      # auto | manual | ''
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    clan = db.relationship('ClanInfo', foreign_keys=[clan_id], primaryjoin='TreasuryOperation.clan_id == ClanInfo.clan_id')

    def __repr__(self):
        return f'<TreasuryOperation {self.date} {self.nick}>'


class TreasuryOperationPair(db.Model):
    """Пара операций казны: обмен или долг.

    Источник истины для классификации. Пока пара не подтверждена казначеем, обе
    операции считаются обычными (`op_class = tax`) — молча в нейтральные ничего не
    переводится, автоматика лишь предлагает кандидатов.
    """

    __tablename__ = 'treasury_operation_pair'
    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, db.ForeignKey('clan_info.clan_id'), nullable=False, index=True)
    first_op_id = db.Column(db.Integer, db.ForeignKey('treasury_operations.id'), nullable=False)
    second_op_id = db.Column(db.Integer, db.ForeignKey('treasury_operations.id'), nullable=True)
    kind = db.Column(db.String(20), default='exchange')      # exchange | loan
    status = db.Column(db.String(20), default='candidate')   # candidate | confirmed | rejected
    comment = db.Column(db.String(500), default='')
    created_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    first_op = db.relationship('TreasuryOperation', foreign_keys=[first_op_id])
    second_op = db.relationship('TreasuryOperation', foreign_keys=[second_op_id])

    def __repr__(self):
        return f'<TreasuryOperationPair {self.kind} {self.status} {self.first_op_id}/{self.second_op_id}>'


class TreasuryExclusionGroup(db.Model):
    """Группа исключений казны.

    Админ или казначей сам заводит группы, называет их и наполняет типами ресурсов.
    Дальше ресурсы из группы либо выпадают из аналитики казны целиком (`exclude`),
    либо становятся нейтральными (`neutral`) — второе оставляет их видимыми
    в журнале и истории.
    """

    __tablename__ = 'treasury_exclusion_group'

    id = db.Column(db.Integer, primary_key=True)
    clan_id = db.Column(db.Integer, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    # 'exclude' — не попадать ни в один отчёт казны; 'neutral' — не сдача, но видно.
    mode = db.Column(db.String(20), nullable=False, default='exclude')
    comment = db.Column(db.String(500), default='')
    created_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    rules = db.relationship(
        'TreasuryExclusionRule',
        backref='group',
        cascade='all, delete-orphan',
        lazy='selectin',
    )


class TreasuryExclusionRule(db.Model):
    """Правило группы: сопоставление по началу названия ресурса.

    «Сущность» ловит и «Сущность кретса», и «Сущность корра» — так решил владелец.
    """

    __tablename__ = 'treasury_exclusion_rule'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(
        db.Integer,
        db.ForeignKey('treasury_exclusion_group.id'),
        nullable=False,
        index=True,
    )
    prefix = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TreasuryPairRevision(db.Model):
    """Лог корректировок пары.

    Требование владельца: история изменений пары сохраняется. Форма повторяет
    `audit_log`, чтобы не заводить второй механизм истории в проекте.
    """

    __tablename__ = 'treasury_pair_revision'
    id = db.Column(db.Integer, primary_key=True)
    pair_id = db.Column(db.Integer, db.ForeignKey('treasury_operation_pair.id'), nullable=False, index=True)
    changed_by = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    old_value = db.Column(db.Text, default='')
    new_value = db.Column(db.Text, default='')
    comment = db.Column(db.String(500), default='')

    def __repr__(self):
        return f'<TreasuryPairRevision pair={self.pair_id}>'


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
