export interface User {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string | null;
}

export interface AuthContextType {
  user: User | null;
  permissions: Record<string, 'full' | 'read' | 'none'>;
  login: (username: string, password: string) => Promise<{ requires_2fa?: boolean; user_id?: number; must_change_password: boolean }>;
  login2fa: (userId: number, code: string) => Promise<void>;
  logout: () => void;
  changePassword: (newPassword: string) => Promise<void>;
  isAuthenticated: boolean;
  isLoading: boolean;
}
