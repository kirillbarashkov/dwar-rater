import apiClient from './client';

export async function login(username: string, password: string) {
  const credentials = btoa(`${username}:${password}`);
  const response = await apiClient.post('/api/login', {}, {
    headers: { Authorization: `Basic ${credentials}` },
  });
  localStorage.setItem('auth_credentials', credentials);
  localStorage.setItem('auth_username', username);
  return response.data;
}

export async function logout() {
  localStorage.removeItem('auth_credentials');
  localStorage.removeItem('auth_username');
}

export function getStoredUsername(): string | null {
  return localStorage.getItem('auth_username');
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem('auth_credentials');
}
