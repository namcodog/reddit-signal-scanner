/**
 * 认证服务 - JWT认证业务逻辑实现
 *
 * 基于Linus架构原则：
 * - 数据结构优先：清晰的认证状态管理
 * - 消除特殊情况：统一错误处理逻辑
 * - 安全第一：保留原有优秀的安全机制
 *
 * 功能：
 * 1. 用户登录/登出
 * 2. Token验证和刷新
 * 3. 安全的认证状态管理
 * 4. 统一的错误处理
 */

import apiClient from './api.client';
import logger from '@/utils/logger';
import { SecureStorage } from '@/utils/security';
import {
  User,
  LoginRequest,
  LoginResponse,
  RefreshTokenResponse,
  TokenVerifyResponse,
  AuthError,
  AuthErrorType,
  AUTH_STORAGE_KEYS,
  AUTH_ENDPOINTS,
  AUTH_CONFIG,
} from '@/types/auth.types';

/**
 * 认证服务类
 * 包含所有认证相关的业务逻辑
 */
export class AuthService {
  /**
   * 用户登录
   * @param email 用户邮箱
   * @param password 用户密码
   * @returns 登录响应数据
   */
  static async login(email: string, password: string): Promise<LoginResponse> {
    // 输入验证
    if (!email || !password) {
      throw new Error('邮箱和密码不能为空');
    }

    if (!email.includes('@')) {
      throw new Error('请输入有效的邮箱地址');
    }

    const loginData: LoginRequest = { email, password };

    try {
      const response = await apiClient.post<LoginResponse>(
        AUTH_ENDPOINTS.LOGIN,
        loginData
      );

      const { user, access_token, refresh_token } = response;

      // 加密存储认证数据
      this.storeAuthData(user, access_token, refresh_token);

      return response;
    } catch (error) {
      logger.error('Login failed:', error as Error);
      throw error;
    }
  }

  /**
   * 用户登出
   */
  static async logout(): Promise<void> {
    try {
      // 通知服务端注销token
      await apiClient.post(AUTH_ENDPOINTS.LOGOUT).catch(() => {
        // 忽略服务端注销错误，确保客户端清理
        logger.warn('Server logout failed, proceeding with client cleanup');
      });
    } finally {
      // 无论如何都要清除本地数据
      this.clearAuthData();
    }
  }

  /**
   * Token验证
   * @param token JWT token
   * @returns 是否有效
   */
  static async verifyToken(token: string): Promise<boolean> {
    try {
      const response = await apiClient.post<TokenVerifyResponse>(
        AUTH_ENDPOINTS.VERIFY,
        { token }
      );

      return response.valid;
    } catch (error) {
      logger.error('Token verification failed:', error as Error);
      return false;
    }
  }

  /**
   * 刷新Token
   * @returns 刷新后的认证数据
   */
  static async refreshToken(): Promise<RefreshTokenResponse> {
    const refreshToken = SecureStorage.getItem(AUTH_STORAGE_KEYS.REFRESH_TOKEN);

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await apiClient.post<RefreshTokenResponse>(
        AUTH_ENDPOINTS.REFRESH,
        { refresh_token: refreshToken }
      );

      const { access_token, refresh_token: newRefreshToken, user } = response;

      // 更新存储的token
      this.storeAuthData(user, access_token, newRefreshToken);

      return response;
    } catch (error) {
      logger.error('Token refresh failed:', error as Error);
      // 刷新失败，清除认证数据
      this.clearAuthData();
      throw error;
    }
  }

  /**
   * 从存储中恢复认证状态
   * @returns 存储的认证数据或null
   */
  static restoreAuthState(): {
    user: User;
    token: string;
    refreshToken: string;
  } | null {
    try {
      const token = SecureStorage.getItem(AUTH_STORAGE_KEYS.TOKEN);
      const userJson = SecureStorage.getItem(AUTH_STORAGE_KEYS.USER);
      const refreshToken = SecureStorage.getItem(
        AUTH_STORAGE_KEYS.REFRESH_TOKEN
      );

      if (token && userJson && refreshToken) {
        const user = JSON.parse(userJson);
        return { user, token, refreshToken };
      }

      return null;
    } catch (error) {
      logger.error('Failed to restore auth state:', error as Error);
      // 数据损坏，清除存储
      this.clearAuthData();
      return null;
    }
  }

  /**
   * 安全存储认证数据
   * @param user 用户信息
   * @param accessToken 访问token
   * @param refreshToken 刷新token
   */
  static storeAuthData(
    user: User,
    accessToken: string,
    refreshToken: string
  ): void {
    try {
      SecureStorage.setItem(AUTH_STORAGE_KEYS.TOKEN, accessToken);
      SecureStorage.setItem(AUTH_STORAGE_KEYS.REFRESH_TOKEN, refreshToken);
      SecureStorage.setItem(AUTH_STORAGE_KEYS.USER, JSON.stringify(user));
    } catch (error) {
      logger.error('Failed to store auth data:', error as Error);
      throw new Error('认证数据存储失败');
    }
  }

  /**
   * 清除认证数据
   */
  static clearAuthData(): void {
    SecureStorage.removeItem(AUTH_STORAGE_KEYS.TOKEN);
    SecureStorage.removeItem(AUTH_STORAGE_KEYS.USER);
    SecureStorage.removeItem(AUTH_STORAGE_KEYS.REFRESH_TOKEN);
  }

  /**
   * 检查token是否即将过期
   * @param token JWT token
   * @returns 是否需要刷新
   */
  static shouldRefreshToken(_token: string): boolean {
    try {
      // 这里可以解析JWT token来检查过期时间
      // 为了安全起见，我们采用更保守的策略：定期刷新
      const lastRefresh = parseInt(
        localStorage.getItem('last_token_refresh') || '0'
      );
      const now = Date.now();

      return now - lastRefresh > AUTH_CONFIG.TOKEN_REFRESH_THRESHOLD;
    } catch (error) {
      logger.error('Token parsing failed:', error as Error);
      return true; // 解析失败时建议刷新
    }
  }

  /**
   * 更新最后刷新时间
   */
  static updateLastRefreshTime(): void {
    localStorage.setItem('last_token_refresh', Date.now().toString());
  }

  /**
   * 获取当前用户信息
   * @returns 用户信息或null
   */
  static getCurrentUser(): User | null {
    try {
      const userJson = SecureStorage.getItem(AUTH_STORAGE_KEYS.USER);
      return userJson ? JSON.parse(userJson) : null;
    } catch (error) {
      logger.error('Failed to get current user:', error as Error);
      return null;
    }
  }

  /**
   * 获取当前token
   * @returns token或null
   */
  static getCurrentToken(): string | null {
    return SecureStorage.getItem(AUTH_STORAGE_KEYS.TOKEN);
  }

  /**
   * 检查是否已认证
   * @returns 是否已认证
   */
  static isAuthenticated(): boolean {
    const token = this.getCurrentToken();
    const user = this.getCurrentUser();
    return !!(token && user);
  }

  /**
   * 分类认证错误
   * @param error 错误对象
   * @returns 分类后的错误信息
   */
  static classifyAuthError(error: Error): AuthError {
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
  }

  /**
   * 获取认证头部
   * @returns 认证头部对象
   */
  static getAuthHeaders(): { Authorization: string } | Record<string, never> {
    const token = this.getCurrentToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }
}

export default AuthService;
