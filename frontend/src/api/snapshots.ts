import apiClient from './client';
import type { Snapshot, SnapshotListResponse, SaveSnapshotRequest, SaveSnapshotResponse } from '../types/snapshot';

export async function getSnapshots(params?: { page?: number; per_page?: number; nick?: string }): Promise<SnapshotListResponse> {
  const response = await apiClient.get('/api/snapshots', { params });
  return response.data;
}

export async function getSnapshot(id: number): Promise<Snapshot & Record<string, unknown>> {
  const response = await apiClient.get(`/api/snapshots/${id}`);
  return response.data;
}

export async function deleteSnapshot(id: number): Promise<void> {
  await apiClient.delete(`/api/snapshots/${id}`);
}

export async function saveSnapshot(data: SaveSnapshotRequest): Promise<SaveSnapshotResponse> {
  const response = await apiClient.post('/api/save-snapshot', data);
  return response.data;
}
