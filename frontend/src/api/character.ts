import apiClient from './client';
import type { AnalysisResult } from '../types/character';

export async function getMyCharacter(): Promise<AnalysisResult> {
  const response = await apiClient.get<AnalysisResult>('/api/auth/me/character');
  return response.data;
}

export async function refreshMyCharacter(): Promise<AnalysisResult> {
  const response = await apiClient.post<AnalysisResult>('/api/auth/me/character/refresh');
  return response.data;
}
