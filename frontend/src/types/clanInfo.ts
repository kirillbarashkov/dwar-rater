export interface ClanInfoData {
  clan_id: number;
  name: string;
  logo_url: string;
  logo_big: string;
  logo_small: string;
  description: string;
  leader_nick: string;
  leader_rank: string;
  clan_rank: string;
  clan_level: number;
  step: number;
  talents: number;
  total_players: number;
  current_players: number;
  council: string[];
  clan_structure: ClanStructure;
  structure_warning?: string;
  updated_at: string;
}

export interface ClanStructure {
  leader?: {
    nick: string;
    description: string;
  };
  deputies?: Array<{
    nick: string;
    description: string;
  }>;
  council?: Array<{
    nick: string;
    description: string;
  }>;
  commander?: {
    nick: string;
    description: string;
  };
  has_members?: boolean;
  council_slots?: number;
}

export interface ClanMemberData {
  id?: number;
  nick: string;
  icon?: string;
  game_rank: string;
  level: number;
  profession: string;
  profession_level: number;
  clan_role: string;
  join_date: string;
  trial_until: string;
  is_deleted?: boolean;
  left_date?: string;
  leave_reason?: string;
}

export interface LeftMemberData {
  id: number;
  nick: string;
  icon?: string;
  game_rank: string;
  level: number;
  profession: string;
  profession_level: number;
  clan_role: string;
  join_date: string;
  left_date: string;
  leave_reason: string;
}

export interface TreasuryOperationData {
  id: number;
  date: string;
  nick: string;
  operation_type: string;
  object_name: string;
  quantity: number;
  compensation_flag: boolean;
  compensation_comment: string;
}
