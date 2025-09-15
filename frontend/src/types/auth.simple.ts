/**
 * 极简认证类型定义 - Linus重构版本
 *
 * 原则：只定义真正需要的核心数据结构
 * 目标：从114行→<25行，消除过度抽象
 */

// 用户信息
export interface User {
  id: string;
  email: string;
  name?: string;
}

// 认证状态
export interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

// 认证操作接口
export interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

// 存储键名
export const AUTH_KEYS = {
  TOKEN: 'rss_token',
  USER: 'rss_user',
  REFRESH_TOKEN: 'rss_refresh',
} as const;
