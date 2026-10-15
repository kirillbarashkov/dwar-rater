"""Группы исключений казны: ресурсы, которые не считаем.

Revision ID: 017
Revises: 016

Владелец попросил интерфейс для групп исключений и завести «Сущности» сразу:
операции с ними не должны попадать в аналитику казны.
"""

import sqlalchemy as sa
from alembic import op

revision = '017_treasury_exclusion_groups'
down_revision = '016_treasury_operation_pair'
branch_labels = None
depends_on = None

# Клан, для которого заводится стартовая группа.
SEED_CLAN_ID = 2315


def upgrade():
    # Идемпотентность обязательна: при старте бэкенда миграции запускают несколько
    # воркеров, файловый лок разводит их не всегда. Без if_not_exists второй проход
    # падает на «already exists» и откатывает транзакцию вместе с записью версии —
    # таблицы остаются, а alembic_version нет.
    op.create_table(
        'treasury_exclusion_group',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('mode', sa.String(20), nullable=False, server_default='exclude'),
        sa.Column('comment', sa.String(500), server_default=''),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('app_user.id'), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true()),
        if_not_exists=True,
    )
    op.create_index(
        'ix_treasury_exclusion_group_clan_id',
        'treasury_exclusion_group',
        ['clan_id'],
        if_not_exists=True,
    )

    op.create_table(
        'treasury_exclusion_rule',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'group_id',
            sa.Integer(),
            sa.ForeignKey('treasury_exclusion_group.id'),
            nullable=False,
        ),
        sa.Column('prefix', sa.String(200), nullable=False),
        sa.Column('created_at', sa.DateTime()),
        if_not_exists=True,
    )
    op.create_index(
        'ix_treasury_exclusion_rule_group_id',
        'treasury_exclusion_rule',
        ['group_id'],
        if_not_exists=True,
    )

    op.execute(
        sa.text(
            "INSERT INTO treasury_exclusion_group "
            "(clan_id, name, mode, comment, is_active, created_at) "
            "SELECT :clan, 'Сущности', 'exclude', "
            "'Сущности (кретса, корра и прочие) — не участвуют в аналитике казны', "
            "true, NOW() "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM treasury_exclusion_group "
            "  WHERE clan_id = :clan AND name = 'Сущности'"
            ")"
        ).bindparams(clan=SEED_CLAN_ID)
    )
    op.execute(
        sa.text(
            "INSERT INTO treasury_exclusion_rule (group_id, prefix, created_at) "
            "SELECT id, 'Сущность', NOW() FROM treasury_exclusion_group "
            "WHERE clan_id = :clan AND name = 'Сущности' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM treasury_exclusion_rule r "
            "  WHERE r.group_id = treasury_exclusion_group.id AND r.prefix = 'Сущность'"
            ")"
        ).bindparams(clan=SEED_CLAN_ID)
    )


def downgrade():
    op.drop_index(
        'ix_treasury_exclusion_rule_group_id', table_name='treasury_exclusion_rule'
    )
    op.drop_table('treasury_exclusion_rule')
    op.drop_index(
        'ix_treasury_exclusion_group_clan_id', table_name='treasury_exclusion_group'
    )
    op.drop_table('treasury_exclusion_group')
