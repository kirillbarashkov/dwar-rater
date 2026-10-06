"""treasury_month_close: explicit «месяц закрыт» marker

`is_month_closed()` in the tax engine is only a calendar fact (the month has
passed); the treasurer's freeze is a decision, and it must be recorded. One row
per (clan, month, year) means "this month is closed": manual writes into it are
refused until the row is deleted by an explicit reopen. Both the close and the
reopen are written to audit_log, so history survives the row itself.

Revision ID: 014_treasury_month_close
Revises: 013_audit_log_clan_id
Create Date: 2026-10-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_treasury_month_close"
down_revision: Union[str, None] = "013_audit_log_clan_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "treasury_month_close",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "clan_id",
            sa.Integer(),
            sa.ForeignKey("clan_info.clan_id"),
            nullable=False,
        ),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=200), server_default=""),
        sa.Column(
            "closed_by", sa.Integer(), sa.ForeignKey("app_user.id"), nullable=True
        ),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "clan_id", "month", "year", name="uq_treasury_month_close"
        ),
    )
    op.create_index(
        "ix_treasury_month_close_clan_id", "treasury_month_close", ["clan_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_treasury_month_close_clan_id", table_name="treasury_month_close")
    op.drop_table("treasury_month_close")
