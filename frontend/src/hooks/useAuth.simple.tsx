/**
 * 智能认证Hook - Linus架构重构版本
 *
 * 基于Linus原则：
 * - 消除中间层：直接管理状态+HTTP调用，无需Service层
 * - 数据结构优先：清晰的认证状态管理
 * - 3层调用链：用户输入→Hook→HTTP→服务器
 *
 * 目标：整合原来3个文件的功能到<100行
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react';
import { SecureStorage } from '@/utils/security';
import httpClient from '@/services/http.client';
import {
  User,
  AuthState,
  AuthContextType,
  AUTH_KEYS,
} from '@/types/auth.simple';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  });

  // 初始化认证状态
  useEffect(() => {
    const initAuth = async () => {
      const savedUser = SecureStorage.getItem(AUTH_KEYS.USER);
      const savedToken = SecureStorage.getItem(AUTH_KEYS.TOKEN);

      if (savedUser && savedToken) {
        try {
          // 验证token有效性
          await httpClient.get('/api/auth/verify');
          setAuthState({
            user: JSON.parse(savedUser),
            isLoading: false,
            isAuthenticated: true,
          });
        } catch {
          // Token无效，尝试刷新
          await refreshToken();
        }
      } else {
        setAuthState(prev => ({ ...prev, isLoading: false }));
      }
    };

    initAuth();
  }, []);

  // Token刷新逻辑
  const refreshToken = async (): Promise<void> => {
    try {
      const refreshToken = SecureStorage.getItem(AUTH_KEYS.REFRESH_TOKEN);
      if (!refreshToken) throw new Error('No refresh token');

      const response = await httpClient.post<{
        access_token: string;
        refresh_token: string;
        user: User;
      }>('/api/auth/refresh', { refresh_token: refreshToken });

      // 存储新token
      SecureStorage.setItem(AUTH_KEYS.TOKEN, response.access_token);
      SecureStorage.setItem(AUTH_KEYS.REFRESH_TOKEN, response.refresh_token);
      SecureStorage.setItem(AUTH_KEYS.USER, JSON.stringify(response.user));

      setAuthState({
        user: response.user,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch {
      // 刷新失败，清除所有数据
      clearAuth();
    }
  };

  // 清除认证数据
  const clearAuth = (): void => {
    SecureStorage.removeItem(AUTH_KEYS.TOKEN);
    SecureStorage.removeItem(AUTH_KEYS.USER);
    SecureStorage.removeItem(AUTH_KEYS.REFRESH_TOKEN);
    setAuthState({
      user: null,
      isLoading: false,
      isAuthenticated: false,
    });
  };

  // 登录
  const login = async (email: string, password: string): Promise<void> => {
    setAuthState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await httpClient.post<{
        user: User;
        access_token: string;
        refresh_token: string;
      }>('/api/auth/login', { email, password });

      // 存储认证数据
      SecureStorage.setItem(AUTH_KEYS.TOKEN, response.access_token);
      SecureStorage.setItem(AUTH_KEYS.REFRESH_TOKEN, response.refresh_token);
      SecureStorage.setItem(AUTH_KEYS.USER, JSON.stringify(response.user));

      setAuthState({
        user: response.user,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      setAuthState(prev => ({ ...prev, isLoading: false }));
      throw error;
    }
  };

  // 登出
  const logout = async (): Promise<void> => {
    try {
      await httpClient.post('/api/auth/logout');
    } finally {
      clearAuth();
    }
  };

  return (
    <AuthContext.Provider value={{ ...authState, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

// Hook
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// 向后兼容别名
export const SecureAuthProvider = AuthProvider;
export const useSecureAuth = useAuth;

export default useAuth;
