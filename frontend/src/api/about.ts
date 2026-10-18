import apiClient from './client';
import type { AboutPayload } from '../types/about';

/** Документы вкладки «О проекте»: описание, что нового, релизы, техдолг. */
export async function fetchAbout(): Promise<AboutPayload> {
  const response = await apiClient.get('/api/about');
  return response.data as AboutPayload;
}
