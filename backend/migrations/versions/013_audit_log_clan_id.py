"""audit_log.clan_id: attribute audit entries to a clan

The treasury journal («журнал корректировок») is per-clan, but audit_log had no
clan column, so entries could only be linked by guessing through target_id
(a clan id for imports, an operation id for edits). Add an explicit, indexed
clan_id; entries written before this migration stay NULL and simply do not show
up in a clan journal.

Revision ID: 013_audit_log_clan_id
Revises: 012_tax_carryover
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_audit_log_clan_id"
down_revision: Union[str, None] = "012_tax_carryover"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("clan_id", sa.Integer(), nullable=True))
    op.create_index("ix_audit_log_clan_id", "audit_log", ["clan_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_clan_id", table_name="audit_log")
    op.drop_column("audit_log", "clan_id")
