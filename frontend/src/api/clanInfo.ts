import apiClient from './client';
import type { ClanInfoData, ClanMemberData, TreasuryOperationData } from '../types/clanInfo';

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

export async function deleteClanMember(clanId: number, memberId: number): Promise<void> {
  await apiClient.delete(`/api/clan/${clanId}/members/${memberId}`);
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
