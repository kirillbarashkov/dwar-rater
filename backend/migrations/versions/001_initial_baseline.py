"""Initial baseline — create all tables from current models

Revision ID: 001_initial_baseline
Revises:
Create Date: 2025-04-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('app_user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )

    op.create_table('character_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nick', sa.String(length=100), nullable=False),
        sa.Column('raw_data', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nick'),
    )
    op.create_index(op.f('ix_character_cache_nick'), 'character_cache', ['nick'], unique=False)

    op.create_table('clan',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    op.create_table('clan_info',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('logo_url', sa.String(length=300), nullable=True),
        sa.Column('logo_big', sa.String(length=300), nullable=True),
        sa.Column('logo_small', sa.String(length=300), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('leader_nick', sa.String(length=100), nullable=True),
        sa.Column('leader_rank', sa.String(length=100), nullable=True),
        sa.Column('clan_rank', sa.String(length=100), nullable=True),
        sa.Column('clan_level', sa.Integer(), nullable=True),
        sa.Column('step', sa.Integer(), nullable=True),
        sa.Column('talents', sa.Integer(), nullable=True),
        sa.Column('total_players', sa.Integer(), nullable=True),
        sa.Column('current_players', sa.Integer(), nullable=True),
        sa.Column('council', sa.Text(), nullable=True),
        sa.Column('clan_structure', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clan_id'),
    )
    op.create_index(op.f('ix_clan_info_clan_id'), 'clan_info', ['clan_id'], unique=False)

    op.create_table('character_snapshot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('nick', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('race', sa.String(length=100), nullable=True),
        sa.Column('rank', sa.String(length=100), nullable=True),
        sa.Column('clan', sa.String(length=200), nullable=True),
        sa.Column('snapshot_name', sa.String(length=200), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(), nullable=True),
        sa.Column('snapshot_data', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_character_snapshot_nick'), 'character_snapshot', ['nick'], unique=False)
    op.create_index(op.f('ix_character_snapshot_analyzed_at'), 'character_snapshot', ['analyzed_at'], unique=False)
    op.create_index(op.f('ix_character_snapshot_user_id'), 'character_snapshot', ['user_id'], unique=False)

    op.create_table('clan_chat_room',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['clan_id'], ['clan.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('clan_member',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['clan_id'], ['clan.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clan_id', 'user_id'),
    )

    op.create_table('clan_member_info',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('nick', sa.String(length=100), nullable=False),
        sa.Column('icon', sa.String(length=10), nullable=True),
        sa.Column('game_rank', sa.String(length=100), nullable=True),
        sa.Column('level', sa.Integer(), nullable=True),
        sa.Column('profession', sa.String(length=100), nullable=True),
        sa.Column('profession_level', sa.Integer(), nullable=True),
        sa.Column('clan_role', sa.String(length=100), nullable=True),
        sa.Column('join_date', sa.String(length=20), nullable=True),
        sa.Column('trial_until', sa.String(length=20), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.Column('left_date', sa.String(length=20), nullable=True),
        sa.Column('leave_reason', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['clan_id'], ['clan_info.clan_id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_clan_member_info_clan_id'), 'clan_member_info', ['clan_id'], unique=False)

    op.create_table('closed_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nick', sa.String(length=100), nullable=False),
        sa.Column('first_seen_closed', sa.DateTime(), nullable=False),
        sa.Column('last_checked', sa.DateTime(), nullable=True),
        sa.Column('check_count', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('level', sa.String(length=20), nullable=True),
        sa.Column('rank', sa.String(length=20), nullable=True),
        sa.Column('clan', sa.String(length=200), nullable=True),
        sa.Column('snapshot_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_scanned_open', sa.Boolean(), nullable=True),
        sa.Column('scanned_open_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['snapshot_id'], ['character_snapshot.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nick'),
    )
    op.create_index(op.f('ix_closed_profiles_nick'), 'closed_profiles', ['nick'], unique=False)

    op.create_table('clan_chat_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('room_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['room_id'], ['clan_chat_room.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('leveling_scenario',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('scenario_data', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('rate_limit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('window_start', sa.Integer(), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rate_limit_ip_window', 'rate_limit', ['ip_address', 'window_start'], unique=False)

    op.create_table('treasury_operations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('clan_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.String(length=20), nullable=True),
        sa.Column('nick', sa.String(length=100), nullable=True),
        sa.Column('operation_type', sa.String(length=100), nullable=True),
        sa.Column('object_name', sa.String(length=200), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('compensation_flag', sa.Boolean(), nullable=True),
        sa.Column('compensation_comment', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['clan_id'], ['clan_info.clan_id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_treasury_operations_clan_id'), 'treasury_operations', ['clan_id'], unique=False)

    op.create_table('analysis_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('nick', sa.String(length=100), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('snapshot_id', sa.Integer(), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
        sa.ForeignKeyConstraint(['snapshot_id'], ['character_snapshot.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_analysis_log_nick'), 'analysis_log', ['nick'], unique=False)
    op.create_index(op.f('ix_analysis_log_analyzed_at'), 'analysis_log', ['analyzed_at'], unique=False)
    op.create_index(op.f('ix_analysis_log_user_id'), 'analysis_log', ['user_id'], unique=False)

    op.create_table('compare_character',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('character_name', sa.String(length=255), nullable=False),
        sa.Column('snapshot_data', sa.Text(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_compare_character_user_id'), 'compare_character', ['user_id'], unique=False)

    op.create_table('equipment_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('snapshot_id', sa.Integer(), nullable=False),
        sa.Column('slot_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('quality_name', sa.String(length=50), nullable=True),
        sa.Column('quality_color', sa.String(length=20), nullable=True),
        sa.Column('item_level', sa.String(length=20), nullable=True),
        sa.Column('durability', sa.String(length=50), nullable=True),
        sa.Column('set_name', sa.String(length=100), nullable=True),
        sa.Column('rune', sa.String(length=255), nullable=True),
        sa.Column('rune2', sa.String(length=255), nullable=True),
        sa.Column('runic_setting', sa.String(length=255), nullable=True),
        sa.Column('plate', sa.String(length=255), nullable=True),
        sa.Column('lacquer', sa.String(length=255), nullable=True),
        sa.Column('enhancement', sa.String(length=255), nullable=True),
        sa.Column('symbol_1', sa.String(length=100), nullable=True),
        sa.Column('symbol_2', sa.String(length=100), nullable=True),
        sa.Column('symbol_3', sa.String(length=100), nullable=True),
        sa.Column('symbol_4', sa.String(length=100), nullable=True),
        sa.Column('other', sa.Text(), nullable=True),
        sa.Column('skills_json', sa.Text(), nullable=True),
        sa.Column('skills_e_json', sa.Text(), nullable=True),
        sa.Column('enchants_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['snapshot_id'], ['character_snapshot.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_equipment_item_snapshot_id'), 'equipment_item', ['snapshot_id'], unique=False)

    op.create_table('improvement_track',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('character_nick', sa.String(length=100), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=True),
        sa.Column('track_data', sa.Text(), nullable=False),
        sa.Column('total_progress', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['app_user.id'], ),
        sa.ForeignKeyConstraint(['scenario_id'], ['leveling_scenario.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('improvement_track')
    op.drop_table('equipment_item')
    op.drop_table('compare_character')
    op.drop_table('analysis_log')
    op.drop_table('treasury_operations')
    op.drop_table('rate_limit')
    op.drop_table('leveling_scenario')
    op.drop_table('clan_chat_message')
    op.drop_table('closed_profiles')
    op.drop_table('clan_member_info')
    op.drop_table('clan_member')
    op.drop_table('clan_chat_room')
    op.drop_table('character_snapshot')
    op.drop_table('clan_info')
    op.drop_table('clan')
    op.drop_table('character_cache')
    op.drop_table('app_user')
