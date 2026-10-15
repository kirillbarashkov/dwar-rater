import apiClient from './client';
import type { ExclusionGroup, ExclusionGroupsResponse } from '../types/treasuryExclusions';

/** Группы исключений казны: что не считаем и в каком режиме. */
export async function getExclusionGroups(clanId: number): Promise<ExclusionGroupsResponse> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/exclusions`);
  return response.data;
}

export interface ExclusionGroupPayload {
  name: string;
  mode: 'exclude' | 'neutral';
  comment?: string;
  prefixes?: string[];
  is_active?: boolean;
}

export async function createExclusionGroup(
  clanId: number,
  data: ExclusionGroupPayload,
): Promise<ExclusionGroup> {
  const response = await apiClient.post(`/api/clan/${clanId}/treasury/exclusions`, data);
  return response.data;
}

export async function updateExclusionGroup(
  clanId: number,
  groupId: number,
  data: Partial<ExclusionGroupPayload>,
): Promise<ExclusionGroup> {
  const response = await apiClient.put(
    `/api/clan/${clanId}/treasury/exclusions/${groupId}`,
    data,
  );
  return response.data;
}

export async function deleteExclusionGroup(
  clanId: number,
  groupId: number,
): Promise<{ ok: boolean }> {
  const response = await apiClient.delete(
    `/api/clan/${clanId}/treasury/exclusions/${groupId}`,
  );
  return response.data;
}

/** Применяет правила групп ко всем операциям клана. */
export async function applyExclusions(
  clanId: number,
): Promise<{ changed: number; total: number }> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/exclusions/apply`,
    {},
  );
  return response.data;
}
