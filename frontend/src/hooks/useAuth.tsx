import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import type { User, AuthContextType } from '../types/auth';
import {
  login as apiLogin,
  login2fa as apiLogin2fa,
  logout as apiLogout,
  changePassword as apiChangePassword,
  fetchMe,
  setSession,
  getStoredUser,
  getStoredPermissions,
  isAuthenticated,
  clearSession,
} from '../api/auth';

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(getStoredUser());
  const [permissions, setPermissions] = useState<Record<string, 'full' | 'read' | 'none'>>(getStoredPermissions);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (isAuthenticated()) {
      fetchMe()
        .then((data) => {
          const u: User = {
            ...data.user,
            last_login_at: data.user.last_login_at ?? null,
            created_at: data.user.created_at ?? null,
          };
          setUser(u);
          setPermissions(data.permissions);
          setSession(localStorage.getItem('auth_token') || '', u, data.permissions);
        })
        .catch(() => {
          clearSession();
          setUser(null);
          setPermissions({});
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const result = await apiLogin(username, password);
    if (result.requires_2fa) {
      return { requires_2fa: true, user_id: result.user_id, must_change_password: false };
    }
    const u: User = {
      ...result.user,
      last_login_at: null,
      created_at: null,
    };
    setSession(result.token, u);
    setUser(u);
    return { must_change_password: result.must_change_password };
  }, []);

  const login2fa = useCallback(async (userId: number, code: string) => {
    const result = await apiLogin2fa(userId, code);
    const u: User = {
      ...result.user,
      last_login_at: null,
      created_at: null,
    };
    setSession(result.token, u);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
    setPermissions({});
  }, []);

  const changePassword = useCallback(async (newPassword: string) => {
    await apiChangePassword(newPassword);
    if (user) {
      const updated = { ...user, must_change_password: false };
      setUser(updated);
      setSession(localStorage.getItem('auth_token') || '', updated, permissions);
    }
  }, [user, permissions]);

  return (
    <AuthContext.Provider value={{ user, permissions, login, login2fa, logout, changePassword, isAuthenticated: !!user, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

export function usePermission(feature: string, action: string): 'full' | 'read' | 'none' {
  const { permissions, user } = useAuth();
  if (user?.role === 'admin') return 'full';
  const key = `${feature}:${action}`;
  return permissions[key] ?? 'none';
}
