"""Add clan_cookies table for treasury auto-import authentication

Revision ID: 003_add_clan_cookies
Revises: 002_rbac_tables
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003_add_clan_cookies'
down_revision: Union[str, None] = '002_rbac_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('clan_cookies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('cookie_string', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), server_default='1', nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_clan_cookies_clan_id', 'clan_cookies', ['clan_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_clan_cookies_clan_id', table_name='clan_cookies')
    op.drop_table('clan_cookies')
