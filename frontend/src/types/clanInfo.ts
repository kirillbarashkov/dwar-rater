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
  /**
   * Role assigned in "Структура клана" (ui_ prefix = app-side, not from
   * dwar.ru). null when the member is not part of the structure — in that
   * case the UI falls back to clan_role.
   */
  ui_structure_role?: string | null;
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

/** Boundary of the treasury history dwar still serves (learned, not probed). */
export interface SourceWindow {
  oldest_available_date: string;
  total_pages: number;
  learned_at: string | null;
}

export interface DateCoverage {
  years: Record<string, {
    months: Record<string, {
      days: string[];
      total_ops: number;
    }>;
    total_ops: number;
  }>;
  total_dates_with_data: number;
  total_operations: number;
  earliest_date: string | null;
  latest_date: string | null;
  source_window?: SourceWindow | null;
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

export interface MembershipEvent {
  id: number;
  nick: string;
  event_type: 'joined' | 'left';
  event_date: string;
  source: 'diff' | 'history';
  leave_reason?: string;
  synced: boolean;
  created_at: string;
}

export interface MemberDiffResult {
  joined: Partial<ClanMemberData>[];
  left: {
    nick: string;
    last_seen_level?: number;
    last_seen_role?: string;
  }[];
}

/**
 * Tax overpayment carry-over ledger. A proposal is created automatically for a
 * closed month and stays `pending` until a treasurer confirms or cancels it;
 * the credit then applies to the following month. `source_month`/`source_year`
 * are the month the member overpaid — the receiving month is derived.
 */
export type TaxCarryoverStatus = 'pending' | 'confirmed' | 'cancelled';

export interface TaxCarryoverData {
  id: number;
  clan_id: number;
  nick: string;
  source_month: number;
  source_year: number;
  amount: number;
  status: TaxCarryoverStatus;
  comment: string;
  created_by: number | null;
  created_at: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
}

/** A confirmed carry-over credited INTO the requested month. */
export interface TaxCarryoverIncoming {
  nick: string;
  amount: number;
  source_month: number;
  source_year: number;
}

/** Computed for a month that is not closed yet; never stored, never approvable. */
export interface TaxCarryoverPreview {
  nick: string;
  source_month: number;
  source_year: number;
  amount: number;
}

export interface TaxCarryoverMonth {
  month: number;
  year: number;
  is_closed: boolean;
  carryovers: TaxCarryoverData[];
  incoming: TaxCarryoverIncoming[];
  preview: TaxCarryoverPreview[];
  pending_count: number;
  pending_total: number;
}
