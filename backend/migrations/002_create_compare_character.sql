-- Migration: Create compare_character table
-- Date: 2026-04-12

CREATE TABLE IF NOT EXISTS compare_character (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES user(id),
    character_name VARCHAR(255) NOT NULL,
    snapshot_data TEXT NOT NULL,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sort_order INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_compare_user ON compare_character(user_id);
CREATE INDEX IF NOT EXISTS idx_compare_order ON compare_character(sort_order);