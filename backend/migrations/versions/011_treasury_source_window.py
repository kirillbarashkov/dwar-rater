"""treasury_source_window: remember the oldest treasury date dwar still serves

dwar purges operations after roughly six months without telling anyone: the
report just ends and requests for older periods return nothing. The app learns
the boundary from import attempts and stores it per clan so the UI can tag
stale periods and freeze their selection.

Revision ID: 011_treasury_source_window
Revises: 010_user_role_fk
Create Date: 2026-10-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_treasury_source_window"
down_revision: Union[str, None] = "010_user_role_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "treasury_source_window",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clan_id", sa.Integer(), nullable=False),
        sa.Column("oldest_date", sa.String(length=20), nullable=True),
        sa.Column("total_pages", sa.Integer(), nullable=True),
        sa.Column("learned_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_treasury_source_window_clan_id",
        "treasury_source_window",
        ["clan_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_treasury_source_window_clan_id", table_name="treasury_source_window")
    op.drop_table("treasury_source_window")
