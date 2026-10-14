import apiClient from './client';
import type { MemberStatusResponse } from '../types/memberStatus';

/** Состояние дел участника за месяц — для вкладки «Статус персонажа». */
export async function getMemberStatus(
  clanId: number,
  nick: string,
  month?: number,
  year?: number,
): Promise<MemberStatusResponse> {
  const response = await apiClient.get(
    `/api/clan/${clanId}/treasury/member-status`,
    { params: { nick, month, year } },
  );
  return response.data;
}
