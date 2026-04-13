import apiClient from './client';
import type { ClanInfoData, ClanMemberData, ClanHierarchyData } from '../types/clanInfo';

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

export async function importClanMembers(clanId: number, members: Partial<ClanMemberData>[], overwrite: boolean = false): Promise<ImportResult> {
  const response = await apiClient.post(`/api/clan/${clanId}/members/import`, { members, overwrite });
  return response.data;
}

export async function getClanHierarchy(clanId: number): Promise<ClanHierarchyData[]> {
  const response = await apiClient.get(`/api/clan/${clanId}/hierarchy`);
  return response.data;
}

export async function addClanHierarchy(clanId: number, data: Partial<ClanHierarchyData> & { role_name: string }): Promise<ClanHierarchyData> {
  const response = await apiClient.post(`/api/clan/${clanId}/hierarchy`, data);
  return response.data;
}

export async function updateClanHierarchy(clanId: number, roleId: number, data: Partial<ClanHierarchyData>): Promise<ClanHierarchyData> {
  const response = await apiClient.put(`/api/clan/${clanId}/hierarchy/${roleId}`, data);
  return response.data;
}

export async function deleteClanHierarchy(clanId: number, roleId: number): Promise<void> {
  await apiClient.delete(`/api/clan/${clanId}/hierarchy/${roleId}`);
}
