import apiClient from './client';

import type { User } from '../types/auth';

export interface LoginResponse {
  token: string;
  user: {
    id: number;
    username: string;
    role: string;
    is_active: boolean;
    must_change_password: boolean;
  };
  must_change_password: boolean;
  requires_2fa?: boolean;
  user_id?: number;
  expires_at: string;
}

export interface MeResponse {
  user: {
    id: number;
    username: string;
    role: string;
    is_active: boolean;
    must_change_password: boolean;
    last_login_at: string | null;
    created_at: string | null;
  };
  permissions: Record<string, 'full' | 'read' | 'none'>;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/api/auth/login', { username, password });
  return response.data;
}

export async function login2fa(userId: number, code: string): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/api/auth/login/2fa', { user_id: userId, code });
  return response.data;
}

export async function logout() {
  try {
    await apiClient.post('/api/auth/logout');
  } finally {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    localStorage.removeItem('auth_permissions');
  }
}

export async function changePassword(newPassword: string) {
  await apiClient.post('/api/auth/change-password', { new_password: newPassword });
}

export async function fetchMe(): Promise<MeResponse> {
  const response = await apiClient.get<MeResponse>('/api/auth/me');
  return response.data;
}

export function setSession(token: string, user: LoginResponse['user'], permissions?: Record<string, 'full' | 'read' | 'none'>) {
  localStorage.setItem('auth_token', token);
  localStorage.setItem('auth_user', JSON.stringify(user));
  if (permissions) {
    localStorage.setItem('auth_permissions', JSON.stringify(permissions));
  }
}

export function getStoredUser(): User | null {
  const raw = localStorage.getItem('auth_user');
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    return {
      ...parsed,
      last_login_at: parsed.last_login_at ?? null,
      created_at: parsed.created_at ?? null,
    };
  } catch {
    return null;
  }
}

export function getStoredPermissions(): Record<string, 'full' | 'read' | 'none'> {
  const raw = localStorage.getItem('auth_permissions');
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

export function isAuthenticated(): boolean {
  return !!localStorage.getItem('auth_token');
}

export function clearSession() {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('auth_user');
  localStorage.removeItem('auth_permissions');
}
