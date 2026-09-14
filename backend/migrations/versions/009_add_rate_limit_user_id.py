"""Per-user rate limiting: add user_id to rate_limit.

Anonymous requests are keyed by ip_address (unchanged); authenticated requests
are now keyed by user_id so one user cannot be throttled by a shared NAT IP and
a malicious actor cannot evade the limit simply by rotating IPs.

Revision ID: 009_add_rate_limit_user_id
Revises: 008_improvement_track_v2
Create Date: 2026-09-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '009_add_rate_limit_user_id'
down_revision: Union[str, None] = '008_improvement_track_v2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rate_limit', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index(
        'ix_rate_limit_user_window', 'rate_limit', ['user_id', 'window_start']
    )


def downgrade() -> None:
    op.drop_index('ix_rate_limit_user_window', table_name='rate_limit')
    op.drop_column('rate_limit', 'user_id')