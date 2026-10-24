"""A12: составные индексы казны по парам, по которым реально идёт фильтрация.

Revision ID: 018
Revises: 017

У `treasury_operations` был только одиночный индекс по `clan_id`, а запросы
фильтруют по `clan_id + date` (периоды) и `clan_id + nick` (участник). При
десятках тысяч операций это последовательные сканы.

**Уникальный индекс сознательно НЕ создаётся.** Рекомендация аудита предлагала
уникальный ключ `(clan_id, date, nick, operation_type, object_name)`, но импорт
казны намеренно пишет ВТОРУЮ строку с тем же ключом, когда сумма отличается
(`features/clan_info/routes.py`, ветка «Op will insert NEW (different qty)»):
двар легитимно повторяет одинаковые платежи. Уникальный индекс отклонил бы такие
вставки и сломал импорт. Для защиты от дублей в проекте уже есть `replace_range`
и per-key дедупликация в коде.
"""

from alembic import op

revision = '018_treasury_operation_indexes'
down_revision = '017_treasury_exclusion_groups'
branch_labels = None
depends_on = None


def upgrade():
    # Идемпотентность обязательна: при старте бэкенда миграции запускают
    # несколько воркеров, файловый лок разводит их не всегда. Повторный
    # CREATE INDEX без IF NOT EXISTS упал бы на «already exists» и откатил
    # транзакцию вместе с записью версии.
    op.create_index(
        'ix_treasury_operations_clan_date',
        'treasury_operations',
        ['clan_id', 'date'],
        if_not_exists=True,
    )
    op.create_index(
        'ix_treasury_operations_clan_nick',
        'treasury_operations',
        ['clan_id', 'nick'],
        if_not_exists=True,
    )


def downgrade():
    op.drop_index(
        'ix_treasury_operations_clan_nick',
        table_name='treasury_operations',
        if_exists=True,
    )
    op.drop_index(
        'ix_treasury_operations_clan_date',
        table_name='treasury_operations',
        if_exists=True,
    )
