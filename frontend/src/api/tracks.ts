import apiClient from './client';
import type { ImprovementTrack, TrackSummary, ImprovementStep } from '../types/track';

export async function generateTrack(characterData: Record<string, unknown>, scenarioId: number): Promise<ImprovementTrack> {
  const response = await apiClient.post('/api/tracks/generate', { character_data: characterData, scenario_id: scenarioId });
  return response.data;
}

export async function getTrack(id: number): Promise<ImprovementTrack> {
  const response = await apiClient.get(`/api/tracks/${id}`);
  return response.data;
}

export async function listTracks(): Promise<TrackSummary[]> {
  const response = await apiClient.get('/api/tracks');
  return response.data;
}

export async function updateStep(trackId: number, stepId: string, completed: boolean): Promise<{ steps: ImprovementStep[]; total_progress: number }> {
  const response = await apiClient.put(`/api/tracks/${trackId}/step/${stepId}`, { completed });
  return response.data;
}

export async function deleteTrack(id: number): Promise<void> {
  await apiClient.delete(`/api/tracks/${id}`);
}
