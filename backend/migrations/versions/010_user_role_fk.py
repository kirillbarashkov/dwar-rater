"""User.role string -> role_id FK.

`app_user.role` was a free-form string joined by name. This migration adds a
proper role_id FK, backfills it from the existing string, then drops the string
column. The User model exposes `role` as a property backed by role_id, so
existing `.role == 'admin'` reads keep working.

Revision ID: 010_user_role_fk
Revises: 009_add_rate_limit_user_id
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '010_user_role_fk'
down_revision: Union[str, None] = '009_add_rate_limit_user_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'app_user',
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('role.id'), nullable=True),
    )
    op.create_index('ix_app_user_role_id', 'app_user', ['role_id'])
    # Backfill from the legacy string column.
    op.execute(
        "UPDATE app_user SET role_id = role.id FROM role WHERE role.name = app_user.role"
    )
    op.drop_column('app_user', 'role')


def downgrade() -> None:
    op.add_column('app_user', sa.Column('role', sa.String(30), nullable=True))
    op.execute(
        "UPDATE app_user SET role = role.name FROM role WHERE role.id = app_user.role_id"
    )
    op.drop_index('ix_app_user_role_id', table_name='app_user')
    op.drop_column('app_user', 'role_id')