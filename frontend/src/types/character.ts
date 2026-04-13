export interface QualityInfo {
  name: string;
  color: string;
  emoji: string;
}

export interface Skill {
  title: string;
  value: string;
}

export interface Enchant {
  type: string;
  value: string;
}

export interface EquipmentItem {
  title: string;
  quality: QualityInfo;
  level: string;
  trend: string;
  durability: string;
  skills: Skill[];
  skills_e: Skill[];
  enchants: Enchant[];
  set: string;
  rune: string;
  rune2: string;
  runicSetting: string;
  plate: string;
  lacquer: string;
  enhancement: string;
  symbols: string[];
  other: string;
}

export interface Medal {
  num: number;
  title: string;
  quality: QualityInfo;
  reputation: string;
  description: string;
}

export interface Effect {
  title: string;
  quality: QualityInfo;
  skills: Skill[];
  desc: string;
  image?: string;
  time_left?: string;
  time_left_sec?: number;
  category?: string;
  kind_id?: string;
  del_after_fight?: boolean;
  picture?: string;
}

export interface CharacterStats {
  name: string;
  race: string;
  sex: string;
  level: string;
  rank: string;
  clan: string;
  clan_rank: string;
  hp: string;
  mana: string;
}

export interface AnalysisResult {
  profile_closed?: boolean;
  name: string;
  race: string;
  rank: string;
  clan: string;
  clan_rank: string;
  wins: string;
  losses: string;
  winrate: number;
  kills: string;
  main_stats: Record<string, string>;
  combat_stats: Record<string, string>;
  magic_stats: Record<string, string>;
  social: Record<string, string>;
  achievements: Record<string, string>;
  great_battles: {
    wins: string;
    total: string;
    winrate: number;
  };
  combat_records: Record<string, string>;
  professions: Record<string, string>;
  equipment_by_kind: Record<string, EquipmentItem[]>;
  sets: Record<string, string[]>;
  medals: Medal[];
  permanent_effects: Effect[];
  temp_effects: Effect[];
  manor_location: string;
  manor_buildings: string[];
  closed_info?: {
    level: string;
    rank: string;
    picture: string;
    description: string;
    premium_level: string;
  };
}
