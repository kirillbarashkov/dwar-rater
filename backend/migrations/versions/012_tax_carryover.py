"""tax_carryover: review ledger for tax overpayments carried to the next month

An overpayment is proposed automatically (engine: shared/services/tax_engine.py)
and stays ``pending`` until a treasurer confirms or cancels it. It is kept
outside ``treasury_operations`` on purpose: cancelling must not touch the
treasury, and a cancelled proposal has to survive recomputation.

Revision ID: 012_tax_carryover
Revises: 011_treasury_source_window
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_tax_carryover"
down_revision: Union[str, None] = "011_treasury_source_window"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tax_carryover",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clan_id", sa.Integer(), nullable=False),
        sa.Column("nick", sa.String(length=100), nullable=False),
        sa.Column("source_month", sa.Integer(), nullable=False),
        sa.Column("source_year", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="pending"),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["clan_id"], ["clan_info.clan_id"]),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "clan_id", "nick", "source_month", "source_year",
            name="uq_tax_carryover_source",
        ),
    )
    op.create_index("ix_tax_carryover_clan_id", "tax_carryover", ["clan_id"])


def downgrade() -> None:
    op.drop_index("ix_tax_carryover_clan_id", table_name="tax_carryover")
    op.drop_table("tax_carryover")
