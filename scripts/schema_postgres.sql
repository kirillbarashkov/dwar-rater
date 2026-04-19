-- PostgreSQL schema for Dwar Rater
-- Run this before migrate_to_postgres.py

CREATE TABLE IF NOT EXISTS app_user (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(64) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clan (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    created_by INTEGER NOT NULL REFERENCES app_user(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clan_member (
    id SERIAL PRIMARY KEY,
    clan_id INTEGER NOT NULL REFERENCES clan(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(clan_id, user_id)
);

CREATE TABLE IF NOT EXISTS clan_chat_room (
    id SERIAL PRIMARY KEY,
    clan_id INTEGER NOT NULL REFERENCES clan(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clan_chat_message (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES clan_chat_room(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS clan_info (
    id SERIAL PRIMARY KEY,
    clan_id INTEGER UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    logo_url VARCHAR(300) DEFAULT '',
    logo_big VARCHAR(300) DEFAULT '',
    logo_small VARCHAR(300) DEFAULT '',
    description TEXT DEFAULT '',
    leader_nick VARCHAR(100) DEFAULT '',
    leader_rank VARCHAR(100) DEFAULT '',
    clan_rank VARCHAR(100) DEFAULT '',
    clan_level INTEGER DEFAULT 0,
    step INTEGER DEFAULT 0,
    talents INTEGER DEFAULT 0,
    total_players INTEGER DEFAULT 0,
    current_players INTEGER DEFAULT 0,
    council TEXT DEFAULT '[]',
    clan_structure TEXT DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clan_info_clan_id ON clan_info(clan_id);

CREATE TABLE IF NOT EXISTS clan_member_info (
    id SERIAL PRIMARY KEY,
    clan_id INTEGER NOT NULL,
    nick VARCHAR(100) NOT NULL,
    icon VARCHAR(10) DEFAULT '',
    game_rank VARCHAR(100) DEFAULT '',
    level INTEGER DEFAULT 0,
    profession VARCHAR(100) DEFAULT '',
    profession_level INTEGER DEFAULT 0,
    clan_role VARCHAR(100) DEFAULT '',
    join_date VARCHAR(20) DEFAULT '',
    trial_until VARCHAR(20) DEFAULT '',
    is_deleted BOOLEAN DEFAULT FALSE,
    left_date VARCHAR(20) DEFAULT '',
    leave_reason VARCHAR(200) DEFAULT '',
    FOREIGN KEY (clan_id) REFERENCES clan_info(clan_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_clan_member_info_clan_id ON clan_member_info(clan_id);

CREATE TABLE IF NOT EXISTS treasury_operations (
    id SERIAL PRIMARY KEY,
    clan_id INTEGER NOT NULL,
    date VARCHAR(20) DEFAULT '',
    nick VARCHAR(100) DEFAULT '',
    operation_type VARCHAR(100) DEFAULT '',
    object_name VARCHAR(200) DEFAULT '',
    quantity INTEGER DEFAULT 0,
    compensation_flag BOOLEAN DEFAULT FALSE,
    compensation_comment VARCHAR(500) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (clan_id) REFERENCES clan_info(clan_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_treasury_operations_clan_id ON treasury_operations(clan_id);

CREATE TABLE IF NOT EXISTS character_cache (
    id SERIAL PRIMARY KEY,
    url VARCHAR(500) NOT NULL,
    data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_character_cache_url ON character_cache(url);

CREATE TABLE IF NOT EXISTS character_snapshot (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES app_user(id) ON DELETE SET NULL,
    character_url VARCHAR(500),
    character_name VARCHAR(100),
    data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_character_snapshot_user ON character_snapshot(user_id);

CREATE TABLE IF NOT EXISTS analysis_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES app_user(id) ON DELETE SET NULL,
    character_url VARCHAR(500),
    action VARCHAR(50),
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analysis_log_user ON analysis_log(user_id);

CREATE TABLE IF NOT EXISTS leveling_scenario (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name VARCHAR(100),
    description TEXT,
    scenario_data TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS improvement_track (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    character_nick VARCHAR(100),
    scenario_id INTEGER REFERENCES leveling_scenario(id) ON DELETE SET NULL,
    track_data TEXT,
    total_progress INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS compare_character (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    character_url VARCHAR(500),
    character_name VARCHAR(100),
    comparison_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);