import apiClient from './client';
import type {
  TreasuryCandidatesResponse,
  TreasuryPairData,
  TreasuryPairHistoryResponse,
  TreasuryPairsResponse,
} from '../types/treasuryPairs';

/** Очередь пар казны: кандидаты автоматики и решения казначея. */
export async function getTreasuryPairs(
  clanId: number,
  params: {
    status?: string;
    kind?: string;
    nick?: string;
    /** Тип операции на любой стороне пары: «Деньги», «Предмет» и т.п. */
    op_type?: string;
    /** Месяц в формате YYYY-MM — границы периода по датам операций. */
    date_from?: string;
    date_to?: string;
    /** 'old' — порядок импорта, 'new' — сначала новые. */
    sort?: string;
    /** Показать одну конкретную пару — переход из «Статуса персонажа». */
    pair_id?: number;
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

/** Разрыв пары: указанная сторона — списание на таланты клана, вторая снова кандидат. */
export async function splitTreasuryPair(
  clanId: number,
  pairId: number,
  keep: 'first' | 'second',
  comment?: string,
): Promise<TreasuryPairData> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/pairs/${pairId}/split`,
    { keep, comment: comment ?? '' },
  );
  return response.data;
}

/** Групповое решение по пачке пар: одно действие на всю пачку. */
export async function batchDecideTreasuryPairs(
  clanId: number,
  ids: number[],
  action: 'confirm' | 'reject',
  kind?: 'exchange' | 'loan',
): Promise<{ done: number[]; failed: { id: number; error: string }[] }> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/pairs/batch`,
    { ids, action, kind: kind ?? '' },
  );
  return response.data;
}

/** История решений по паре: кто, когда и что менял. */
export async function getTreasuryPairHistory(
  clanId: number,
  pairId: number,
): Promise<TreasuryPairHistoryResponse> {
  const response = await apiClient.get(
    `/api/clan/${clanId}/treasury/pairs/${pairId}/history`,
  );
  return response.data;
}

/** Возврат пары в очередь кандидатов — отмена решения казначея. */
export async function restoreTreasuryPair(
  clanId: number,
  pairId: number,
): Promise<TreasuryPairData> {
  const response = await apiClient.post(
    `/api/clan/${clanId}/treasury/pairs/${pairId}/restore`,
    {},
  );
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
