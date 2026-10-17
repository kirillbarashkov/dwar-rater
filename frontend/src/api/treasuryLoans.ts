import apiClient from './client';
import type { TreasuryLoansResponse } from '../types/treasuryLoans';

/**
 * Открытые займы клана. Без `nick` приходит сводка по людям, с `nick` — ещё и
 * операции этого человека: тянуть тысячи строк ради одной раскрытой строки незачем.
 */
export async function getTreasuryLoans(
  clanId: number,
  nick?: string,
): Promise<TreasuryLoansResponse> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/loans`, {
    params: nick ? { nick } : undefined,
  });
  return response.data;
}
