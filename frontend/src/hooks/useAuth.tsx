import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import type { User, AuthContextType } from '../types/auth';
import { login as apiLogin, logout as apiLogout, isAuthenticated, getStoredUsername } from '../api/auth';

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (isAuthenticated()) {
      const username = getStoredUsername();
      setUser({
        id: 0,
        username: username || '',
        role: 'user',
      });
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await apiLogin(username, password);
    setUser({
      id: 0,
      username,
      role: 'user',
    });
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user, isLoading }}>
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
