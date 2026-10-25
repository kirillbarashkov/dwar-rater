import type { AnalysisResult } from './character';

/** A45: канон DTO сравнения (был в api/compare.ts и CompareListManager.tsx). */
export interface CompareCharacter {
  id: number;
  name: string;
  data: AnalysisResult;
  added_at: string;
  sort_order: number;
}
