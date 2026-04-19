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
  const lastRequestTime = useRef<number>(0);

  const analyze = useCallback(async (url: string) => {
    const now = Date.now();
    const minInterval = 3000;
    
    if (now - lastRequestTime.current < minInterval) {
      setError('Подождите несколько секунд перед следующим анализом');
      return;
    }
    
    if (isLoading) {
      setError('Анализ уже выполняется, подождите...');
      return;
    }
    
    lastRequestTime.current = now;
    setIsLoading(true);
    setError(null);
    
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
      setIsLoading(false);
    }
  }, [isLoading]);

  const clearResult = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { result, isLoading, error, analyze, clearResult, canAnalyze: !isLoading };
}
