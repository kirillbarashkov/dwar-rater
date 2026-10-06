import apiClient from './client';
import type {
  ClanInfoData,
  ClanMemberData,
  TreasuryOperationData,
  LeftMemberData,
  MembershipEvent,
  TaxCarryoverData,
  TaxCarryoverMonth,
  TaxLedgerResponse,
  TreasuryAnomaliesResponse,
  TreasuryClosedMonth,
  TreasuryJournalResponse,
} from '../types/clanInfo';

export async function getClanInfo(clanId: number): Promise<ClanInfoData> {
  const response = await apiClient.get(`/api/clan/${clanId}/info`);
  return response.data;
}

export async function updateClanInfo(clanId: number, data: Partial<ClanInfoData>): Promise<ClanInfoData> {
  const response = await apiClient.put(`/api/clan/${clanId}/info`, data);
  return response.data;
}

export async function getClanMembers(clanId: number): Promise<ClanMemberData[]> {
  const response = await apiClient.get(`/api/clan/${clanId}/members`);
  return response.data;
}

export async function addClanMember(clanId: number, data: Partial<ClanMemberData> & { nick: string; level: number; clan_role: string }): Promise<ClanMemberData> {
  const response = await apiClient.post(`/api/clan/${clanId}/members`, data);
  return response.data;
}

export async function updateClanMember(clanId: number, memberId: number, data: Partial<ClanMemberData>): Promise<ClanMemberData> {
  const response = await apiClient.put(`/api/clan/${clanId}/members/${memberId}`, data);
  return response.data;
}

export async function deleteClanMember(clanId: number, memberId: number, leaveReason?: string, leftDate?: string): Promise<void> {
  await apiClient.delete(`/api/clan/${clanId}/members/${memberId}`, {
    data: { leave_reason: leaveReason, left_date: leftDate },
  });
}

export async function getLeftMembers(clanId: number): Promise<LeftMemberData[]> {
  const response = await apiClient.get(`/api/clan/${clanId}/members/left`);
  return response.data;
}

export interface ImportResult {
  success: number;
  skipped: number;
  failed: number;
  errors: string[];
}

export async function importClanMembers(clanId: number, members: Partial<ClanMemberData>[], overwrite: boolean = false, clanInfo?: Partial<ClanInfoData>): Promise<ImportResult> {
  const response = await apiClient.post(`/api/clan/${clanId}/members/import`, { members, overwrite, clanInfo });
  return response.data;
}

export interface TreasuryFetchResult {
  success: boolean;
  imported: number;
  message: string;
  error?: string;
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
}

export async function getTreasuryDateCoverage(clanId: number): Promise<DateCoverage> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/date-coverage`);
  return response.data;
}

export async function getTreasuryOperations(clanId: number): Promise<TreasuryOperationData[]> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury`);
  return response.data;
}

export async function fetchTreasuryOperations(clanId: number): Promise<TreasuryFetchResult> {
  const response = await apiClient.post(`/api/clan/${clanId}/treasury`, {});
  return response.data;
}

export async function importTreasuryOperations(
  clanId: number, 
  operations: Array<{
    date: string;
    nick: string;
    operation_type: string;
    object_name: string;
    quantity: number;
  }>,
  replace: boolean = false,
  /**
   * Replace the day span covered by `operations` instead of appending to it.
   * Used by the auto-collect flow so a repeated import of the same range cannot
   * double the treasury; the paste-a-page flow keeps appending because a page
   * covers only part of a day.
   */
  replaceRange: boolean = false
): Promise<{ success: boolean; imported: number; updated: number; skipped: number; message: string }> {
  const response = await apiClient.post(`/api/clan/${clanId}/treasury/import`, {
    operations,
    replace,
    replace_range: replaceRange,
  });
  return response.data;
}

export interface TreasuryExportData {
  version: number;
  exported_at: string;
  clan_id: number;
  operations_count: number;
  operations: Array<{
    id: number;
    date: string;
    nick: string;
    operation_type: string;
    object_name: string;
    quantity: number;
    created_at: string | null;
  }>;
}

export async function exportTreasuryOperations(clanId: number): Promise<TreasuryExportData> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/export`);
  return response.data;
}

export interface BackupFile {
  filename: string;
  size: number;
  modified: string;
}

export interface SaveBackupResult {
  success: boolean;
  filename: string;
  operations_count: number;
  message: string;
}

export async function saveTreasuryBackup(clanId: number): Promise<SaveBackupResult> {
  const response = await apiClient.post(`/api/clan/${clanId}/treasury/backup`, {});
  return response.data;
}

export async function listTreasuryBackups(clanId: number): Promise<{ backups: BackupFile[] }> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/backups`);
  return response.data;
}

export async function getTreasuryBackup(clanId: number, filename: string): Promise<TreasuryExportData> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/backup/${filename}`);
  return response.data;
}

export async function restoreTreasuryBackup(clanId: number, filename: string): Promise<{ success: boolean; imported: number; message: string }> {
  const response = await apiClient.post(`/api/clan/${clanId}/treasury/backup/restore`, { filename });
  return response.data;
}

export async function updateTreasuryCompensation(
  clanId: number,
  operationId: number,
  compensationFlag: boolean,
  compensationComment: string
): Promise<TreasuryOperationData> {
  const response = await apiClient.put(`/api/clan/${clanId}/treasury/${operationId}`, {
    compensation_flag: compensationFlag,
    compensation_comment: compensationComment,
  });
  return response.data;
}

export async function updateTreasuryOperation(
  clanId: number,
  operationId: number,
  data: { quantity?: number; compensation_flag?: boolean; compensation_comment?: string; reason?: string }
): Promise<TreasuryOperationData> {
  const response = await apiClient.put(`/api/clan/${clanId}/treasury/${operationId}`, data);
  return response.data;
}

/**
 * Re-attribute a payment to another member: the money is untouched, only its
 * owner changes. `reason` is required — it lands in the treasury journal.
 */
export async function reassignTreasuryOperation(
  clanId: number,
  operationId: number,
  data: { to_nick: string; reason: string }
): Promise<TreasuryOperationData & { from_nick: string; member_status: 'active' | 'left' }> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/${operationId}/reassign`,
    data
  );
  return response.data;
}

export async function getTreasuryMonths(
  clanId: number
): Promise<{ clan_id: number; months: TreasuryClosedMonth[] }> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/months`);
  return response.data;
}

/** Read-only diagnostics: what looks wrong in the stored treasury. */
export async function getTreasuryAnomalies(
  clanId: number
): Promise<TreasuryAnomaliesResponse> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/anomalies`);
  return response.data;
}

export async function closeTreasuryMonth(
  clanId: number,
  year: number,
  month: number,
  note = ''
): Promise<{ closed: TreasuryClosedMonth; proposals: number }> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/months/${year}/${month}/close`,
    { note }
  );
  return response.data;
}

export async function reopenTreasuryMonth(
  clanId: number,
  year: number,
  month: number,
  reason = ''
): Promise<{ reopened: { month: number; year: number } }> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/months/${year}/${month}/reopen`,
    { reason }
  );
  return response.data;
}

export interface ParsedTreasuryOperation {
  date: string;
  nick: string;
  operation_type: string;
  object_name: string;
  quantity: number;
}

export async function saveTreasuryCookies(
  clanId: number,
  cookies: string
): Promise<{ success: boolean; message: string; error?: string }> {
  const response = await apiClient.post(`/api/clan/${clanId}/treasury/cookies/save`, { cookies });
  return response.data;
}

export async function getTreasuryCookiesStatus(
  clanId: number
): Promise<{ has_cookies: boolean; is_valid: boolean; updated_at?: string | null }> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/cookies/status`);
  return response.data;
}

export async function autoFetchTreasury(
  clanId: number
): Promise<{
  success: boolean;
  operations: ParsedTreasuryOperation[];
  pages_fetched: number;
  date_range: { earliest: string; latest: string };
  message: string;
  error?: string;
}> {
  const response = await apiClient.post(`/api/clan/${clanId}/treasury/auto-fetch`, {});
  return response.data;
}

export async function createTreasuryCompensation(
  clanId: number,
  nick: string,
  normAmount: number,
  comment: string,
  months: number[],
  year?: number
): Promise<{ created: number; operations: TreasuryOperationData[] }> {
  const response = await apiClient.post(`/api/clan/${clanId}/treasury/compensation`, {
    nick,
    norm_amount: normAmount,
    comment,
    months,
    year,
  });
  return response.data;
}

export async function getMembershipEvents(
  clanId: number,
  filters?: { source?: string; event_type?: string }
): Promise<MembershipEvent[]> {
  const params = new URLSearchParams();
  if (filters?.source) params.set('source', filters.source);
  if (filters?.event_type) params.set('event_type', filters.event_type);
  const qs = params.toString();
  const response = await apiClient.get(`/api/clan/${clanId}/members/events${qs ? `?${qs}` : ''}`);
  return response.data;
}

export async function importMemberDiff(
  clanId: number,
  diff: {
    joined: Partial<ClanMemberData>[];
    left: { nick: string; leave_reason: string; left_date?: string }[];
  }
): Promise<{ success: boolean; joined_count: number; left_count: number; errors: string[]; message: string }> {
  const response = await apiClient.post(`/api/clan/${clanId}/members/diff-import`, diff);
  return response.data;
}

export async function importHistoryEvents(
  clanId: number,
  events: { nick: string; event_type: string; event_date: string; leave_reason?: string }[]
): Promise<{ success: boolean; processed_count: number; skipped_count: number; errors: string[]; message: string }> {
  const response = await apiClient.post(`/api/clan/${clanId}/members/history-import`, { events });
  return response.data;
}

export interface LevelChangeEvent {
  id?: number;
  nick: string;
  old_level: number;
  new_level: number;
  event_date: string;
  created_at?: string;
}

export async function getLevelEvents(clanId: number): Promise<LevelChangeEvent[]> {
  const response = await apiClient.get(`/api/clan/${clanId}/level-events`);
  return response.data;
}

export async function saveLevelEvents(
  clanId: number,
  events: LevelChangeEvent[]
): Promise<{ success: boolean; imported: number; skipped: number; message: string }> {
  const response = await apiClient.post(`/api/clan/${clanId}/level-events/save`, { events });
  return response.data;
}

export async function getLevelHistory(
  clanId: number
): Promise<Record<string, Array<{ date: string; old_level: number; new_level: number }>>> {
  const response = await apiClient.get(`/api/clan/${clanId}/level-history`);
  return response.data;
}

export async function getTaxCarryovers(
  clanId: number,
  month: number,
  year: number
): Promise<TaxCarryoverMonth> {
  const response = await apiClient.get(`/api/clan/${clanId}/tax-carryover`, {
    params: { month, year },
  });
  return response.data;
}

export async function getTaxLedger(
  clanId: number,
  params: {
    from_month: number;
    from_year: number;
    to_month: number;
    to_year: number;
  }
): Promise<TaxLedgerResponse> {
  const response = await apiClient.get(`/api/clan/${clanId}/tax-ledger`, { params });
  return response.data;
}

export async function recomputeTaxCarryovers(
  clanId: number,
  month: number,
  year: number
): Promise<{ created: number; updated: number; removed: number; carryovers: TaxCarryoverData[] }> {
  const response = await apiClient.post(`/api/clan/${clanId}/tax-carryover/recompute`, {
    month,
    year,
  });
  return response.data;
}

export async function reviewTaxCarryover(
  clanId: number,
  carryoverId: number,
  action: 'confirm' | 'cancel',
  comment?: string
): Promise<{ success: boolean; carryover: TaxCarryoverData }> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/tax-carryover/${carryoverId}/${action}`,
    { comment: comment ?? '' }
  );
  return response.data;
}

export async function bulkReviewTaxCarryovers(
  clanId: number,
  ids: number[],
  action: 'confirm' | 'cancel',
  comment?: string
): Promise<{ success: boolean; updated: number; updated_ids: number[]; skipped_ids: number[]; missing_ids: number[] }> {
  const response = await apiClient.post(`/api/clan/${clanId}/tax-carryover/bulk`, {
    ids,
    action,
    comment: comment ?? '',
  });
  return response.data;
}

export async function getTreasuryJournal(
  clanId: number,
  params: { limit?: number; offset?: number; action?: string; nick?: string } = {}
): Promise<TreasuryJournalResponse> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/journal`, { params });
  return response.data;
}

export async function revertTreasuryJournalEntry(
  clanId: number,
  entryId: number,
  reason?: string
): Promise<{ success: boolean; operation_id: number; restored: Record<string, unknown> }> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/journal/${entryId}/revert`,
    { reason: reason ?? '' }
  );
  return response.data;
}
