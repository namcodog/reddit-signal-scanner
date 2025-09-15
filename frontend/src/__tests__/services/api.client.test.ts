/**
 * ApiClient API客户端测试
 * 严格按照Context7最佳实践：AxiosMockAdapter + vi.mock
 * 100%类型安全，零技术债务
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import AxiosMockAdapter from 'axios-mock-adapter';
import axios from 'axios';

// Context7最佳实践：使用vi.mock模拟依赖
vi.mock('@/utils/security', () => ({
  SecurityUtils: {
    getClientFingerprint: vi.fn(() => 'test-fingerprint-123'),
    checkRateLimit: vi.fn(() => true),
    generateCSRFToken: vi.fn(() => 'test-csrf-token'),
  },
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
}));

import { SecurityUtils, SecureStorage } from '@/utils/security';
import { AUTH_STORAGE_KEYS } from '@/types/auth.types';

// 严格类型定义
interface MockTokenRefreshResponse {
  access_token: string;
  refresh_token: string;
  user: { id: string; name: string };
}

describe('ApiClient', () => {
  let mockAxios: AxiosMockAdapter;
  let originalLocation: Location;

  beforeEach(async () => {
    // Context7最佳实践：重置模块缓存
    vi.resetModules();
    
    // Context7最佳实践：重置所有mock
    vi.clearAllMocks();
    
    // 设置默认mock返回值
    vi.mocked(SecurityUtils.getClientFingerprint).mockReturnValue('test-fingerprint-123');
    vi.mocked(SecurityUtils.checkRateLimit).mockReturnValue(true);
    vi.mocked(SecurityUtils.generateCSRFToken).mockReturnValue('test-csrf-token');
    vi.mocked(SecureStorage.getItem).mockReturnValue(null);
    
    // Context7最佳实践：mock window.location
    originalLocation = window.location;
    delete (window as any).location;
    window.location = { href: '' } as Location;
    
    // Context7最佳实践：mock sessionStorage
    Object.defineProperty(window, 'sessionStorage', {
      value: {
        getItem: vi.fn(() => 'test-csrf-token'),
        setItem: vi.fn(),
        removeItem: vi.fn(),
      },
      writable: true,
    });

    // Context7最佳实践：创建axios mock adapter
    mockAxios = new AxiosMockAdapter(axios);
  });

  afterEach(() => {
    // Context7最佳实践：清理mock adapter
    mockAxios.restore();
    
    // 恢复原始location
    window.location = originalLocation;
    
    // Context7最佳实践：重置请求历史
    mockAxios.resetHistory();
  });

  describe('构造函数和初始化', () => {
    it('应该正确初始化axios实例', async () => {
      // Context7方法：动态导入模块
      const { apiClient } = await import('@/services/api.client');

      const axiosInstance = apiClient.getAxiosInstance();
      expect(axiosInstance.defaults.timeout).toBe(10000);
      expect(axiosInstance.defaults.headers['Content-Type']).toBe('application/json');
    });

    it('应该从环境变量读取baseURL', async () => {
      vi.stubEnv('VITE_API_BASE_URL', 'https://test-api.example.com');
      
      const { apiClient } = await import('@/services/api.client');
      
      const axiosInstance = apiClient.getAxiosInstance();
      expect(axiosInstance.defaults.baseURL).toBe('https://test-api.example.com');
      
      vi.unstubAllEnvs();
    });

    it('应该获取客户端指纹', async () => {
      await import('@/services/api.client');

      expect(SecurityUtils.getClientFingerprint).toHaveBeenCalledTimes(1);
    });
  });

  describe('HTTP方法测试', () => {
    let apiClient: any;

    beforeEach(async () => {
      const module = await import('@/services/api.client');
      apiClient = module.apiClient;
    });

    it('应该正确执行GET请求', async () => {
      const testData = { users: [{ id: 1, name: 'John' }] };
      
      // Context7方法：使用AxiosMockAdapter mock响应
      mockAxios.onGet('/api/users').reply(200, testData);

      const result = await apiClient.get('/api/users');

      expect(result).toEqual(testData);
      expect(mockAxios.history.get).toHaveLength(1);
      expect(mockAxios.history.get[0].url).toBe('/api/users');
    });

    it('应该正确执行POST请求', async () => {
      const requestData = { name: 'John', email: 'john@example.com' };
      const responseData = { id: 1, ...requestData };
      
      mockAxios.onPost('/api/users', requestData).reply(201, responseData);

      const result = await apiClient.post('/api/users', requestData);

      expect(result).toEqual(responseData);
      expect(mockAxios.history.post).toHaveLength(1);
      expect(JSON.parse(mockAxios.history.post[0].data)).toEqual(requestData);
    });

    it('应该正确执行PUT请求', async () => {
      const requestData = { id: 1, name: 'John Updated' };
      
      mockAxios.onPut('/api/users/1', requestData).reply(200, requestData);

      const result = await apiClient.put('/api/users/1', requestData);

      expect(result).toEqual(requestData);
      expect(mockAxios.history.put).toHaveLength(1);
    });

    it('应该正确执行DELETE请求', async () => {
      mockAxios.onDelete('/api/users/1').reply(204);

      await apiClient.delete('/api/users/1');

      expect(mockAxios.history.delete).toHaveLength(1);
      expect(mockAxios.history.delete[0].url).toBe('/api/users/1');
    });

    it('应该正确执行PATCH请求', async () => {
      const requestData = { name: 'John Patched' };
      const responseData = { id: 1, name: 'John Patched', email: 'john@example.com' };
      
      mockAxios.onPatch('/api/users/1', requestData).reply(200, responseData);

      const result = await apiClient.patch('/api/users/1', requestData);

      expect(result).toEqual(responseData);
      expect(mockAxios.history.patch).toHaveLength(1);
    });
  });

  describe('请求拦截器测试', () => {
    let apiClient: any;

    beforeEach(async () => {
      const module = await import('@/services/api.client');
      apiClient = module.apiClient;
    });

    it('应该在请求中添加安全头部', async () => {
      mockAxios.onGet('/api/test').reply(200, {});

      await apiClient.get('/api/test');

      const request = mockAxios.history.get[0];
      expect(request.headers['X-Requested-With']).toBe('XMLHttpRequest');
      expect(request.headers['X-Client-Fingerprint']).toBe('test-fingerprint-123');
    });

    it('应该在有token时添加Authorization头部', async () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        if (key === AUTH_STORAGE_KEYS.TOKEN) return 'test-jwt-token';
        return null;
      });

      mockAxios.onGet('/api/test').reply(200, {});

      await apiClient.get('/api/test');

      const request = mockAxios.history.get[0];
      expect(request.headers.Authorization).toBe('Bearer test-jwt-token');
    });

    it('应该在POST请求中添加CSRF token', async () => {
      mockAxios.onPost('/api/test').reply(200, {});

      await apiClient.post('/api/test', { data: 'test' });

      const request = mockAxios.history.post[0];
      expect(request.headers['X-CSRF-Token']).toBe('test-csrf-token');
    });

    it('应该检查请求频率限制', async () => {
      vi.mocked(SecurityUtils.checkRateLimit).mockReturnValue(false);

      await expect(apiClient.get('/api/test')).rejects.toThrow('请求过于频繁，请稍后再试');
      
      expect(SecurityUtils.checkRateLimit).toHaveBeenCalledWith('test-fingerprint-123', 20, 60000);
      expect(mockAxios.history.get).toHaveLength(0);
    });
  });

  describe('响应拦截器和错误处理', () => {
    let apiClient: any;

    beforeEach(async () => {
      const module = await import('@/services/api.client');
      apiClient = module.apiClient;
    });

    it('应该处理401错误并尝试刷新token', async () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        if (key === AUTH_STORAGE_KEYS.REFRESH_TOKEN) return 'test-refresh-token';
        if (key === AUTH_STORAGE_KEYS.TOKEN) return 'new-jwt-token';
        return null;
      });

      const refreshResponse: MockTokenRefreshResponse = {
        access_token: 'new-jwt-token',
        refresh_token: 'new-refresh-token',
        user: { id: '1', name: 'John' },
      };

      // Context7方法：mock token刷新接口
      mockAxios.onPost('/api/auth/refresh').reply(200, refreshResponse);
      
      // 第一次请求返回401，第二次重试成功
      mockAxios
        .onGet('/api/protected')
        .replyOnce(401)
        .onGet('/api/protected')
        .reply(200, { data: 'success' });

      const result = await apiClient.get('/api/protected');

      expect(result).toEqual({ data: 'success' });
      expect(mockAxios.history.get).toHaveLength(2); // 原始请求 + 重试
      expect(mockAxios.history.post).toHaveLength(1); // token刷新
      expect(SecureStorage.setItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.TOKEN, 'new-jwt-token');
    });

    it('应该在token刷新失败时清除认证数据并跳转登录', async () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        if (key === AUTH_STORAGE_KEYS.REFRESH_TOKEN) return 'invalid-refresh-token';
        return null;
      });

      mockAxios.onPost('/api/auth/refresh').reply(401);
      mockAxios.onGet('/api/protected').reply(401);

      await expect(apiClient.get('/api/protected')).rejects.toThrow();

      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.TOKEN);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.USER);
      expect(SecureStorage.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEYS.REFRESH_TOKEN);
      expect(window.location.href).toBe('/login');
    });

    it('应该处理网络错误', async () => {
      // Context7方法：使用networkError模拟网络错误
      mockAxios.onGet('/api/test').networkError();

      await expect(apiClient.get('/api/test')).rejects.toThrow('Network Error');
    });

    it('应该处理服务器错误', async () => {
      mockAxios.onGet('/api/test').reply(500, { message: '内部服务器错误' });

      await expect(apiClient.get('/api/test')).rejects.toThrow('服务器错误，请稍后重试');
    });

    it('应该处理403禁止访问错误', async () => {
      mockAxios.onGet('/api/test').reply(403);

      await expect(apiClient.get('/api/test')).rejects.toThrow('403');
    });

    it('应该处理429频率限制错误', async () => {
      mockAxios.onGet('/api/test').reply(429);

      await expect(apiClient.get('/api/test')).rejects.toThrow('rate limit');
    });

    it('应该处理自定义错误消息', async () => {
      mockAxios.onGet('/api/test').reply(400, { message: '自定义错误消息' });

      await expect(apiClient.get('/api/test')).rejects.toThrow('自定义错误消息');
    });
  });

  describe('validateTaskId方法', () => {
    let apiClient: any;

    beforeEach(async () => {
      const module = await import('@/services/api.client');
      apiClient = module.apiClient;
    });

    it('应该在任务存在时返回true', async () => {
      mockAxios.onGet('/api/tasks/valid-task-id/status').reply(200, { status: 'completed' });

      const result = await apiClient.validateTaskId('valid-task-id');

      expect(result).toBe(true);
      expect(mockAxios.history.get).toHaveLength(1);
      expect(mockAxios.history.get[0].url).toBe('/api/tasks/valid-task-id/status');
    });

    it('应该在任务不存在时返回false', async () => {
      mockAxios.onGet('/api/tasks/invalid-task-id/status').reply(404);

      const result = await apiClient.validateTaskId('invalid-task-id');

      expect(result).toBe(false);
    });

    it('应该在网络错误时返回false', async () => {
      mockAxios.onGet('/api/tasks/test-task/status').networkError();

      const result = await apiClient.validateTaskId('test-task');

      expect(result).toBe(false);
    });
  });

  describe('便捷导出函数', () => {
    it('应该正确导出validateTaskId函数', async () => {
      const { validateTaskId } = await import('@/services/api.client');
      
      mockAxios.onGet('/api/tasks/test-id/status').reply(200, {});

      const result = await validateTaskId('test-id');

      expect(result).toBe(true);
    });
  });

  describe('获取原始axios实例', () => {
    it('应该返回配置好的axios实例', async () => {
      const { apiClient } = await import('@/services/api.client');

      const axiosInstance = apiClient.getAxiosInstance();

      expect(axiosInstance).toBeDefined();
      expect(axiosInstance.defaults.timeout).toBe(10000);
      expect(axiosInstance.defaults.headers['Content-Type']).toBe('application/json');
    });
  });

  describe('边界情况和容错', () => {
    let apiClient: any;

    beforeEach(async () => {
      const module = await import('@/services/api.client');
      apiClient = module.apiClient;
    });

    it('应该处理空的刷新token', async () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue(null);
      
      mockAxios.onGet('/api/protected').reply(401);

      await expect(apiClient.get('/api/protected')).rejects.toThrow();
      
      expect(mockAxios.history.post).toHaveLength(0); // 没有尝试刷新token
    });

    it('应该处理重复的401错误（防止无限重试）', async () => {
      vi.mocked(SecureStorage.getItem).mockImplementation((key: string) => {
        if (key === AUTH_STORAGE_KEYS.REFRESH_TOKEN) return 'test-refresh-token';
        return null;
      });

      mockAxios.onPost('/api/auth/refresh').reply(200, {
        access_token: 'new-token',
        refresh_token: 'new-refresh-token',
        user: { id: '1', name: 'John' },
      });
      
      // 两次请求都返回401
      mockAxios.onGet('/api/protected').reply(401);

      await expect(apiClient.get('/api/protected')).rejects.toThrow();
      
      expect(mockAxios.history.get).toHaveLength(2); // 原始请求 + 1次重试
      expect(mockAxios.history.post).toHaveLength(1); // 只刷新1次token
    });

    it('应该处理非HTTP错误', async () => {
      // Context7方法：使用timeout模拟超时
      mockAxios.onGet('/api/test').timeout();

      await expect(apiClient.get('/api/test')).rejects.toThrow();
    });

    it('应该处理没有refresh token的情况', async () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue(null);
      
      mockAxios.onGet('/api/protected').reply(401);

      await expect(apiClient.get('/api/protected')).rejects.toThrow();
      
      // 应该直接跳转到登录页面
      expect(window.location.href).toBe('/login');
    });
  });
});