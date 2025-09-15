/**
 * ConfigService配置服务测试
 * 严格按照Context7最佳实践：vi.stubEnv + vi.unstubAllEnvs
 * 100%类型安全，零技术债务
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// 严格类型定义 - 禁止any类型
interface AppConfig {
  useMockApi: boolean;
  apiBaseUrl: string;
  mockApiPath: string;
  realApiPath: string;
}

describe('ConfigService', () => {
  beforeEach(() => {
    // Context7最佳实践：清除模块缓存
    vi.resetModules();
  });

  afterEach(() => {
    // Context7最佳实践：恢复所有环境变量
    vi.unstubAllEnvs();
  });

  describe('构造函数和初始化', () => {
    it('应该使用默认配置初始化', async () => {
      // Context7方法：不设置任何环境变量，使用默认值
      const { configService } = await import('@/services/config.service');

      const config = configService.getConfig();
      expect(config).toEqual({
        useMockApi: true, // 默认使用Mock（VITE_USE_MOCK_API !== 'false'）
        apiBaseUrl: 'http://localhost:8000',
        mockApiPath: '/api/v1/mock',
        realApiPath: '/api/v1/discovery',
      });
    });

    it('应该从环境变量读取配置', async () => {
      // Context7方法：使用vi.stubEnv设置环境变量
      vi.stubEnv('VITE_USE_MOCK_API', 'false');
      vi.stubEnv('VITE_API_BASE_URL', 'https://prod-api.example.com');

      const { configService } = await import('@/services/config.service');

      const config = configService.getConfig();
      expect(config.useMockApi).toBe(false);
      expect(config.apiBaseUrl).toBe('https://prod-api.example.com');
    });

    it('应该正确解析VITE_USE_MOCK_API环境变量', async () => {
      // 测试true值
      vi.stubEnv('VITE_USE_MOCK_API', 'true');
      
      const { configService: configServiceTrue } = await import('@/services/config.service');
      expect(configServiceTrue.isUsingMock()).toBe(true);

      vi.resetModules();

      // 测试false值
      vi.stubEnv('VITE_USE_MOCK_API', 'false');
      
      const { configService: configServiceFalse } = await import('@/services/config.service');
      expect(configServiceFalse.isUsingMock()).toBe(false);
    });

    it('应该在缺少环境变量时使用默认值', async () => {
      // Context7方法：不设置环境变量，验证默认行为
      const { configService } = await import('@/services/config.service');

      expect(configService.isUsingMock()).toBe(true);
      expect(configService.getConfig().apiBaseUrl).toBe('http://localhost:8000');
    });
  });

  describe('isUsingMock方法', () => {
    it('应该正确返回Mock模式状态', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      expect(configService.isUsingMock()).toBe(true);
    });

    it('应该正确返回非Mock模式状态', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'false');

      const { configService } = await import('@/services/config.service');

      expect(configService.isUsingMock()).toBe(false);
    });
  });

  describe('getAnalyzeEndpoint方法', () => {
    it('应该在Mock模式下返回Mock端点', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      expect(configService.getAnalyzeEndpoint()).toBe('/api/v1/mock/analyze');
    });

    it('应该在真实模式下返回真实端点', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'false');

      const { configService } = await import('@/services/config.service');

      expect(configService.getAnalyzeEndpoint()).toBe('/api/v1/discovery/analyze');
    });
  });

  describe('getStatusEndpoint方法', () => {
    it('应该在Mock模式下返回Mock状态端点', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      const endpoint = configService.getStatusEndpoint('test-task-123');
      expect(endpoint).toBe('/api/v1/mock/status/test-task-123');
    });

    it('应该在真实模式下返回真实状态端点', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'false');

      const { configService } = await import('@/services/config.service');

      const endpoint = configService.getStatusEndpoint('test-task-123');
      expect(endpoint).toBe('/api/v1/status/test-task-123');
    });

    it('应该正确处理不同的taskId', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      const testCases = [
        'simple-task',
        'task-with-numbers-123',
        'task_with_underscores',
        'task-with-special-chars-!@#'
      ];

      testCases.forEach(taskId => {
        const endpoint = configService.getStatusEndpoint(taskId);
        expect(endpoint).toBe(`/api/v1/mock/status/${taskId}`);
      });
    });
  });

  describe('getResultEndpoint方法', () => {
    it('应该在Mock模式下返回Mock结果端点', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      const endpoint = configService.getResultEndpoint('test-task-123');
      expect(endpoint).toBe('/api/v1/mock/result/test-task-123');
    });

    it('应该在真实模式下返回真实结果端点', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'false');

      const { configService } = await import('@/services/config.service');

      const endpoint = configService.getResultEndpoint('test-task-123');
      expect(endpoint).toBe('/api/v1/report/test-task-123');
    });
  });

  describe('getStreamEndpoint方法', () => {
    it('应该在Mock模式下返回轮询端点（不支持SSE）', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      const endpoint = configService.getStreamEndpoint('test-task-123');
      expect(endpoint).toBe('/api/v1/mock/status/test-task-123');
    });

    it('应该在真实模式下返回SSE流端点', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'false');

      const { configService } = await import('@/services/config.service');

      const endpoint = configService.getStreamEndpoint('test-task-123');
      expect(endpoint).toBe('/api/v1/stream/test-task-123');
    });
  });

  describe('toggleMockMode方法', () => {
    it('应该切换Mock模式状态', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      // 初始状态为Mock模式
      expect(configService.isUsingMock()).toBe(true);

      // 第一次切换到真实模式
      configService.toggleMockMode();
      expect(configService.isUsingMock()).toBe(false);

      // 第二次切换回Mock模式
      configService.toggleMockMode();
      expect(configService.isUsingMock()).toBe(true);
    });

    it('应该记录模式切换日志', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');
      
      const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => undefined);

      const { configService } = await import('@/services/config.service');

      configService.toggleMockMode();
      expect(consoleLogSpy).toHaveBeenCalledWith('Switched to Real API mode');

      configService.toggleMockMode();
      expect(consoleLogSpy).toHaveBeenCalledWith('Switched to Mock API mode');

      consoleLogSpy.mockRestore();
    });

    it('应该在切换后影响端点生成', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      // Mock模式下的端点
      expect(configService.getAnalyzeEndpoint()).toBe('/api/v1/mock/analyze');

      // 切换到真实模式
      configService.toggleMockMode();
      expect(configService.getAnalyzeEndpoint()).toBe('/api/v1/discovery/analyze');

      // 切换回Mock模式
      configService.toggleMockMode();
      expect(configService.getAnalyzeEndpoint()).toBe('/api/v1/mock/analyze');
    });
  });

  describe('getConfig方法', () => {
    it('应该返回配置的只读副本', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'false');
      vi.stubEnv('VITE_API_BASE_URL', 'https://test-api.example.com');

      const { configService } = await import('@/services/config.service');

      const config = configService.getConfig();

      expect(config).toEqual({
        useMockApi: false,
        apiBaseUrl: 'https://test-api.example.com',
        mockApiPath: '/api/v1/mock',
        realApiPath: '/api/v1/discovery',
      });
    });

    it('应该返回不可修改的配置对象', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      const config = configService.getConfig();
      
      // 尝试修改返回的配置应该不影响内部状态
      (config as any).useMockApi = false;
      
      // 内部状态应该保持不变
      expect(configService.isUsingMock()).toBe(true);
      expect(configService.getConfig().useMockApi).toBe(true);
    });

    it('应该包含所有必需的配置字段', async () => {
      const { configService } = await import('@/services/config.service');

      const config = configService.getConfig();

      expect(config).toHaveProperty('useMockApi');
      expect(config).toHaveProperty('apiBaseUrl');
      expect(config).toHaveProperty('mockApiPath');
      expect(config).toHaveProperty('realApiPath');

      expect(typeof config.useMockApi).toBe('boolean');
      expect(typeof config.apiBaseUrl).toBe('string');
      expect(typeof config.mockApiPath).toBe('string');
      expect(typeof config.realApiPath).toBe('string');
    });
  });

  describe('环境变量边界情况', () => {
    it('应该正确处理undefined环境变量', async () => {
      // Context7方法：不设置任何环境变量，验证默认行为
      const { configService } = await import('@/services/config.service');

      // 应该使用默认值
      expect(configService.isUsingMock()).toBe(true);
      expect(configService.getConfig().apiBaseUrl).toBe('http://localhost:8000');
    });

    it('应该正确处理空字符串环境变量', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', '');
      vi.stubEnv('VITE_API_BASE_URL', '');

      const { configService } = await import('@/services/config.service');

      // 空字符串不等于'false'，所以应该是true
      expect(configService.isUsingMock()).toBe(true);
      expect(configService.getConfig().apiBaseUrl).toBe('http://localhost:8000'); // 默认值
    });

    it('应该正确处理非标准的VITE_USE_MOCK_API值', async () => {
      const testCases = [
        { value: 'TRUE', expected: true },
        { value: 'false', expected: false },
        { value: 'yes', expected: true },
        { value: '1', expected: true },
        { value: '0', expected: true },
      ];

      for (const testCase of testCases) {
        vi.resetModules();
        vi.stubEnv('VITE_USE_MOCK_API', testCase.value);

        const { configService } = await import('@/services/config.service');

        expect(configService.isUsingMock()).toBe(testCase.expected);
      }
    });
  });

  describe('集成测试', () => {
    it('应该在不同模式下正确生成所有端点', async () => {
      vi.stubEnv('VITE_USE_MOCK_API', 'true');

      const { configService } = await import('@/services/config.service');

      const taskId = 'integration-test-task';

      // Mock模式下的端点
      expect(configService.getAnalyzeEndpoint()).toBe('/api/v1/mock/analyze');
      expect(configService.getStatusEndpoint(taskId)).toBe(`/api/v1/mock/status/${taskId}`);
      expect(configService.getResultEndpoint(taskId)).toBe(`/api/v1/mock/result/${taskId}`);
      expect(configService.getStreamEndpoint(taskId)).toBe(`/api/v1/mock/status/${taskId}`);

      // 切换到真实模式
      configService.toggleMockMode();

      expect(configService.getAnalyzeEndpoint()).toBe('/api/v1/discovery/analyze');
      expect(configService.getStatusEndpoint(taskId)).toBe(`/api/v1/status/${taskId}`);
      expect(configService.getResultEndpoint(taskId)).toBe(`/api/v1/report/${taskId}`);
      expect(configService.getStreamEndpoint(taskId)).toBe(`/api/v1/stream/${taskId}`);
    });

    it('应该支持配置的完整生命周期', async () => {
      // 1. 使用环境变量初始化
      vi.stubEnv('VITE_USE_MOCK_API', 'false');
      vi.stubEnv('VITE_API_BASE_URL', 'https://prod-api.example.com');

      const { configService } = await import('@/services/config.service');

      // 2. 验证初始配置
      expect(configService.isUsingMock()).toBe(false);
      expect(configService.getConfig().apiBaseUrl).toBe('https://prod-api.example.com');

      // 3. 动态切换模式
      configService.toggleMockMode();
      expect(configService.isUsingMock()).toBe(true);

      // 4. 验证端点生成受到模式影响
      const taskId = 'lifecycle-test';
      expect(configService.getStatusEndpoint(taskId)).toBe(`/api/v1/mock/status/${taskId}`);

      // 5. 获取完整配置进行验证
      const finalConfig = configService.getConfig();
      expect(finalConfig.useMockApi).toBe(true);
      expect(finalConfig.apiBaseUrl).toBe('https://prod-api.example.com'); // 不受模式切换影响
    });
  });
});