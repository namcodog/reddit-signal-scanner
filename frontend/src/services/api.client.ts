/**
 * 统一API客户端 - 基于axios的HTTP客户端
 *
 * 基于Linus架构原则：
 * - 消除特殊情况：统一HTTP客户端，替代双客户端混乱
 * - 数据结构优先：清晰的请求/响应流程
 * - 安全第一：集成现有安全机制
 *
 * 功能：
 * 1. 统一axios配置和拦截器
 * 2. 自动JWT token注入
 * 3. 请求/响应错误处理
 * 4. 安全头部和CSRF保护
 * 5. 请求频率限制
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { SecurityUtils, SecureStorage } from '@/utils/security';
import { AUTH_STORAGE_KEYS } from '@/types/auth.types';

/**
 * API客户端类 - 统一HTTP请求管理
 */
class ApiClient {
  private axiosInstance: AxiosInstance;
  private clientFingerprint: string;

  constructor() {
    // 创建axios实例
    this.axiosInstance = axios.create({
      baseURL:
        (import.meta as { env?: { VITE_API_BASE_URL?: string } })?.env
          ?.VITE_API_BASE_URL || '',
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // 获取客户端指纹
    this.clientFingerprint = SecurityUtils.getClientFingerprint();

    // 设置请求拦截器
    this.setupRequestInterceptor();

    // 设置响应拦截器
    this.setupResponseInterceptor();
  }

  /**
   * 设置请求拦截器
   * 自动添加认证token和安全头部
   */
  private setupRequestInterceptor(): void {
    this.axiosInstance.interceptors.request.use(
      config => {
        // 检查请求频率限制
        if (!SecurityUtils.checkRateLimit(this.clientFingerprint, 20, 60000)) {
          throw new Error('请求过于频繁，请稍后再试');
        }

        // 添加安全头部
        config.headers['X-Requested-With'] = 'XMLHttpRequest';
        config.headers['X-Client-Fingerprint'] = this.clientFingerprint;

        // 自动注入JWT token
        const token = SecureStorage.getItem(AUTH_STORAGE_KEYS.TOKEN);
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }

        // 添加CSRF token（POST/PUT/DELETE/PATCH请求）
        if (
          config.method &&
          ['post', 'put', 'delete', 'patch'].includes(
            config.method.toLowerCase()
          )
        ) {
          const csrfToken =
            sessionStorage.getItem('csrf_token') ||
            SecurityUtils.generateCSRFToken();
          sessionStorage.setItem('csrf_token', csrfToken);
          config.headers['X-CSRF-Token'] = csrfToken;
        }

        return config;
      },
      error => {
        console.error('Request interceptor error:', error);
        return Promise.reject(error);
      }
    );
  }

  /**
   * 设置响应拦截器
   * 统一错误处理和token刷新
   */
  private setupResponseInterceptor(): void {
    this.axiosInstance.interceptors.response.use(
      (response: AxiosResponse) => {
        return response;
      },
      async error => {
        const originalRequest = error.config;

        // Token过期处理 - 自动刷新token
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            await this.refreshToken();
            // 重新发送原始请求
            const token = SecureStorage.getItem(AUTH_STORAGE_KEYS.TOKEN);
            if (token) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return this.axiosInstance(originalRequest);
          } catch (refreshError) {
            // Token刷新失败，清除认证数据
            this.clearAuthData();
            // 可以在这里触发登录页面跳转
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        // 统一错误处理
        return Promise.reject(this.handleResponseError(error));
      }
    );
  }

  /**
   * 响应错误处理
   * 将axios错误转换为标准化的错误格式
   */
  private handleResponseError(error: {
    response?: { status: number; data?: { message?: string; error?: string } };
    request?: unknown;
    message?: string;
  }): Error {
    if (error.response) {
      // HTTP错误响应
      const status = error.response.status;
      const data = error.response.data;

      switch (status) {
        case 401:
          return new Error('401');
        case 403:
          return new Error('403');
        case 429:
          return new Error('rate limit');
        case 500:
        case 502:
        case 503:
          return new Error('服务器错误，请稍后重试');
        default:
          return new Error(data?.message || data?.error || `HTTP ${status}`);
      }
    } else if (error.request) {
      // 网络错误
      return new Error('网络连接失败，请检查网络设置');
    } else {
      // 其他错误
      return new Error(error.message || '请求失败，请稍后重试');
    }
  }

  /**
   * Token刷新逻辑
   */
  private async refreshToken(): Promise<void> {
    const refreshToken = SecureStorage.getItem(AUTH_STORAGE_KEYS.REFRESH_TOKEN);

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await axios.post('/api/auth/refresh', {
        refresh_token: refreshToken,
      });

      const {
        access_token,
        refresh_token: newRefreshToken,
        user,
      } = response.data;

      // 更新存储的token
      SecureStorage.setItem(AUTH_STORAGE_KEYS.TOKEN, access_token);
      SecureStorage.setItem(AUTH_STORAGE_KEYS.REFRESH_TOKEN, newRefreshToken);
      SecureStorage.setItem(AUTH_STORAGE_KEYS.USER, JSON.stringify(user));
    } catch (error) {
      console.error('Token refresh failed:', error);
      throw error;
    }
  }

  /**
   * 清除认证数据
   */
  private clearAuthData(): void {
    SecureStorage.removeItem(AUTH_STORAGE_KEYS.TOKEN);
    SecureStorage.removeItem(AUTH_STORAGE_KEYS.USER);
    SecureStorage.removeItem(AUTH_STORAGE_KEYS.REFRESH_TOKEN);
  }

  /**
   * 通用GET请求
   */
  async get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.axiosInstance.get<T>(url, config);
    return response.data;
  }

  /**
   * 通用POST请求
   */
  async post<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.axiosInstance.post<T>(url, data, config);
    return response.data;
  }

  /**
   * 通用PUT请求
   */
  async put<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.axiosInstance.put<T>(url, data, config);
    return response.data;
  }

  /**
   * 通用DELETE请求
   */
  async delete<T = unknown>(
    url: string,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.axiosInstance.delete<T>(url, config);
    return response.data;
  }

  /**
   * 通用PATCH请求
   */
  async patch<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<T> {
    const response = await this.axiosInstance.patch<T>(url, data, config);
    return response.data;
  }

  /**
   * 获取原始axios实例（用于需要完全控制的场景）
   */
  getAxiosInstance(): AxiosInstance {
    return this.axiosInstance;
  }
}

// 导出单例实例
export const apiClient = new ApiClient();

// 导出类型，供其他模块使用
export default apiClient;
export type { AxiosRequestConfig, AxiosResponse } from 'axios';
