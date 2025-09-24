export interface AuthContextType {
  user: unknown;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  getAuthError: (error: Error) => { type: string; message: string };
}

const defaultAuthContext: AuthContextType = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: async () => {},
  logout: () => {},
  refreshToken: async () => {},
  getAuthError: () => ({ type: 'unknown', message: '未登录' }),
};

export const useAuth = (): AuthContextType => {
  return defaultAuthContext;
};

export default useAuth;
