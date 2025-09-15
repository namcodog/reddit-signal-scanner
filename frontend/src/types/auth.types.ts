/**
 * 认证系统类型定义
 * 统一所有JWT认证相关的类型接口
 *
 * 基于Linus架构原则：
 * - 数据结构优先：明确定义所有数据契约
 * - 消除特殊情况：统一错误类型和状态定义
 * - 简洁性：避免冗余的类型定义
 */

// 用户信息接口
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

// 认证错误类型枚举
export enum AuthErrorType {
  NETWORK = 'network',
  INVALID_CREDENTIALS = 'invalid_credentials',
  TOKEN_EXPIRED = 'token_expired',
  RATE_LIMITED = 'rate_limited',
  UNKNOWN = 'unknown',
}

// 认证错误信息接口
export interface AuthError {
  type: AuthErrorType;
  message: string;
}

// 登录请求接口
export interface LoginRequest {
  email: string;
  password: string;
}

// 登录响应接口
export interface LoginResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

// Token刷新请求接口
export interface RefreshTokenRequest {
  refresh_token: string;
}

// Token刷新响应接口
export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

// Token验证请求接口
export interface TokenVerifyRequest {
  token: string;
}

// Token验证响应接口
export interface TokenVerifyResponse {
  valid: boolean;
  user?: User;
}

// API响应基础接口
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

// 认证操作接口 - Hook暴露的主要接口
export interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  getAuthError: (error: Error) => AuthError;
}

// 存储键名常量
export const AUTH_STORAGE_KEYS = {
  TOKEN: 'rss_token',
  USER: 'rss_user',
  REFRESH_TOKEN: 'rss_refresh',
} as const;

// API端点常量
export const AUTH_ENDPOINTS = {
  LOGIN: '/api/auth/login',
  LOGOUT: '/api/auth/logout',
  REFRESH: '/api/auth/refresh',
  VERIFY: '/api/auth/verify',
} as const;

// 认证配置常量
export const AUTH_CONFIG = {
  TOKEN_REFRESH_THRESHOLD: 5 * 60 * 1000, // 5分钟
  MAX_RETRY_ATTEMPTS: 3,
  RATE_LIMIT_REQUESTS: 20,
  RATE_LIMIT_WINDOW: 60 * 1000, // 1分钟
} as const;
