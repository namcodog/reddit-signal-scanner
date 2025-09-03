/**
 * 标准认证Hook - 统一的认证状态管理
 *
 * 基于Linus架构原则：
 * - 数据结构优先：清晰的状态管理
 * - 消除特殊情况：统一的错误处理
 * - 向后兼容：保持API接口不变
 *
 * 重构说明：
 * 1. 使用新的AuthService处理业务逻辑
 * 2. 使用统一的axios API客户端
 * 3. 保持原有的安全特性
 * 4. 标准化文件结构和命名
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from 'react';
import AuthService from '@/services/auth.service';
import { AuthState, AuthContextType, AuthError } from '@/types/auth.types';

// 创建认证Context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * 认证Provider - 标准化版本
 * 使用新的认证服务和统一的API客户端
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
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
   * 初始化认证状态
   * 从存储中恢复认证信息并验证token有效性
   */
  const initializeAuth = async (): Promise<void> => {
    try {
      const authData = AuthService.restoreAuthState();

      if (authData) {
        const { user, token } = authData;

        // 安全验证：通过后端验证token
        const isValid = await AuthService.verifyToken(token);

        if (isValid) {
          setAuthState({
            user,
            token,
            isLoading: false,
            isAuthenticated: true,
          });
        } else {
          // Token无效，尝试刷新
          await attemptTokenRefresh();
        }
      } else {
        setAuthState(prev => ({ ...prev, isLoading: false }));
      }
    } catch (error) {
      console.error('Failed to initialize auth:', error);
      clearAuthState();
    }
  };

  /**
   * 尝试刷新token
   */
  const attemptTokenRefresh = async (): Promise<void> => {
    try {
      const response = await AuthService.refreshToken();
      const { user, access_token } = response;

      setAuthState({
        user,
        token: access_token,
        isLoading: false,
        isAuthenticated: true,
      });

      // 更新最后刷新时间
      AuthService.updateLastRefreshTime();
    } catch (error) {
      console.error('Token refresh failed:', error);
      clearAuthState();
    }
  };

  /**
   * 清除认证状态
   */
  const clearAuthState = (): void => {
    AuthService.clearAuthData();
    setAuthState({
      user: null,
      token: null,
      isLoading: false,
      isAuthenticated: false,
    });
  };

  /**
   * 用户登录
   * @param email 邮箱
   * @param password 密码
   */
  const login = async (email: string, password: string): Promise<void> => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));

      const response = await AuthService.login(email, password);
      const { user, access_token } = response;

      setAuthState({
        user,
        token: access_token,
        isLoading: false,
        isAuthenticated: true,
      });

      // 更新最后刷新时间
      AuthService.updateLastRefreshTime();
    } catch (error) {
      setAuthState(prev => ({ ...prev, isLoading: false }));
      throw error; // 让调用者处理具体错误
    }
  };

  /**
   * 用户登出
   */
  const logout = async (): Promise<void> => {
    try {
      await AuthService.logout();
    } finally {
      // 无论服务端是否成功，都要清除本地状态
      clearAuthState();
    }
  };

  /**
   * 手动刷新token
   */
  const refreshToken = async (): Promise<void> => {
    await attemptTokenRefresh();
  };

  /**
   * 获取分类后的认证错误
   * @param error 错误对象
   * @returns 分类后的错误信息
   */
  const getAuthError = (error: Error): AuthError => {
    return AuthService.classifyAuthError(error);
  };

  // Context值
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
 * 认证Hook
 * 获取认证状态和操作方法
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);

  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
};

/**
 * 获取认证头部的工具函数
 * @returns 认证头部对象
 */
export const getAuthHeaders = ():
  | { Authorization: string }
  | Record<string, never> => {
  return AuthService.getAuthHeaders();
};

// 向后兼容：导出别名
export const SecureAuthProvider = AuthProvider;
export const useSecureAuth = useAuth;
export const getSecureAuthHeader = getAuthHeaders;

// 默认导出
export default useAuth;
