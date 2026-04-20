import { useState, useCallback, useRef } from 'react';
import { analyzeCharacter } from '../api/analyze';
import type { AnalysisResult } from '../types/character';

interface UseCharacterAnalysisReturn {
  result: AnalysisResult | null;
  isLoading: boolean;
  error: string | null;
  analyze: (url: string) => Promise<void>;
  clearResult: () => void;
  canAnalyze: boolean;
}

export function useCharacterAnalysis(): UseCharacterAnalysisReturn {
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadingRef = useRef(false);

  const analyze = useCallback(async (url: string) => {
    if (loadingRef.current) {
      setError('Анализ уже выполняется, подождите...');
      return;
    }

    loadingRef.current = true;
    setIsLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const data = await analyzeCharacter(url);
      setResult(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        const message = err.message;
        if (message.includes('429') || message.includes('Too Many Requests')) {
          setError('Слишком много запросов. Подождите 10-15 секунд и попробуйте снова.');
        } else {
          setError(message);
        }
      } else {
        setError('Произошла неизвестная ошибка');
      }
    } finally {
      loadingRef.current = false;
      setIsLoading(false);
    }
  }, []);

  const clearResult = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, isLoading, error, analyze, clearResult, canAnalyze: !loadingRef.current };
}
