from shared.models import db
from datetime import datetime, timezone


class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    feature = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_deprecated = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint('feature', 'action', name='uq_permission_feature_action'),
    )

    roles = db.relationship('RolePermission', back_populates='permission', lazy='dynamic')
    user_perms = db.relationship('UserPermission', back_populates='permission', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'feature': self.feature,
            'action': self.action,
            'label': self.label,
            'description': self.description,
            'is_deprecated': self.is_deprecated,
        }


class Role(db.Model):
    __tablename__ = 'role'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)
    label = db.Column(db.String(50), nullable=False)
    is_system = db.Column(db.Boolean, default=False)

    permissions = db.relationship('RolePermission', back_populates='role', lazy='select')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'label': self.label,
            'is_system': self.is_system,
        }

    def get_users(self):
        """Get users with this role (User.role is a string, not FK)."""
        from shared.models.user import User
        return User.query.filter_by(role=self.name)


class RolePermission(db.Model):
    __tablename__ = 'role_permission'

    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), primary_key=True)
    level = db.Column(db.String(10), nullable=False, default='none')

    role = db.relationship('Role', back_populates='permissions')
    permission = db.relationship('Permission', back_populates='roles')

    def to_dict(self):
        return {
            'role_id': self.role_id,
            'permission_id': self.permission_id,
            'level': self.level,
        }


class UserPermission(db.Model):
    __tablename__ = 'user_permission'

    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), primary_key=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), primary_key=True)
    level = db.Column(db.String(10), nullable=False, default='none')

    user = db.relationship('User', back_populates='individual_permissions')
    permission = db.relationship('Permission', back_populates='user_perms')

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'permission_id': self.permission_id,
            'level': self.level,
        }


class SessionToken(db.Model):
    __tablename__ = 'session_token'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='sessions')

    @property
    def is_expired(self):
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now > expires

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'expires_at': self.expires_at.isoformat(),
            'created_at': self.created_at.isoformat(),
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(30), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='audit_entries')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'system',
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat(),
        }
