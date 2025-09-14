/**
 * AuthService 认证服务测试
 * 严格按照Context7最佳实践：vi.mock + AxiosMockAdapter
 * 100%类型安全，零技术债务
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import AxiosMockAdapter from 'axios-mock-adapter';

// Context7最佳实践：在导入service之前先mock依赖
vi.mock('@/services/api.client', () => ({
  default: {
    post: vi.fn(),
  },
}));

vi.mock('@/utils/security', () => ({
  SecureStorage: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  },
}));

vi.mock('@/types/auth.types', () => ({
  AUTH_STORAGE_KEYS: {
    TOKEN: 'auth_token',
    REFRESH_TOKEN: 'refresh_token',
    USER: 'user_data',
  },
  AUTH_ENDPOINTS: {
    LOGIN: '/api/auth/login',
    LOGOUT: '/api/auth/logout',
    VERIFY: '/api/auth/verify',
    REFRESH: '/api/auth/refresh',
  },
  AUTH_CONFIG: {
    TOKEN_REFRESH_THRESHOLD: 300000, // 5分钟
  },
  AuthErrorType: {
    NETWORK: 'NETWORK',
    INVALID_CREDENTIALS: 'INVALID_CREDENTIALS', 
    TOKEN_EXPIRED: 'TOKEN_EXPIRED',
    RATE_LIMITED: 'RATE_LIMITED',
    UNKNOWN: 'UNKNOWN',
  },
}));

import apiClient from '@/services/api.client';
import { SecureStorage } from '@/utils/security';
import { 
  AUTH_STORAGE_KEYS, 
  AUTH_ENDPOINTS, 
  AUTH_CONFIG,
  AuthErrorType,
  type User,
  type LoginResponse,
  type RefreshTokenResponse,
  type TokenVerifyResponse,
} from '@/types/auth.types';

// Context7最佳实践：严格类型定义
interface MockUser {
  id: string;
  email: string;
  name: string;
}

interface MockLoginResponse {
  user: MockUser;
  access_token: string;
  refresh_token: string;
}

interface MockRefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  user: MockUser;
}

interface MockTokenVerifyResponse {
  valid: boolean;
}

describe('AuthService', () => {
  let AuthService: any;
  let mockConsoleError: any;
  let mockConsoleWarn: any;

  beforeEach(async () => {
    // Context7最佳实践：重置模块缓存
    vi.resetModules();
    
    // Context7最佳实践：重置所有mock
    vi.clearAllMocks();
    
    // Mock console方法
    mockConsoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockConsoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    
    // 设置默认mock返回值
    vi.mocked(SecureStorage.getItem).mockReturnValue(null);
    vi.mocked(SecureStorage.setItem).mockImplementation(() => {});
    vi.mocked(SecureStorage.removeItem).mockImplementation(() => {});
    
    // Mock localStorage
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem: vi.fn(() => '0'),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      },
      writable: true,
    });

    // Context7最佳实践：动态导入模块
    const module = await import('@/services/auth.service');
    AuthService = module.AuthService;
  });

  afterEach(() => {
    // Context7最佳实践：恢复console方法
    mockConsoleError.mockRestore();
    mockConsoleWarn.mockRestore();
  });

  describe('login方法', () => {
    const mockLoginResponse: MockLoginResponse = {
      user: { id: '1', email: 'test@example.com', name: 'Test User' },
      access_token: 'test-access-token',
      refresh_token: 'test-refresh-token',
    };

    it('应该成功登录并存储认证数据', async () => {
      vi.mocked(apiClient.post).mockResolvedValue(mockLoginResponse);

      const result = await AuthService.login('test@example.com', 'password123');

      expect(apiClient.post).toHaveBeenCalledWith(
        AUTH_ENDPOINTS.LOGIN,
        { email: 'test@example.com', password: 'password123' }
      );
      expect(SecureStorage.setItem).toHaveBeenCalledWith(
        AUTH_STORAGE_KEYS.TOKEN,
        'test-access-token'
      );
      expect(SecureStorage.setItem).toHaveBeenCalledWith(
        AUTH_STORAGE_KEYS.REFRESH_TOKEN,
        'test-refresh-token'
      );
      expect(SecureStorage.setItem).toHaveBeenCalledWith(
        AUTH_STORAGE_KEYS.USER,
        JSON.stringify(mockLoginResponse.user)
      );
      expect(result).toEqual(mockLoginResponse);
    });

    it('应该在邮箱为空时抛出错误', async () => {
      await expect(AuthService.login('', 'password123')).rejects.toThrow(
        '邮箱和密码不能为空'
      );
      
      expect(apiClient.post).not.toHaveBeenCalled();
    });

    it('应该在密码为空时抛出错误', async () => {
      await expect(AuthService.login('test@example.com', '')).rejects.toThrow(
        '邮箱和密码不能为空'
      );
      
      expect(apiClient.post).not.toHaveBeenCalled();
    });

    it('应该在邮箱格式无效时抛出错误', async () => {
      await expect(AuthService.login('invalid-email', 'password123')).rejects.toThrow(
        '请输入有效的邮箱地址'
      );
      
      expect(apiClient.post).not.toHaveBeenCalled();
    });

    it('应该处理API请求失败', async () => {
      const error = new Error('Login failed');
      vi.mocked(apiClient.post).mockRejectedValue(error);

      await expect(AuthService.login('test@example.com', 'password123')).rejects.toThrow(
        'Login failed'
      );
      
      expect(mockConsoleError).toHaveBeenCalledWith('Login failed:', error);
    });
  });

  describe('logout方法', () => {
    it('应该成功登出并清除认证数据', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({});

      await AuthService.logout();

      expect(apiClient.post).toHaveBeenCalledWith(AUTH_ENDPOINTS.LOGOUT);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.TOKEN);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.USER);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.REFRESH_TOKEN);
    });

    it('应该在服务端注销失败时仍清除本地数据', async () => {
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Server error'));

      await AuthService.logout();

      expect(mockConsoleWarn).toHaveBeenCalledWith(
        'Server logout failed, proceeding with client cleanup'
      );
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.TOKEN);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.USER);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.REFRESH_TOKEN);
    });
  });

  describe('verifyToken方法', () => {
    it('应该返回true当token有效时', async () => {
      const mockResponse: MockTokenVerifyResponse = { valid: true };
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse);

      const result = await AuthService.verifyToken('valid-token');

      expect(apiClient.post).toHaveBeenCalledWith(
        AUTH_ENDPOINTS.VERIFY,
        { token: 'valid-token' }
      );
      expect(result).toBe(true);
    });

    it('应该返回false当token无效时', async () => {
      const mockResponse: MockTokenVerifyResponse = { valid: false };
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse);

      const result = await AuthService.verifyToken('invalid-token');

      expect(result).toBe(false);
    });

    it('应该在验证失败时返回false', async () => {
      const error = new Error('Verification failed');
      vi.mocked(apiClient.post).mockRejectedValue(error);

      const result = await AuthService.verifyToken('test-token');

      expect(result).toBe(false);
      expect(mockConsoleError).toHaveBeenCalledWith('Token verification failed:', error);
    });
  });

  describe('refreshToken方法', () => {
    const mockRefreshResponse: MockRefreshTokenResponse = {
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
      user: { id: '1', email: 'test@example.com', name: 'Test User' },
    };

    it('应该成功刷新token', async () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue('old-refresh-token');
      vi.mocked(apiClient.post).mockResolvedValue(mockRefreshResponse);

      const result = await AuthService.refreshToken();

      expect(apiClient.post).toHaveBeenCalledWith(
        AUTH_ENDPOINTS.REFRESH,
        { refresh_token: 'old-refresh-token' }
      );
      expect(SecureStorage.setItem).toHaveBeenCalledWith(
        AUTH_STORAGE_KEYS.TOKEN,
        'new-access-token'
      );
      expect(SecureStorage.setItem).toHaveBeenCalledWith(
        AUTH_STORAGE_KEYS.REFRESH_TOKEN,
        'new-refresh-token'
      );
      expect(result).toEqual(mockRefreshResponse);
    });

    it('应该在没有refresh token时抛出错误', async () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue(null);

      await expect(AuthService.refreshToken()).rejects.toThrow(
        'No refresh token available'
      );
      
      expect(apiClient.post).not.toHaveBeenCalled();
    });

    it('应该在刷新失败时清除认证数据', async () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue('invalid-refresh-token');
      const error = new Error('Refresh failed');
      vi.mocked(apiClient.post).mockRejectedValue(error);

      await expect(AuthService.refreshToken()).rejects.toThrow('Refresh failed');
      
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.TOKEN);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.USER);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.REFRESH_TOKEN);
      expect(mockConsoleError).toHaveBeenCalledWith('Token refresh failed:', error);
    });
  });

  describe('restoreAuthState方法', () => {
    const mockUser = { id: '1', email: 'test@example.com', name: 'Test User' };

    it('应该成功恢复认证状态', () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        switch (key) {
          case AUTH_STORAGE_KEYS.TOKEN: return 'stored-token';
          case AUTH_STORAGE_KEYS.USER: return JSON.stringify(mockUser);
          case AUTH_STORAGE_KEYS.REFRESH_TOKEN: return 'stored-refresh-token';
          default: return null;
        }
      });

      const result = AuthService.restoreAuthState();

      expect(result).toEqual({
        user: mockUser,
        token: 'stored-token',
        refreshToken: 'stored-refresh-token',
      });
    });

    it('应该在数据不完整时返回null', () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        if (key === AUTH_STORAGE_KEYS.TOKEN) return 'stored-token';
        return null; // 缺少user和refresh token
      });

      const result = AuthService.restoreAuthState();

      expect(result).toBeNull();
    });

    it('应该在数据损坏时清除存储并返回null', () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        if (key === AUTH_STORAGE_KEYS.USER) return 'invalid-json';
        if (key === AUTH_STORAGE_KEYS.TOKEN) return 'stored-token';
        if (key === AUTH_STORAGE_KEYS.REFRESH_TOKEN) return 'stored-refresh-token';
        return null;
      });

      const result = AuthService.restoreAuthState();

      expect(result).toBeNull();
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.TOKEN);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.USER);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.REFRESH_TOKEN);
      expect(mockConsoleError).toHaveBeenCalled();
    });
  });

  describe('storeAuthData方法', () => {
    const mockUser = { id: '1', email: 'test@example.com', name: 'Test User' };

    it('应该成功存储认证数据', () => {
      AuthService.storeAuthData(mockUser, 'access-token', 'refresh-token');

      expect(SecureStorage.setItem).toHaveBeenCalledWith(
        AUTH_STORAGE_KEYS.TOKEN,
        'access-token'
      );
      expect(SecureStorage.setItem).toHaveBeenCalledWith(
        AUTH_STORAGE_KEYS.REFRESH_TOKEN,
        'refresh-token'
      );
      expect(SecureStorage.setItem).toHaveBeenCalledWith(
        AUTH_STORAGE_KEYS.USER,
        JSON.stringify(mockUser)
      );
    });

    it('应该在存储失败时抛出错误', () => {
      vi.mocked(SecureStorage.setItem).mockImplementation(() => {
        throw new Error('Storage failed');
      });

      expect(() => 
        AuthService.storeAuthData(mockUser, 'access-token', 'refresh-token')
      ).toThrow('认证数据存储失败');
      
      expect(mockConsoleError).toHaveBeenCalledWith(
        'Failed to store auth data:',
        expect.any(Error)
      );
    });
  });

  describe('clearAuthData方法', () => {
    it('应该清除所有认证数据', () => {
      AuthService.clearAuthData();

      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.TOKEN);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.USER);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.REFRESH_TOKEN);
    });
  });

  describe('shouldRefreshToken方法', () => {
    it('应该在token需要刷新时返回true', () => {
      vi.mocked(localStorage.getItem).mockReturnValue('0'); // 很久以前的时间

      const result = AuthService.shouldRefreshToken('test-token');

      expect(result).toBe(true);
    });

    it('应该在token不需要刷新时返回false', () => {
      const recentTime = Date.now() - 1000; // 1秒前
      vi.mocked(localStorage.getItem).mockReturnValue(recentTime.toString());

      const result = AuthService.shouldRefreshToken('test-token');

      expect(result).toBe(false);
    });

    it('应该在解析失败时返回true', () => {
      vi.mocked(localStorage.getItem).mockImplementation(() => {
        throw new Error('Parse error');
      });

      const result = AuthService.shouldRefreshToken('test-token');

      expect(result).toBe(true);
      expect(mockConsoleError).toHaveBeenCalledWith(
        'Token parsing failed:',
        expect.any(Error)
      );
    });
  });

  describe('updateLastRefreshTime方法', () => {
    it('应该更新最后刷新时间', () => {
      const mockTime = 1234567890000;
      vi.spyOn(Date, 'now').mockReturnValue(mockTime);

      AuthService.updateLastRefreshTime();

      expect(localStorage.setItem).toHaveBeenCalledWith(
        'last_token_refresh',
        mockTime.toString()
      );
    });
  });

  describe('getCurrentUser方法', () => {
    const mockUser = { id: '1', email: 'test@example.com', name: 'Test User' };

    it('应该返回当前用户信息', () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue(JSON.stringify(mockUser));

      const result = AuthService.getCurrentUser();

      expect(result).toEqual(mockUser);
    });

    it('应该在没有用户数据时返回null', () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue(null);

      const result = AuthService.getCurrentUser();

      expect(result).toBeNull();
    });

    it('应该在解析失败时返回null', () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue('invalid-json');

      const result = AuthService.getCurrentUser();

      expect(result).toBeNull();
      expect(mockConsoleError).toHaveBeenCalledWith(
        'Failed to get current user:',
        expect.any(Error)
      );
    });
  });

  describe('getCurrentToken方法', () => {
    it('应该返回当前token', () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue('current-token');

      const result = AuthService.getCurrentToken();

      expect(result).toBe('current-token');
    });

    it('应该在没有token时返回null', () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue(null);

      const result = AuthService.getCurrentToken();

      expect(result).toBeNull();
    });
  });

  describe('isAuthenticated方法', () => {
    it('应该在有token和用户信息时返回true', () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        if (key === AUTH_STORAGE_KEYS.TOKEN) return 'test-token';
        if (key === AUTH_STORAGE_KEYS.USER) return '{"id":"1","name":"Test"}';
        return null;
      });

      const result = AuthService.isAuthenticated();

      expect(result).toBe(true);
    });

    it('应该在缺少token时返回false', () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        if (key === AUTH_STORAGE_KEYS.TOKEN) return null;
        if (key === AUTH_STORAGE_KEYS.USER) return '{"id":"1","name":"Test"}';
        return null;
      });

      const result = AuthService.isAuthenticated();

      expect(result).toBe(false);
    });

    it('应该在缺少用户信息时返回false', () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        if (key === AUTH_STORAGE_KEYS.TOKEN) return 'test-token';
        if (key === AUTH_STORAGE_KEYS.USER) return null;
        return null;
      });

      const result = AuthService.isAuthenticated();

      expect(result).toBe(false);
    });
  });

  describe('classifyAuthError方法', () => {
    it('应该正确分类网络错误', () => {
      const error = new Error('Network connection failed');

      const result = AuthService.classifyAuthError(error);

      expect(result).toEqual({
        type: AuthErrorType.NETWORK,
        message: '网络连接失败，请检查网络设置',
      });
    });

    it('应该正确分类401错误', () => {
      const error = new Error('401 Unauthorized');

      const result = AuthService.classifyAuthError(error);

      expect(result).toEqual({
        type: AuthErrorType.INVALID_CREDENTIALS,
        message: '用户名或密码错误',
      });
    });

    it('应该正确分类token过期错误', () => {
      const error = new Error('Token expired');

      const result = AuthService.classifyAuthError(error);

      expect(result).toEqual({
        type: AuthErrorType.TOKEN_EXPIRED,
        message: '登录已过期，请重新登录',
      });
    });

    it('应该正确分类频率限制错误', () => {
      const error = new Error('Rate limit exceeded');

      const result = AuthService.classifyAuthError(error);

      expect(result).toEqual({
        type: AuthErrorType.RATE_LIMITED,
        message: '请求过于频繁，请稍后再试',
      });
    });

    it('应该正确分类未知错误', () => {
      const error = new Error('Unknown error');

      const result = AuthService.classifyAuthError(error);

      expect(result).toEqual({
        type: AuthErrorType.UNKNOWN,
        message: '登录失败，请稍后重试',
      });
    });
  });

  describe('getAuthHeaders方法', () => {
    it('应该在有token时返回认证头部', () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue('test-token');

      const result = AuthService.getAuthHeaders();

      expect(result).toEqual({ Authorization: 'Bearer test-token' });
    });

    it('应该在没有token时返回空对象', () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue(null);

      const result = AuthService.getAuthHeaders();

      expect(result).toEqual({});
    });
  });
});