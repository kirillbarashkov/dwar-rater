import apiClient from './client';
import type { ClanInfoData, ClanMemberData } from '../types/clanInfo';

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
