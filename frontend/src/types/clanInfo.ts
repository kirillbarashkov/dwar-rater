export interface ClanInfoData {
  clan_id: number;
  name: string;
  logo_url: string;
  description: string;
  leader_nick: string;
  leader_rank: string;
  clan_rank: string;
  clan_level: number;
  step: number;
  talents: number;
  updated_at: string;
}

export interface ClanMemberData {
  id?: number;
  nick: string;
  game_rank: string;
  level: number;
  profession: string;
  profession_level: number;
  clan_role: string;
  join_date: string;
  trial_until: string;
}
