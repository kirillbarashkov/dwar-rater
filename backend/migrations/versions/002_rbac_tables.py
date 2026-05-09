"""Add RBAC tables and alter app_user for session-based auth

Revision ID: 002_rbac_tables
Revises: 001_initial_baseline
Create Date: 2026-04-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002_rbac_tables'
down_revision: Union[str, None] = '001_initial_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter app_user
    op.add_column('app_user', sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'))
    op.add_column('app_user', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    op.add_column('app_user', sa.Column('totp_secret', sa.String(64), nullable=True))
    op.add_column('app_user', sa.Column('must_change_password', sa.Boolean(), nullable=True, server_default='0'))

    # New tables
    op.create_table('permission',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feature', sa.String(50), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_deprecated', sa.Boolean(), nullable=True, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('feature', 'action', name='uq_permission_feature_action'),
    )

    op.create_table('role',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(30), nullable=False),
        sa.Column('label', sa.String(50), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=True, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    op.create_table('role_permission',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.String(10), nullable=False, server_default='none'),
        sa.ForeignKeyConstraint(['permission_id'], ['permission.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['role.id'], ),
        sa.PrimaryKeyConstraint('role_id', 'permission_id'),
    )

    op.create_table('session_token',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_session_token_token'), 'session_token', ['token'], unique=True)

    op.create_table('user_permission',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('level', sa.String(10), nullable=False, server_default='none'),
        sa.ForeignKeyConstraint(['permission_id'], ['permission.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'permission_id'),
    )

    op.create_table('audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('target_type', sa.String(30), nullable=True),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('audit_log')
    op.drop_table('user_permission')
    op.drop_index(op.f('ix_session_token_token'), table_name='session_token')
    op.drop_table('session_token')
    op.drop_table('role_permission')
    op.drop_table('role')
    op.drop_table('permission')
    op.drop_column('app_user', 'must_change_password')
    op.drop_column('app_user', 'totp_secret')
    op.drop_column('app_user', 'last_login_at')
    op.drop_column('app_user', 'is_active')
