from datetime import datetime, timezone
from shared.models import db


class User(db.Model):
    __tablename__ = 'app_user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    # Source of truth for the role (was a free-form string, now an FK to role.id).
    role_id = db.Column(
        db.Integer, db.ForeignKey('role.id'), nullable=True, index=True
    )
    is_active = db.Column(db.Boolean, default=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    totp_secret = db.Column(db.String(64), nullable=True)
    must_change_password = db.Column(db.Boolean, default=False)
    character_nick = db.Column(db.String(100), nullable=True, index=True)
    character_url = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    role_obj = db.relationship('Role', lazy='select', uselist=False)
    sessions = db.relationship('SessionToken', back_populates='user', lazy='dynamic')
    individual_permissions = db.relationship('UserPermission', back_populates='user', lazy='dynamic')
    audit_entries = db.relationship('AuditLog', back_populates='user', lazy='dynamic')

    @property
    def role(self):
        """Role name, backed by the role_id FK (keeps legacy `.role` reads working)."""
        return self.role_obj.name if self.role_obj else None

    @role.setter
    def role(self, value):
        from shared.rbac.models import Role
        if value is None:
            self.role_obj = None
        elif isinstance(value, Role):
            self.role_obj = value
        else:
            self.role_obj = Role.query.filter_by(name=str(value)).first()

    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'is_active': self.is_active,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'must_change_password': self.must_change_password,
            'character_nick': self.character_nick,
            'character_url': self.character_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }