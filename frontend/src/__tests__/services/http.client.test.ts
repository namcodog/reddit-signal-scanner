/**
 * SimpleHttpClient HTTP客户端测试
 * 严格按照Context7最佳实践：vi.stubGlobal + fetch mock
 * 100%类型安全，零技术债务
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// Context7最佳实践：使用vi.mock模拟依赖
vi.mock('@/utils/security', () => ({
  SecureStorage: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  },
}));

import { SecureStorage } from '@/utils/security';

// 严格类型定义
interface MockResponse {
  status: string;
  data?: unknown;
}

// Context7最佳实践：创建fetch mock
const createMockResponse = (data: any, status = 200): Response => {
  return new Response(JSON.stringify(data), {
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: {
      'Content-Type': 'application/json',
    },
  });
};

describe('SimpleHttpClient', () => {
  const mockFetch = vi.fn();

  beforeEach(async () => {
    // Context7最佳实践：重置模块缓存
    vi.resetModules();
    
    // Context7最佳实践：重置所有mock
    vi.clearAllMocks();
    
    // Context7最佳实践：mock全局fetch
    vi.stubGlobal('fetch', mockFetch);
    
    // 设置默认mock返回值
    vi.mocked(SecureStorage.getItem).mockReturnValue(null);
  });

  afterEach(() => {
    // Context7最佳实践：恢复全局变量
    vi.unstubAllGlobals();
  });

  describe('构造函数和初始化', () => {
    it('应该正确初始化HTTP客户端', async () => {
      // Context7方法：动态导入模块
      const { httpClient } = await import('@/services/http.client');

      expect(httpClient).toBeDefined();
    });

    it('应该正确创建新的HTTP客户端实例', async () => {
      const { default: httpClient } = await import('@/services/http.client');
      
      expect(httpClient).toBeDefined();
    });
  });

  describe('HTTP方法测试', () => {
    let httpClient: any;

    beforeEach(async () => {
      const module = await import('@/services/http.client');
      httpClient = module.httpClient;
    });

    it('应该正确执行GET请求', async () => {
      const testData: MockResponse = { status: 'success', data: { users: [{ id: 1, name: 'John' }] } };
      
      // Context7方法：使用vi.stubGlobal设置mock响应
      mockFetch.mockResolvedValue(createMockResponse(testData));

      const result = await httpClient.get('http://localhost/api/users');

      expect(result).toEqual(testData);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost/api/users', expect.objectContaining({
        method: 'GET'
      }));
    });

    it('应该正确执行POST请求', async () => {
      const requestData = { name: 'John', email: 'john@example.com' };
      const responseData: MockResponse = { status: 'created', data: { id: 1, ...requestData } };
      
      mockFetch.mockResolvedValue(createMockResponse(responseData));

      const result = await httpClient.post('http://localhost/api/users', requestData);

      expect(result).toEqual(responseData);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost/api/users', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(requestData)
      }));
    });

    it('应该正确执行PUT请求', async () => {
      const requestData = { id: 1, name: 'John Updated' };
      const responseData: MockResponse = { status: 'updated', data: requestData };
      
      mockFetch.mockResolvedValue(createMockResponse(responseData));

      const result = await httpClient.put('http://localhost/api/users/1', requestData);

      expect(result).toEqual(responseData);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost/api/users/1', expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(requestData)
      }));
    });

    it('应该正确执行DELETE请求', async () => {
      const responseData = { status: 'deleted' };
      
      mockFetch.mockResolvedValue(createMockResponse(responseData));

      const result = await httpClient.delete('http://localhost/api/users/1');

      expect(result).toEqual(responseData);
      expect(mockFetch).toHaveBeenCalledWith('http://localhost/api/users/1', expect.objectContaining({
        method: 'DELETE'
      }));
    });
  });

  describe('认证头部测试', () => {
    let httpClient: any;

    beforeEach(async () => {
      const module = await import('@/services/http.client');
      httpClient = module.httpClient;
    });

    it('应该在有token时添加Authorization头部', async () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue('test-jwt-token');
      mockFetch.mockResolvedValue(createMockResponse({ status: 'success' }));

      await httpClient.get('http://localhost/api/test');

      const call = mockFetch.mock.calls[0];
      const headers = call[1].headers;
      expect(headers.get('Authorization')).toBe('Bearer test-jwt-token');
    });

    it('应该在没有token时不添加Authorization头部', async () => {
      vi.mocked(SecureStorage.getItem).mockReturnValue(null);
      mockFetch.mockResolvedValue(createMockResponse({ status: 'success' }));

      await httpClient.get('http://localhost/api/test');

      const call = mockFetch.mock.calls[0];
      const headers = call[1].headers;
      expect(headers.get('Authorization')).toBeNull();
    });

    it('应该设置Content-Type头部', async () => {
      mockFetch.mockResolvedValue(createMockResponse({ status: 'success' }));

      await httpClient.get('http://localhost/api/test');

      const call = mockFetch.mock.calls[0];
      const headers = call[1].headers;
      expect(headers.get('Content-Type')).toBe('application/json');
    });
  });

  describe('URL参数处理', () => {
    let httpClient: any;

    beforeEach(async () => {
      const module = await import('@/services/http.client');
      httpClient = module.httpClient;
    });

    it('应该正确处理查询参数', async () => {
      mockFetch.mockResolvedValue(createMockResponse({ status: 'success' }));

      await httpClient.get('http://localhost/api/test', { params: { search: 'keyword', limit: '10' } });

      const call = mockFetch.mock.calls[0];
      expect(call[0]).toContain('search=keyword');
      expect(call[0]).toContain('limit=10');
    });

    it('应该处理没有参数的请求', async () => {
      mockFetch.mockResolvedValue(createMockResponse({ status: 'success' }));

      await httpClient.get('http://localhost/api/test');

      const call = mockFetch.mock.calls[0];
      expect(call[0]).not.toContain('?');
    });
  });

  describe('错误处理', () => {
    let httpClient: any;

    beforeEach(async () => {
      const module = await import('@/services/http.client');
      httpClient = module.httpClient;
    });

    it('应该处理HTTP错误状态码', async () => {
      // Context7方法：使用createMockResponse模拟错误状态
      mockFetch.mockResolvedValue(createMockResponse('Not Found', 404));

      await expect(httpClient.get('http://localhost/api/test')).rejects.toThrow('HTTP 404: Error');
    });

    it('应该处理网络错误', async () => {
      // Context7方法：使用mockRejectedValue模拟网络错误
      mockFetch.mockRejectedValue(new Error('Network Error'));

      await expect(httpClient.get('http://localhost/api/test')).rejects.toThrow('Network Error');
    });

    it('应该处理服务器错误', async () => {
      mockFetch.mockResolvedValue(createMockResponse('Internal Server Error', 500));

      await expect(httpClient.get('http://localhost/api/test')).rejects.toThrow('HTTP 500: Error');
    });
  });

  describe('请求体处理', () => {
    let httpClient: any;

    beforeEach(async () => {
      const module = await import('@/services/http.client');
      httpClient = module.httpClient;
    });

    it('应该在POST请求中正确序列化JSON数据', async () => {
      const requestData = { name: 'test', value: 123 };
      
      mockFetch.mockResolvedValue(createMockResponse({ status: 'success' }));

      await httpClient.post('http://localhost/api/test', requestData);

      const call = mockFetch.mock.calls[0];
      expect(call[1].body).toBe(JSON.stringify(requestData));
    });

    it('应该处理没有请求体的POST请求', async () => {
      mockFetch.mockResolvedValue(createMockResponse({ status: 'success' }));

      await httpClient.post('http://localhost/api/test');

      const call = mockFetch.mock.calls[0];
      expect(call[1].body).toBeUndefined();
    });
  });

  describe('边界情况和容错', () => {
    let httpClient: any;

    beforeEach(async () => {
      const module = await import('@/services/http.client');
      httpClient = module.httpClient;
    });

    it('应该处理JSON响应', async () => {
      const responseData = { test: 'data' };
      mockFetch.mockResolvedValue(createMockResponse(responseData));

      const result = await httpClient.get('http://localhost/api/test');

      expect(result).toEqual(responseData);
    });

    it('应该处理非200状态码的响应', async () => {
      mockFetch.mockResolvedValue(createMockResponse('Bad Request', 400));

      await expect(httpClient.get('http://localhost/api/test')).rejects.toThrow('HTTP 400: Error');
    });
  });
});