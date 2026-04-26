import apiClient from './client';
import type { ClosedProfileData, CheckResult, BatchScanResult } from '../types/closedProfile';

export async function getClosedProfiles(): Promise<ClosedProfileData[]> {
  const response = await apiClient.get('/api/closed-profiles');
  return response.data;
}

export async function addClosedProfile(nick: string): Promise<ClosedProfileData | { exists: boolean; is_scanned_open: boolean; scanned_open_at: string | null }> {
  const response = await apiClient.post('/api/closed-profiles', { nick });
  return response.data;
}

export async function updateClosedProfile(id: number, data: { notes?: string }): Promise<ClosedProfileData> {
  const response = await apiClient.put(`/api/closed-profiles/${id}`, data);
  return response.data;
}

export async function deleteClosedProfile(id: number): Promise<void> {
  await apiClient.delete(`/api/closed-profiles/${id}`);
}

export async function checkProfile(nick: string): Promise<CheckResult> {
  const response = await apiClient.post(`/api/closed-profiles/${nick}/check`, {});
  return response.data;
}

export async function batchScan(nicks: string[]): Promise<BatchScanResult> {
  const response = await apiClient.post('/api/closed-profiles/batch-scan', { nicks });
  return response.data;
}

export async function batchDelete(ids: number[]): Promise<void> {
  await apiClient.post('/api/closed-profiles/batch-delete', { ids });
}

export async function deleteAllClosedProfiles(): Promise<void> {
  await apiClient.post('/api/closed-profiles/delete-all', {});
}

export async function saveSnapshotForProfile(nick: string, snapshotData: Record<string, unknown>, snapshotName?: string): Promise<{ success: boolean; snapshot_id: number }> {
  const response = await apiClient.post(`/api/closed-profiles/${nick}/save-snapshot`, {
    snapshot_data: snapshotData,
    snapshot_name: snapshotName,
  });
  return response.data;
}
