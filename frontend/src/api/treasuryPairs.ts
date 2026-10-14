import apiClient from './client';
import type {
  TreasuryCandidatesResponse,
  TreasuryPairData,
  TreasuryPairsResponse,
} from '../types/treasuryPairs';

/** Очередь пар казны: кандидаты автоматики и решения казначея. */
export async function getTreasuryPairs(
  clanId: number,
  params: {
    status?: string;
    kind?: string;
    nick?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<TreasuryPairsResponse> {
  const response = await apiClient.get(`/api/clan/${clanId}/treasury/pairs`, { params });
  return response.data;
}

/**
 * Подтверждение пары. Тело отправляем всегда: POST без тела Flask отвергает
 * с 415 Unsupported Media Type.
 */
export async function confirmTreasuryPair(
  clanId: number,
  pairId: number,
  kind: 'exchange' | 'loan',
): Promise<TreasuryPairData> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/pairs/${pairId}/confirm`,
    { kind },
  );
  return response.data;
}

export async function rejectTreasuryPair(
  clanId: number,
  pairId: number,
): Promise<TreasuryPairData> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/pairs/${pairId}/reject`,
    {},
  );
  return response.data;
}

export async function unconfirmTreasuryPair(
  clanId: number,
  pairId: number,
): Promise<TreasuryPairData> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/pairs/${pairId}/unconfirm`,
    {},
  );
  return response.data;
}

/** Корректировка пары: тип и комментарий. Историю изменений пишет сервер. */
export async function reviseTreasuryPair(
  clanId: number,
  pairId: number,
  data: { kind: 'exchange' | 'loan'; comment?: string },
): Promise<TreasuryPairData> {
  const response = await apiClient.put(`/api/clan/${clanId}/treasury/pairs/${pairId}`, data);
  return response.data;
}

/** Кандидаты на вторую сторону для конкретной операции. */
export async function getOperationCandidates(
  clanId: number,
  opId: number,
  windowDays?: number,
): Promise<TreasuryCandidatesResponse> {
  const response = await apiClient.get(
    `/api/clan/${clanId}/treasury/operations/${opId}/candidates`,
    { params: windowDays ? { window_days: windowDays } : undefined },
  );
  return response.data;
}
