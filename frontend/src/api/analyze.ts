import apiClient from './client';
import type { AnalysisResult } from '../types/character';

export async function analyzeCharacter(url: string): Promise<AnalysisResult> {
  try {
    const response = await apiClient.post('/api/analyze', { url });
    return response.data;
  } catch (err: unknown) {
    if (err && typeof err === 'object' && 'response' in err) {
      const axiosErr = err as { response?: { data?: { error?: string } } };
      const errorMessage = axiosErr.response?.data?.error || 'Ошибка анализа';
      throw new Error(errorMessage);
    }
    if (err instanceof Error) {
      throw err;
    }
    throw new Error('Неизвестная ошибка при анализе персонажа');
  }
}
