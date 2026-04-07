import apiClient from './client';
import type { ClanInfoData, ClanMemberData } from '../types/clanInfo';

export async function getClanInfo(clanId: number): Promise<ClanInfoData> {
  const response = await apiClient.get(`/api/clan/${clanId}/info`);
  return response.data;
}

export async function getClanMembers(clanId: number): Promise<ClanMemberData[]> {
  const response = await apiClient.get(`/api/clan/${clanId}/members`);
  return response.data;
}
