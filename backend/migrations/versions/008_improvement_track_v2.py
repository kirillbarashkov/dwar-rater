"""Improvement Track v2: gap-close target columns

Adds target_type/target_ref, frozen source/target snapshots, power_gap
and phases_data to improvement_track. Backfills target_type='scenario'
for legacy tracks that reference a LevelingScenario.

Revision ID: 008_improvement_track_v2
Revises: 007_add_user_character_url
Create Date: 2026-08-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '008_improvement_track_v2'
down_revision: Union[str, None] = '007_add_user_character_url'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('improvement_track', sa.Column('target_type', sa.String(20), nullable=False, server_default='scenario'))
    op.add_column('improvement_track', sa.Column('target_ref', sa.String(512), nullable=True))
    op.add_column('improvement_track', sa.Column('source_snapshot', sa.Text(), nullable=True))
    op.add_column('improvement_track', sa.Column('target_snapshot', sa.Text(), nullable=True))
    op.add_column('improvement_track', sa.Column('power_gap', sa.Float(), nullable=True, server_default='0'))
    op.add_column('improvement_track', sa.Column('phases_data', sa.Text(), nullable=True))

    # Backfill: legacy tracks all reference a scenario
    op.execute(
        "UPDATE improvement_track "
        "SET target_type='scenario', target_ref=CAST(scenario_id AS TEXT) "
        "WHERE scenario_id IS NOT NULL"
    )

    op.create_index('ix_improvement_track_target_type', 'improvement_track', ['target_type'])


def downgrade() -> None:
    op.drop_index('ix_improvement_track_target_type', table_name='improvement_track')
    op.drop_column('improvement_track', 'phases_data')
    op.drop_column('improvement_track', 'power_gap')
    op.drop_column('improvement_track', 'target_snapshot')
    op.drop_column('improvement_track', 'source_snapshot')
    op.drop_column('improvement_track', 'target_ref')
    op.drop_column('improvement_track', 'target_type')
