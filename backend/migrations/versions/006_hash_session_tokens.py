"""Hash session tokens in storage (S1 security fix)

Replaces plain-text token column with token_hash (sha256).
Existing tokens are migrated (hashed) — users keep their sessions.

Revision ID: 006_hash_session_tokens
Revises: 005_add_level_change_events
Create Date: 2026-07-06

Note: Migrations 004 and 005 both originate from 003 (branching).
Both their tables exist in production. This merge point consolidates
them and applies the session-token hashing security fix.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import hashlib

revision: str = '006_hash_session_tokens'
down_revision: Union[str, None] = ('004_add_membership_events', '005_add_level_change_events')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add token_hash column (nullable for backfill)
    op.add_column('session_token', sa.Column('token_hash', sa.String(64), nullable=True))

    # Step 2: Backfill — hash existing plain-text tokens
    connection = op.get_bind()
    rows = connection.execute(sa.text('SELECT id, token FROM session_token')).fetchall()
    for row in rows:
        token_hash = hashlib.sha256(row[1].encode()).hexdigest()
        connection.execute(
            sa.text('UPDATE session_token SET token_hash = :hash WHERE id = :id'),
            {'hash': token_hash, 'id': row[0]}
        )

    # Step 3: Make non-nullable + create unique index
    op.alter_column('session_token', 'token_hash', nullable=False)
    op.create_index('ix_session_token_token_hash', 'session_token', ['token_hash'], unique=True)

    # Step 4: Drop old plain-text token column and its index
    op.drop_index(op.f('ix_session_token_token'), table_name='session_token')
    op.drop_column('session_token', 'token')


def downgrade() -> None:
    # Restore plain-text token column
    op.add_column('session_token', sa.Column('token', sa.String(64), nullable=True))
    op.create_index(op.f('ix_session_token_token'), 'session_token', ['token'], unique=True)

    # NOTE: cannot un-hash tokens — they are one-way sha256.
    # Downgrade restores column structure; all existing sessions are invalidated.
    # Users must re-login after downgrade.
    connection = op.get_bind()
    connection.execute(sa.text(
        'UPDATE session_token SET token = token_hash WHERE token IS NULL'
    ))
    op.alter_column('session_token', 'token', nullable=False)

    op.drop_index('ix_session_token_token_hash', table_name='session_token')
    op.drop_column('session_token', 'token_hash')
