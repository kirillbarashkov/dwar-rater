import apiClient from './client';
import type { ClanInfoData, ClanMemberData, TreasuryOperationData, LeftMemberData, MembershipEvent } from '../types/clanInfo';

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
  replace: boolean = false
): Promise<{ success: boolean; imported: number; updated: number; skipped: number; message: string }> {
  const response = await apiClient.post(`/api/clan/${clanId}/treasury/import`, { operations, replace });
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
  data: { quantity?: number; compensation_flag?: boolean; compensation_comment?: string }
): Promise<TreasuryOperationData> {
  const response = await apiClient.put(`/api/clan/${clanId}/treasury/${operationId}`, data);
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
