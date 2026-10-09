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

/** One month of a member's account — a cell of the engine's month chain. */
export interface TaxLedgerMonth {
  month: number;
  year: number;
  norm: number;
  paid: number;
  compensation: number;
  carried_in: number;
  carried_out: number;
  debt: number;
}

/**
 * Лицевой счёт участника: the member's months plus totals over the window.
 * Computed from the same chain as the carry-over proposals, so `carried_out_final`
 * is exactly what the engine proposes to carry out of the window's last month.
 */
export interface TaxLedgerRow {
  nick: string;
  level: number;
  months: TaxLedgerMonth[];
  norm_total: number;
  paid_total: number;
  compensation_total: number;
  carried_in_total: number;
  carried_out_final: number;
  debt: number;
  balance: number;
}

export interface TaxLedgerTotals {
  norm_total: number;
  paid_total: number;
  compensation_total: number;
  carried_in_total: number;
  carried_out_final: number;
  debt: number;
  balance: number;
}

/** A treasury month the treasurer has explicitly closed (frozen). */
export interface TreasuryClosedMonth {
  month: number;
  year: number;
  note: string;
  closed_by: number | null;
  closed_at: string | null;
}

/** A chat-ready markdown summary of one month (see the treasury summary endpoint). */
export interface TreasurySummaryResponse {
  clan_id: number;
  month: number;
  year: number;
  kind: string;
  /** Available kinds, in a stable order. */
  kinds: string[];
  /** kind -> human label, served so the selector has a single source. */
  labels: Record<string, string>;
  count: number;
  markdown: string;
  /** `no_operations` when the clan has nothing to summarize. */
  reason?: string;
}

/** What a renamed character's history transfer would move (and what it cannot). */
export interface NickTransferPlan {
  from_nick: string;
  to_nick: string;
  operations: {
    count: number;
    ids: number[];
    total_quantity: number;
    first_date: string | null;
    last_date: string | null;
    /** (month, year) pairs the moved payments belong to. */
    months: Array<[number, number]>;
  };
  carryovers: {
    move: number[];
    /** Rows whose month the receiving nick already has — left for a human. */
    skip: Array<{ id: number; month: number; year: number; amount: number; reason: string }>;
    skipped_count: number;
  };
  level_events: { count: number; ids: number[] };
  is_empty: boolean;
}

export interface NickTransferResult {
  applied: boolean;
  from_nick: string;
  to_nick: string;
  operations: number;
  carryovers: number;
  level_events: number;
  skipped_carryovers: NickTransferPlan['carryovers']['skip'];
  plan: NickTransferPlan;
}

/** One (nick, month) pair of a bulk waiver — what will happen and why. */
export interface BulkCompensationItem {
  nick: string;
  month: number | string;
  year: number;
  amount: number;
  action: 'create' | 'skip' | 'blocked';
  reason: string | null;
}

export interface BulkCompensationPlan {
  items: BulkCompensationItem[];
  totals: { pairs: number; create: number; skip: number; blocked: number };
  by_reason: Record<string, number>;
  labels: Record<string, string>;
  today: string;
}

export interface BulkCompensationResult {
  created: number;
  operations: Array<{ id: number; nick: string; date: string; quantity: number }>;
  plan: BulkCompensationPlan;
}

/** One category of treasury findings (see the anomaly report endpoint). */
export interface TreasuryAnomalyItem {
  code: string;
  label: string;
  /** True for corruption (a future date, a negative amount) — also refused on write. */
  blocking: boolean;
  count: number;
  examples: Array<{
    id: number | null;
    date: string | null;
    nick: string | null;
    quantity: number | null;
    note?: string;
  }>;
}

export interface TreasuryAnomaliesResponse {
  clan_id: number;
  items: TreasuryAnomalyItem[];
  total: number;
  checked: { operations: number; members: number };
  today: string;
  /** Findings a treasurer has accepted: ref '' = the whole category. */
  muted: Array<{ code: string; ref: string; created_by: number | null; created_at: string | null }>;
}

export interface TaxLedgerResponse {
  clan_id: number;
  from_month: number;
  from_year: number;
  to_month: number;
  to_year: number;
  is_closed: boolean;
  rows: TaxLedgerRow[];
  totals: TaxLedgerTotals;
  /** `no_operations` when the clan has nothing to show inside the window. */
  reason?: string;
}

/** Fields the treasury journal stores in an audit entry's old/new payload. */
export interface JournalValue {
  nick?: string;
  date?: string;
  operation_type?: string;
  object_name?: string;
  quantity?: number;
  compensation_flag?: boolean;
  compensation_comment?: string;
  reason?: string;
  status?: string;
  amount?: number;
  month?: number;
  year?: number;
  norm_amount?: number;
  months?: number[];
  count?: number;
  imported?: number;
  updated?: number;
  skipped?: number;
  filename?: string;
  value?: unknown;
  [key: string]: unknown;
}

export interface TreasuryJournalEntry {
  id: number;
  action: string;
  username: string;
  target_type: string | null;
  target_id: number | null;
  created_at: string | null;
  reason: string | null;
  nick: string | null;
  old: JournalValue | null;
  new: JournalValue | null;
  revertable: boolean;
}

export interface ReasonCode {
  code: string;
  label: string;
}

export interface TreasuryJournalResponse {
  entries: TreasuryJournalEntry[];
  total: number;
  limit: number;
  offset: number;
  reason_codes: ReasonCode[];
  actions: string[];
}
