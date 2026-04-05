import { useState, useCallback } from 'react';
import { analyzeCharacter } from '../api/analyze';
import type { AnalysisResult } from '../types/character';

interface UseCharacterAnalysisReturn {
  result: AnalysisResult | null;
  isLoading: boolean;
  error: string | null;
  analyze: (url: string) => Promise<void>;
  clearResult: () => void;
}

export function useCharacterAnalysis(): UseCharacterAnalysisReturn {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = useCallback(async (url: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await analyzeCharacter(url);
      setResult(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Произошла неизвестная ошибка');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearResult = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, isLoading, error, analyze, clearResult };
}
