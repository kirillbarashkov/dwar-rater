import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import type { User, AuthContextType } from '../types/auth';
import { login as apiLogin, logout as apiLogout, isAuthenticated, fetchUser } from '../api/auth';

const AuthContext = createContext<AuthContextType | null>(null);

// eslint-disable-next-line react-refresh/only-export-components
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => {
    if (isAuthenticated()) {
      fetchUser()
        .then(setUser)
        .catch(() => {
          apiLogout();
          setUser(null);
        })
        .finally(() => setIsLoading(false));
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await apiLogin(username, password);
    const user = await fetchUser();
    setUser(user);
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

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
