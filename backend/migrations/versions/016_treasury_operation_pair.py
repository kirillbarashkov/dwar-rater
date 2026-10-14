"""treasury operation pairs — обмены и долги как пары событий

Revision ID: 016_treasury_operation_pair
Revises: 015_treasury_anomaly_mute
Create Date: 2026-10-11

Этап 1 плана классификации: модель выкатывается отдельно от изменения расчётов.
`op_class` по умолчанию 'tax', поэтому существующие и новые операции остаются
учитываемыми, пока казначей не подтвердил пару. Цифры не меняются.
"""

import sqlalchemy as sa
from alembic import op

revision = '016_treasury_operation_pair'
down_revision = '015_treasury_anomaly_mute'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'treasury_operation_pair',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'clan_id',
            sa.Integer(),
            sa.ForeignKey('clan_info.clan_id'),
            nullable=False,
        ),
        sa.Column(
            'first_op_id',
            sa.Integer(),
            sa.ForeignKey('treasury_operations.id'),
            nullable=False,
        ),
        sa.Column(
            'second_op_id',
            sa.Integer(),
            sa.ForeignKey('treasury_operations.id'),
            nullable=True,
        ),
        sa.Column('kind', sa.String(length=20), nullable=False, server_default='exchange'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='candidate'),
        sa.Column('comment', sa.String(length=500), server_default=''),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('app_user.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_by', sa.Integer(), sa.ForeignKey('app_user.id'), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
    )
    op.create_index(
        'ix_treasury_operation_pair_clan_id', 'treasury_operation_pair', ['clan_id']
    )

    op.create_table(
        'treasury_pair_revision',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'pair_id',
            sa.Integer(),
            sa.ForeignKey('treasury_operation_pair.id'),
            nullable=False,
        ),
        sa.Column('changed_by', sa.Integer(), sa.ForeignKey('app_user.id'), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=True),
        sa.Column('old_value', sa.Text(), server_default=''),
        sa.Column('new_value', sa.Text(), server_default=''),
        sa.Column('comment', sa.String(length=500), server_default=''),
    )
    op.create_index(
        'ix_treasury_pair_revision_pair_id', 'treasury_pair_revision', ['pair_id']
    )

    op.add_column(
        'treasury_operations',
        sa.Column('op_class', sa.String(length=20), nullable=False, server_default='tax'),
    )
    op.add_column(
        'treasury_operations',
        sa.Column('class_kind', sa.String(length=20), server_default=''),
    )
    op.add_column(
        'treasury_operations',
        sa.Column('class_source', sa.String(length=20), server_default=''),
    )


def downgrade():
    op.drop_column('treasury_operations', 'class_source')
    op.drop_column('treasury_operations', 'class_kind')
    op.drop_column('treasury_operations', 'op_class')
    op.drop_index('ix_treasury_pair_revision_pair_id', table_name='treasury_pair_revision')
    op.drop_table('treasury_pair_revision')
    op.drop_index(
        'ix_treasury_operation_pair_clan_id', table_name='treasury_operation_pair'
    )
    op.drop_table('treasury_operation_pair')
