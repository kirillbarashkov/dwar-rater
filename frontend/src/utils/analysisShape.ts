import type { AnalysisResult } from '../types/character';

/**
 * A46: проверка, что слепок действительно содержит результат анализа.
 *
 * Раньше в `App.tsx` стояло `setCurrentResult(data as unknown as AnalysisResult)`:
 * `snapshot_data` из базы попадал во вкладки анализа без единой проверки формы.
 * Слепок, сохранённый по старой схеме (или слепок закрытого профиля, у которого
 * совсем другой набор полей), оказывался «результатом анализа», и вместо ошибки
 * пользователь видел пустые таблицы.
 *
 * Гард намеренно нестрогий: он отличает «похоже на анализ» от «совсем не то»,
 * а не валидирует каждое поле. Требовать полную схему значило бы ломать загрузку
 * слепков, сохранённых старыми версиями, — а они ещё в базе.
 */
export function isAnalysisLike(raw: unknown): raw is AnalysisResult {
  if (!raw || typeof raw !== 'object') return false;

  const record = raw as Record<string, unknown>;

  const hasIdentity = typeof record.name === 'string' && record.name.length > 0;
  if (!hasIdentity) return false;

  const hasStats = typeof record.main_stats === 'object' && record.main_stats !== null;
  const isClosedProfile =
    typeof record.closed_info === 'object' && record.closed_info !== null;

  // Либо это разобранный открытый профиль (есть характеристики), либо слепок
  // закрытого профиля (есть только `closed_info`).
  return hasStats || isClosedProfile;
}

/**
 * Возвращает результат анализа или `null`, если форма не подходит.
 *
 * Функция, а не только предикат: на пересечении `Snapshot & Record<string, unknown>`
 * предикат не сужает тип (проверено — `tsc` продолжал требовать 20 полей),
 * поэтому приведение живёт здесь, сразу после проверки, а не в вызывающем коде.
 */
export function asAnalysisResult(raw: unknown): AnalysisResult | null {
  return isAnalysisLike(raw) ? raw : null;
}
