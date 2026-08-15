import apiClient from './client';
import type {
  ImprovementTrack,
  TrackSummary,
  ImprovementStep,
  GenerateTrackPayload,
  ReEvaluateResult,
} from '../types/track';

export async function generateTrack(payload: GenerateTrackPayload): Promise<ImprovementTrack>;
export async function generateTrack(characterData: Record<string, unknown>, scenarioId: number): Promise<ImprovementTrack>;
export async function generateTrack(
  payloadOrData: GenerateTrackPayload | Record<string, unknown>,
  scenarioId?: number,
): Promise<ImprovementTrack> {
  // Overload: legacy (characterData, scenarioId) → back-compat server signature
  const body =
    scenarioId !== undefined
      ? { character_data: payloadOrData, scenario_id: scenarioId }
      : (payloadOrData as GenerateTrackPayload);
  const response = await apiClient.post('/api/tracks/generate', body);
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

export async function updateStep(
  trackId: number,
  stepId: string,
  completed: boolean,
  current?: number,
): Promise<{ steps: ImprovementStep[]; total_progress: number }> {
  const body: { completed: boolean; current?: number } = { completed };
  if (current !== undefined) body.current = current;
  const response = await apiClient.put(`/api/tracks/${trackId}/step/${stepId}`, body);
  return response.data;
}

export async function reEvaluateTrack(
  id: number,
  characterData: Record<string, unknown>,
  forceRefresh = false,
): Promise<ReEvaluateResult> {
  const response = await apiClient.post(`/api/tracks/${id}/re-evaluate`, {
    character_data: characterData,
    force_refresh: forceRefresh,
  });
  return response.data;
}

export async function deleteTrack(id: number): Promise<void> {
  await apiClient.delete(`/api/tracks/${id}`);
}
