"""Add clan_level_change_events table for tracking member level changes

Revision ID: 005_add_level_change_events
Revises: 003_add_clan_cookies
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '005_add_level_change_events'
down_revision: Union[str, None] = '003_add_clan_cookies'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('clan_level_change_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('nick', sa.String(length=100), nullable=False),
        sa.Column('old_level', sa.Integer(), server_default='0', nullable=True),
        sa.Column('new_level', sa.Integer(), nullable=False),
        sa.Column('event_date', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_clan_level_change_events_clan_id', 'clan_level_change_events', ['clan_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_clan_level_change_events_clan_id', table_name='clan_level_change_events')
    op.drop_table('clan_level_change_events')
