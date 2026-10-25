import type { CompareCharacter } from '../types/compare';
export type { CompareCharacter };
import apiClient from './client';
import type { AnalysisResult } from '../types/character';

interface CompareListResponse {
  characters: CompareCharacter[];
}

export async function getCompareCharacters(): Promise<CompareCharacter[]> {
  const response = await apiClient.get<CompareListResponse>('/api/compare');
  return response.data.characters;
}

export async function addCompareCharacter(
  characterName: string,
  snapshotData: AnalysisResult
): Promise<{ status: string; character_id: number }> {
  const response = await apiClient.post('/api/compare', {
    character_name: characterName,
    snapshot_data: snapshotData,
  });
  return response.data;
}

export async function deleteCompareCharacter(id: number): Promise<void> {
  await apiClient.delete(`/api/compare/${id}`);
}