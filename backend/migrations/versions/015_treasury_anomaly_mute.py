"""treasury anomaly mutes — a treasurer's «это нормально» on a finding

Revision ID: 015_treasury_anomaly_mute
Revises: 014_treasury_month_close
Create Date: 2026-10-06
"""

import sqlalchemy as sa
from alembic import op

revision = '015_treasury_anomaly_mute'
down_revision = '014_treasury_month_close'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'treasury_anomaly_mute',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'clan_id',
            sa.Integer(),
            sa.ForeignKey('clan_info.clan_id'),
            nullable=False,
        ),
        sa.Column('code', sa.String(length=40), nullable=False),
        sa.Column('ref', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('app_user.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('clan_id', 'code', 'ref', name='uq_treasury_anomaly_mute'),
    )
    op.create_index(
        'ix_treasury_anomaly_mute_clan_id', 'treasury_anomaly_mute', ['clan_id']
    )


def downgrade():
    op.drop_index('ix_treasury_anomaly_mute_clan_id', table_name='treasury_anomaly_mute')
    op.drop_table('treasury_anomaly_mute')
