import apiClient from './client';
import type { ScenarioSummary, ScenarioDetail, ScenarioComparisonResult } from '../types/scenario';

export async function getScenarios(): Promise<ScenarioSummary[]> {
  const response = await apiClient.get('/api/scenarios');
  return response.data;
}

export async function getScenario(id: number): Promise<ScenarioDetail> {
  const response = await apiClient.get(`/api/scenarios/${id}`);
  return response.data;
}

export async function createScenario(data: { name: string; description?: string; data: Record<string, unknown>; is_public?: boolean }): Promise<{ id: number; name: string }> {
  const response = await apiClient.post('/api/scenarios', data);
  return response.data;
}

export async function updateScenario(id: number, data: Record<string, unknown>): Promise<void> {
  await apiClient.put(`/api/scenarios/${id}`, data);
}

export async function deleteScenario(id: number): Promise<void> {
  await apiClient.delete(`/api/scenarios/${id}`);
}

export async function compareScenario(id: number, characterData: Record<string, unknown>): Promise<ScenarioComparisonResult> {
  const response = await apiClient.post(`/api/scenarios/${id}/compare`, characterData);
  return response.data;
}
