-- Migration: Create equipment_item table
-- Date: 2026-04-12

CREATE TABLE IF NOT EXISTS equipment_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    
    slot_type VARCHAR(50) NOT NULL,
    
    title VARCHAR(255) DEFAULT '',
    quality_name VARCHAR(50) DEFAULT '',
    quality_color VARCHAR(20) DEFAULT '',
    item_level VARCHAR(20) DEFAULT '',
    durability VARCHAR(50) DEFAULT '',
    
    set_name VARCHAR(100) DEFAULT '',
    
    rune VARCHAR(255) DEFAULT '',
    rune2 VARCHAR(255) DEFAULT '',
    runic_setting VARCHAR(255) DEFAULT '',
    plate VARCHAR(255) DEFAULT '',
    lacquer VARCHAR(255) DEFAULT '',
    enhancement VARCHAR(255) DEFAULT '',
    
    symbol_1 VARCHAR(100) DEFAULT '',
    symbol_2 VARCHAR(100) DEFAULT '',
    symbol_3 VARCHAR(100) DEFAULT '',
    symbol_4 VARCHAR(100) DEFAULT '',
    
    other TEXT DEFAULT '',
    
    skills_json TEXT DEFAULT '[]',
    skills_e_json TEXT DEFAULT '[]',
    enchants_json TEXT DEFAULT '[]',
    
    FOREIGN KEY (snapshot_id) REFERENCES character_snapshot(id)
);

CREATE INDEX IF NOT EXISTS idx_equipment_snapshot ON equipment_item(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_equipment_slot ON equipment_item(slot_type);