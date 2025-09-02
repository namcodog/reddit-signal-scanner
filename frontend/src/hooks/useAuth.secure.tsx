/**
 * 安全认证Hook - 消灭JWT安全技术债务
 * 基于 Linus 安全原则：Never trust user input, 永远验证
 *
 * 安全改进：
 * 1. 后端token验证而非客户端解析
 * 2. 加密存储敏感数据
 * 3. 安全的API调用
 * 4. 完整的错误分类处理
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react';
import { SecureStorage, secureApiFetch } from '@/utils/security';

// 用户类型定义
export interface User {
  id: string;
  email: string;
  name?: string;
  createdAt: string;
}

// 认证状态接口
export interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

// 认证错误类型
export enum AuthErrorType {
  NETWORK = 'network',
  INVALID_CREDENTIALS = 'invalid_credentials',
  TOKEN_EXPIRED = 'token_expired',
  RATE_LIMITED = 'rate_limited',
  UNKNOWN = 'unknown',
}

// 认证操作接口
export interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
  getAuthError: (error: Error) => { type: AuthErrorType; message: string };
}

// 创建认证Context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// 安全的存储键名
const TOKEN_KEY = 'rss_token';
const USER_KEY = 'rss_user';
const REFRESH_TOKEN_KEY = 'rss_refresh';

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * 安全认证Provider - 完全重写版本
 * 解决所有安全技术债务
 */
export const SecureAuthProvider: React.FC<AuthProviderProps> = ({
  children,
}) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    isLoading: true,
    isAuthenticated: false,
  });

  // 初始化认证状态
  useEffect(() => {
    initializeAuth();
  }, []);

  /**
   * 安全的token验证 - 通过后端API而非客户端解析
   */
  const verifyTokenSafely = async (token: string): Promise<boolean> => {
    try {
      const response = await secureApiFetch('/api/auth/verify', {
        method: 'POST',
        body: JSON.stringify({ token }),
      });

      return response.ok;
    } catch (error) {
      console.error('Token verification failed:', error);
      return false;
    }
  };

  /**
   * 从加密存储恢复认证状态
   */
  const initializeAuth = async (): Promise<void> => {
    try {
      const savedToken = SecureStorage.getItem(TOKEN_KEY);
      const savedUser = SecureStorage.getItem(USER_KEY);

      if (savedToken && savedUser) {
        const user = JSON.parse(savedUser);

        // 安全验证：通过后端验证token而非客户端解析
        const isValid = await verifyTokenSafely(savedToken);
        if (isValid) {
          setAuthState({
            user,
            token: savedToken,
            isLoading: false,
            isAuthenticated: true,
          });
        } else {
          // Token无效，尝试刷新或清除
          await attemptTokenRefresh();
        }
      } else {
        setAuthState(prev => ({ ...prev, isLoading: false }));
      }
    } catch (error) {
      console.error('Failed to initialize auth:', error);
      clearAuthData();
    }
  };

  /**
   * 尝试刷新token
   */
  const attemptTokenRefresh = async (): Promise<void> => {
    try {
      const refreshToken = SecureStorage.getItem(REFRESH_TOKEN_KEY);
      if (!refreshToken) {
        clearAuthData();
        return;
      }

      const response = await secureApiFetch('/api/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      const data = await response.json();
      const { access_token, refresh_token: newRefreshToken, user } = data;

      // 更新加密存储
      SecureStorage.setItem(TOKEN_KEY, access_token);
      SecureStorage.setItem(REFRESH_TOKEN_KEY, newRefreshToken);
      SecureStorage.setItem(USER_KEY, JSON.stringify(user));

      setAuthState({
        user,
        token: access_token,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      console.error('Token refresh failed:', error);
      clearAuthData();
    }
  };

  /**
   * 安全清除认证数据
   */
  const clearAuthData = (): void => {
    SecureStorage.removeItem(TOKEN_KEY);
    SecureStorage.removeItem(USER_KEY);
    SecureStorage.removeItem(REFRESH_TOKEN_KEY);

    setAuthState({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
    });
  };

  /**
   * 分类认证错误
   */
  const getAuthError = (
    error: Error
  ): { type: AuthErrorType; message: string } => {
    const message = error.message.toLowerCase();

    if (message.includes('network') || message.includes('fetch')) {
      return {
        type: AuthErrorType.NETWORK,
        message: '网络连接失败，请检查网络设置',
      };
    }

    if (message.includes('401') || message.includes('unauthorized')) {
      return {
        type: AuthErrorType.INVALID_CREDENTIALS,
        message: '用户名或密码错误',
      };
    }

    if (message.includes('expired') || message.includes('403')) {
      return {
        type: AuthErrorType.TOKEN_EXPIRED,
        message: '登录已过期，请重新登录',
      };
    }

    if (message.includes('rate limit') || message.includes('429')) {
      return {
        type: AuthErrorType.RATE_LIMITED,
        message: '请求过于频繁，请稍后再试',
      };
    }

    return {
      type: AuthErrorType.UNKNOWN,
      message: '登录失败，请稍后重试',
    };
  };

  /**
   * 安全用户登录
   */
  const login = async (email: string, password: string): Promise<void> => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));

      // 输入验证
      if (!email || !password) {
        throw new Error('邮箱和密码不能为空');
      }

      if (!email.includes('@')) {
        throw new Error('请输入有效的邮箱地址');
      }

      const response = await secureApiFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();
      const { user, access_token, refresh_token } = data;

      // 加密存储认证数据
      SecureStorage.setItem(TOKEN_KEY, access_token);
      SecureStorage.setItem(REFRESH_TOKEN_KEY, refresh_token);
      SecureStorage.setItem(USER_KEY, JSON.stringify(user));

      setAuthState({
        user,
        token: access_token,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      setAuthState(prev => ({ ...prev, isLoading: false }));
      throw error; // 让调用者处理具体错误
    }
  };

  /**
   * 安全用户退出
   */
  const logout = async (): Promise<void> => {
    try {
      // 通知服务端注销token
      if (authState.token) {
        await secureApiFetch('/api/auth/logout', {
          method: 'POST',
        }).catch(() => {
          // 忽略服务端注销错误，确保客户端清理
          console.warn('Server logout failed, proceeding with client cleanup');
        });
      }
    } finally {
      // 无论如何都要清除本地数据
      clearAuthData();
    }
  };

  /**
   * 刷新token
   */
  const refreshToken = async (): Promise<void> => {
    await attemptTokenRefresh();
  };

  const contextValue: AuthContextType = {
    ...authState,
    login,
    logout,
    refreshToken,
    getAuthError,
  };

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
};

/**
 * 安全认证Hook
 */
export const useSecureAuth = (): AuthContextType => {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error('useSecureAuth must be used within a SecureAuthProvider');
  }

  return context;
};

/**
 * 获取安全认证头部
 */
export const getSecureAuthHeader = ():
  | { Authorization: string }
  | Record<string, never> => {
  const token = SecureStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export default useSecureAuth;
