"""Add character_nick and character_url to app_user

Stores the user's own game character binding so the "Персонаж" tab
can fetch and display the authenticated user's character data.

Revision ID: 007_add_user_character_url
Revises: 006_hash_session_tokens
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '007_add_user_character_url'
down_revision: Union[str, None] = '006_hash_session_tokens'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('app_user', sa.Column('character_nick', sa.String(100), nullable=True))
    op.add_column('app_user', sa.Column('character_url', sa.String(512), nullable=True))
    op.create_index('ix_app_user_character_nick', 'app_user', ['character_nick'])


def downgrade() -> None:
    op.drop_index('ix_app_user_character_nick', table_name='app_user')
    op.drop_column('app_user', 'character_url')
    op.drop_column('app_user', 'character_nick')
