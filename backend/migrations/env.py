import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.models import db
from shared.models.user import User
from shared.models.clan import Clan, ClanMember, ClanChatRoom, ClanChatMessage
from shared.models.clan_info import ClanInfo, ClanMemberInfo, TreasuryOperation
from shared.models.character_snapshot import CharacterSnapshot
from shared.models.character_cache import CharacterCache
from shared.models.analysis_log import AnalysisLog
from shared.models.leveling_scenario import LevelingScenario
from shared.models.improvement_track import ImprovementTrack
from shared.models.compare_character import CompareCharacter
from shared.models.equipment_item import EquipmentItem
from shared.models.closed_profile import ClosedProfile
from shared.rbac.models import Permission, Role, RolePermission, UserPermission, SessionToken, AuditLog

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.metadata

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    config.set_main_option('sqlalchemy.url', DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
