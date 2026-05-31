"""Add clan_membership_events table for membership change tracking

Revision ID: 004_add_membership_events
Revises: 003_add_clan_cookies
Create Date: 2026-05-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '004_add_membership_events'
down_revision: Union[str, None] = '003_add_clan_cookies'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('clan_membership_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('nick', sa.String(100), nullable=False),
        sa.Column('event_type', sa.String(10), nullable=False),
        sa.Column('event_date', sa.String(20), server_default=''),
        sa.Column('source', sa.String(10), server_default='diff'),
        sa.Column('leave_reason', sa.String(200), server_default=''),
        sa.Column('synced', sa.Boolean(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['clan_id'], ['clan_info.clan_id']),
    )
    op.create_index('ix_clan_membership_events_clan_id', 'clan_membership_events', ['clan_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_clan_membership_events_clan_id', table_name='clan_membership_events')
    op.drop_table('clan_membership_events')
