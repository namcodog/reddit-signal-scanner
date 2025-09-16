/**
 * 极简HTTP客户端 - Linus架构重构版本
 *
 * 基于Linus原则：
 * - 只做传输层：纯粹的HTTP请求，不管业务逻辑
 * - 数据结构优先：清晰的请求/响应处理
 * - 消除特殊情况：统一的错误处理和认证注入
 *
 * 目标：<40行代码，消除250行的过度抽象
 */

import { SecureStorage } from '@/utils/security';

// 认证存储键
const TOKEN_KEY = 'rss_token';

/**
 * HTTP请求选项
 */
interface RequestOptions extends RequestInit {
  params?: Record<string, string>;
}

/**
 * 极简HTTP客户端类
 * 只负责传输层，不处理业务逻辑
 */
class SimpleHttpClient {
  private baseURL: string;

  constructor(baseURL = '') {
    this.baseURL = baseURL;
  }

  private async request<T>(
    url: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { params, ...fetchOptions } = options;

    // 构建完整URL
    let fullUrl = `${this.baseURL}${url}`;
    if (params) {
      const searchParams = new URLSearchParams(params);
      fullUrl += `?${searchParams}`;
    }

    // 添加认证头
    const token = SecureStorage.getItem(TOKEN_KEY);
    const headers = new Headers(fetchOptions.headers);
    headers.set('Content-Type', 'application/json');
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    const response = await fetch(fullUrl, { ...fetchOptions, headers });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  get<T>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, { ...options, method: 'GET' });
  }

  post<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  put<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  delete<T>(url: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(url, { ...options, method: 'DELETE' });
  }
}

// 导出单例
export const httpClient = new SimpleHttpClient();
export default httpClient;
