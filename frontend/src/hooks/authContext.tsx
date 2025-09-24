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
  useState,
  useEffect,
  ReactNode,
} from 'react';
import AuthService from '@/services/auth.service';
import logger from '@/utils/logger';
import {
  AuthState,
  AuthContextType,
  AuthError,
  RegisterRequest,
  type AuthSessionOptions,
} from '@/types/auth.types';

// 创建认证Context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

type AuthProviderComponent = React.FC<AuthProviderProps> & {
  Context: React.Context<AuthContextType | undefined>;
};

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * 认证Provider - 标准化版本
 * 使用新的认证服务和统一的API客户端
 */
const AuthProvider: AuthProviderComponent = ({ children }) => {
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
      logger.error('Failed to initialize auth:', error as Error);
      clearAuthState();
    }
  };

  /**
   * 尝试刷新token
   */
  const attemptTokenRefresh = async (
    options?: AuthSessionOptions
  ): Promise<void> => {
    try {
      const session = await AuthService.refreshToken(options);

      setAuthState({
        user: session.user,
        token: session.accessToken,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      logger.error('Token refresh failed:', error as Error);
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
  const login = async (
    email: string,
    password: string,
    options?: AuthSessionOptions
  ): Promise<void> => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));

      const session = await AuthService.login(email, password, options);

      setAuthState({
        user: session.user,
        token: session.accessToken,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      setAuthState(prev => ({ ...prev, isLoading: false }));
      throw error; // 让调用者处理具体错误
    }
  };

  /**
   * 用户注册
   */
  const register = async (
    payload: RegisterRequest,
    options?: AuthSessionOptions
  ): Promise<void> => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));

      const session = await AuthService.register(payload, options);

      setAuthState({
        user: session.user,
        token: session.accessToken,
        isLoading: false,
        isAuthenticated: true,
      });
    } catch (error) {
      setAuthState(prev => ({ ...prev, isLoading: false }));
      throw error;
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
  const refreshToken = async (
    options?: AuthSessionOptions
  ): Promise<void> => {
    await attemptTokenRefresh(options);
  };

  const resendVerificationEmail = async (email: string): Promise<void> => {
    await AuthService.resendVerificationEmail(email);
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
    register,
    logout,
    refreshToken,
    getAuthError,
    resendVerificationEmail,
  };

  return (
    <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>
  );
};

/**
 * 认证Hook
 * 获取认证状态和操作方法
 */

AuthProvider.Context = AuthContext;

export { AuthProvider };
export default AuthProvider;
