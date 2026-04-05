import apiClient from './client';
import type { AnalysisResult } from '../types/character';

export async function analyzeCharacter(url: string): Promise<AnalysisResult> {
  const response = await apiClient.post('/api/analyze', { url });
  return response.data;
}
