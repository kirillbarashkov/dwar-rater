import axios from 'axios';
import { API_BASE_URL } from '../utils/constants';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;

/**
 * A47: адрес API по одному правилу на всё приложение.
 *
 * Раньше часть вызовов собирала базу как `VITE_API_URL || ''` (axios-клиент),
 * а часть — как `VITE_API_URL || window.location.origin` (сырой `fetch` и SSE).
 * Два правила в одном приложении: при пустом `VITE_API_URL` это давало разные
 * строки для одного и того же эндпоинта. Возвращаем относительный путь — его
 * корректно разрешает и `fetch`, и `EventSource`.
 */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

function handleUnauthorized(status: number): void {
  if (status !== 401) return;
  localStorage.removeItem('auth_token');
  localStorage.removeItem('auth_user');
  window.location.href = '/login';
}

/**
 * A47: `fetch` с теми же правилами, что у axios-клиента.
 *
 * Сырые вызовы в обход `apiClient` не обрабатывали 401: при умершей сессии
 * пользователь видел вечный спиннер вместо перехода на `/login`. Здесь
 * повторяются оба правила интерсептора — заголовок с токеном и реакция на 401.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);

  const token = localStorage.getItem('auth_token');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(apiUrl(path), { ...init, headers });
  handleUnauthorized(response.status);
  return response;
}
