from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Re-export RBAC models for convenience
from shared.rbac.models import (
    Permission,
    Role,
    RolePermission,
    UserPermission,
    SessionToken,
    AuditLog,
)
