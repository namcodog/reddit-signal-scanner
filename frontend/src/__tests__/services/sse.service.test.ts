/**
 * SSE服务测试 - Server-Sent Events实时通信
 * 严格按照Context7最佳实践：vi.stubGlobal简单方法
 * 100%类型安全，零技术债务
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// Context7最佳实践：简单EventSource mock
const mockEventSource = {
  readyState: 1,
  onopen: null,
  onmessage: null,
  onerror: null,
  addEventListener: vi.fn(),
  close: vi.fn(),
  url: '',
};

const EventSourceMock = vi.fn().mockImplementation((url: string) => {
  mockEventSource.url = url;
  return mockEventSource;
});

// Context7最佳实践：使用vi.stubGlobal
vi.stubGlobal('EventSource', EventSourceMock);
vi.stubGlobal('fetch', vi.fn());

describe('SSE Service', () => {
  let mockConsoleLog: any;
  let mockConsoleError: any;
  let mockConsoleWarn: any;

  beforeEach(() => {
    // Context7最佳实践：重置模块缓存
    vi.resetModules();
    
    // Context7最佳实践：重置所有mock
    vi.clearAllMocks();
    
    // Mock console方法
    mockConsoleLog = vi.spyOn(console, 'log').mockImplementation(() => {});
    mockConsoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockConsoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    
    // 重置EventSource mock
    mockEventSource.readyState = 1;
    mockEventSource.onopen = null;
    mockEventSource.onmessage = null;
    mockEventSource.onerror = null;
  });

  afterEach(() => {
    // Context7最佳实践：恢复console方法
    mockConsoleLog.mockRestore();
    mockConsoleError.mockRestore();
    mockConsoleWarn.mockRestore();
  });

  describe('SSEManager类', () => {
    let SSEManager: any;
    let sseManager: any;

    beforeEach(async () => {
      // Context7最佳实践：动态导入模块
      const module = await import('@/services/sse.service');
      SSEManager = module.SSEManager;
      sseManager = new SSEManager();
    });

    describe('构造函数和配置', () => {
      it('应该使用默认配置初始化', () => {
        const manager = new SSEManager();
        const state = manager.getConnectionState();
        
        expect(state.connected).toBe(false);
        expect(state.retryCount).toBe(0);
      });

      it('应该接受自定义配置', () => {
        const customConfig = {
          maxRetries: 5,
          retryDelay: 3000,
          heartbeatInterval: 60000,
          connectionTimeout: 15000,
        };
        
        const manager = new SSEManager(customConfig);
        expect(manager).toBeDefined();
      });
    });

    describe('connect方法', () => {
      const mockTaskId = 'test-task-123';
      const mockOnStatusUpdate = vi.fn();
      const mockOnError = vi.fn();
      const mockOnClose = vi.fn();

      it('应该成功建立SSE连接', () => {
        sseManager.connect(mockTaskId, mockOnStatusUpdate, mockOnError, mockOnClose);

        expect(EventSourceMock).toHaveBeenCalledWith(`/api/v1/analyze/stream/${mockTaskId}`);
        expect(mockEventSource.url).toBe(`/api/v1/analyze/stream/${mockTaskId}`);
      });

      it('应该处理连接打开事件', () => {
        sseManager.connect(mockTaskId, mockOnStatusUpdate, mockOnError, mockOnClose);

        // 模拟连接打开
        const onOpenEvent = new Event('open');
        mockEventSource.onopen?.(onOpenEvent);

        expect(mockConsoleLog).toHaveBeenCalledWith(`SSE连接已建立: ${mockTaskId}`);
      });
    });

    describe('消息处理', () => {
      const mockTaskId = 'test-task-123';
      const mockOnStatusUpdate = vi.fn();
      const mockOnError = vi.fn();
      const mockOnClose = vi.fn();

      beforeEach(() => {
        sseManager.connect(mockTaskId, mockOnStatusUpdate, mockOnError, mockOnClose);
        // 模拟连接已建立
        mockEventSource.onopen?.(new Event('open'));
      });

      it('应该正确解析和处理状态消息', () => {
        const mockStatus = {
          task_id: mockTaskId,
          status: 'processing',
          progress: 50,
          message: '分析进行中',
        };

        const messageEvent = new MessageEvent('message', {
          data: JSON.stringify(mockStatus),
        });

        mockEventSource.onmessage?.(messageEvent);

        expect(mockOnStatusUpdate).toHaveBeenCalledWith(mockStatus);
      });

      it('应该在任务完成时自动断开连接', () => {
        const mockStatus = {
          task_id: mockTaskId,
          status: 'completed',
          progress: 100,
        };

        const messageEvent = new MessageEvent('message', {
          data: JSON.stringify(mockStatus),
        });

        mockEventSource.onmessage?.(messageEvent);

        expect(mockEventSource.close).toHaveBeenCalled();
      });

      it('应该处理消息解析错误', () => {
        const invalidMessageEvent = new MessageEvent('message', {
          data: 'invalid-json',
        });

        mockEventSource.onmessage?.(invalidMessageEvent);

        expect(mockConsoleError).toHaveBeenCalledWith('SSE消息解析失败:', expect.any(Error));
        expect(mockOnError).toHaveBeenCalledWith(new Error('数据格式错误'));
      });
    });

    describe('错误处理', () => {
      const mockTaskId = 'test-task-123';
      const mockOnStatusUpdate = vi.fn();
      const mockOnError = vi.fn();
      const mockOnClose = vi.fn();

      it('应该处理连接错误', () => {
        sseManager.connect(mockTaskId, mockOnStatusUpdate, mockOnError, mockOnClose);

        // 模拟连接错误
        mockEventSource.onerror?.();

        expect(mockOnError).toHaveBeenCalledWith(new Error('SSE连接错误'));
        expect(mockConsoleError).toHaveBeenCalledWith('SSE连接错误:', 'SSE连接错误');
      });
    });

    describe('disconnect方法', () => {
      it('应该正确断开连接', () => {
        const mockTaskId = 'test-task-123';
        sseManager.connect(mockTaskId, vi.fn(), vi.fn(), vi.fn());

        sseManager.disconnect();

        expect(mockEventSource.close).toHaveBeenCalled();
        
        const state = sseManager.getConnectionState();
        expect(state.connected).toBe(false);
      });
    });

    describe('getConnectionState方法', () => {
      it('应该返回正确的连接状态', () => {
        const state = sseManager.getConnectionState();
        
        expect(state).toEqual({
          connected: false,
          retryCount: 0,
          readyState: undefined,
        });
      });
    });
  });

  describe('PollingManager类', () => {
    let PollingManager: any;
    let pollingManager: any;

    beforeEach(async () => {
      const module = await import('@/services/sse.service');
      PollingManager = module.PollingManager;
      pollingManager = new PollingManager();
    });

    describe('构造函数', () => {
      it('应该使用默认配置初始化', () => {
        const manager = new PollingManager();
        const state = manager.getPollingState();
        
        expect(state.isPolling).toBe(false);
        expect(state.attemptCount).toBe(0);
      });

      it('应该接受自定义配置', () => {
        const customConfig = {
          interval: 3000,
          maxAttempts: 100,
        };
        
        const manager = new PollingManager(customConfig);
        expect(manager).toBeDefined();
      });
    });

    describe('startPolling方法', () => {
      const mockTaskId = 'test-task-123';
      const mockOnStatusUpdate = vi.fn();
      const mockOnError = vi.fn();
      const mockOnComplete = vi.fn();

      it('应该开始轮询', async () => {
        const mockStatus = {
          task_id: mockTaskId,
          status: 'processing',
          progress: 50,
        };

        const mockResponse = {
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue(mockStatus),
        };

        vi.mocked(fetch).mockResolvedValue(mockResponse as Response);

        pollingManager.startPolling(mockTaskId, mockOnStatusUpdate, mockOnError, mockOnComplete);

        // 等待Promise resolve
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(fetch).toHaveBeenCalledWith(`/api/v1/tasks/${mockTaskId}/status`);
        expect(mockOnStatusUpdate).toHaveBeenCalledWith(mockStatus);
      });

      it('应该在任务完成时停止轮询', async () => {
        const mockStatus = {
          task_id: mockTaskId,
          status: 'completed',
          progress: 100,
        };

        const mockResponse = {
          ok: true,
          status: 200,
          json: vi.fn().mockResolvedValue(mockStatus),
        };

        vi.mocked(fetch).mockResolvedValue(mockResponse as Response);

        pollingManager.startPolling(mockTaskId, mockOnStatusUpdate, mockOnError, mockOnComplete);

        await new Promise(resolve => setTimeout(resolve, 0));

        expect(mockOnComplete).toHaveBeenCalled();
      });

      it('应该处理HTTP错误', async () => {
        const mockResponse = {
          ok: false,
          status: 404,
          statusText: 'Not Found',
        };

        vi.mocked(fetch).mockResolvedValue(mockResponse as Response);

        pollingManager.startPolling(mockTaskId, mockOnStatusUpdate, mockOnError, mockOnComplete);

        await new Promise(resolve => setTimeout(resolve, 0));

        expect(mockOnError).toHaveBeenCalledWith(new Error('HTTP 404: Not Found'));
      });
    });

    describe('stopPolling方法', () => {
      it('应该停止轮询', () => {
        pollingManager.stopPolling();
        
        const state = pollingManager.getPollingState();
        expect(state.isPolling).toBe(false);
      });
    });
  });

  describe('RealTimeTaskService类', () => {
    let RealTimeTaskService: any;
    let realTimeService: any;

    beforeEach(async () => {
      const module = await import('@/services/sse.service');
      RealTimeTaskService = module.RealTimeTaskService;
      realTimeService = new RealTimeTaskService();
    });

    describe('startMonitoring方法', () => {
      const mockTaskId = 'test-task-123';
      const mockOnStatusUpdate = vi.fn();
      const mockOnError = vi.fn();
      const mockOnComplete = vi.fn();

      it('应该优先尝试SSE连接', () => {
        realTimeService.startMonitoring(mockTaskId, mockOnStatusUpdate, mockOnError, mockOnComplete);

        const status = realTimeService.getStatus();
        expect(status.strategy).toBe('sse');
        expect(EventSourceMock).toHaveBeenCalledWith(`/api/v1/analyze/stream/${mockTaskId}`);
      });
    });

    describe('stopMonitoring方法', () => {
      it('应该停止所有监听', () => {
        const mockTaskId = 'test-task-123';
        realTimeService.startMonitoring(mockTaskId, vi.fn(), vi.fn(), vi.fn());
        
        realTimeService.stopMonitoring();

        const status = realTimeService.getStatus();
        expect(status.strategy).toBe(null);
      });
    });

    describe('getStatus方法', () => {
      it('应该返回当前状态', () => {
        const status = realTimeService.getStatus();
        
        expect(status).toEqual({
          strategy: null,
          sse: {
            connected: false,
            retryCount: 0,
            readyState: undefined,
          },
          polling: {
            isPolling: false,
            attemptCount: 0,
          },
        });
      });
    });
  });

  describe('辅助函数', () => {
    let module: any;

    beforeEach(async () => {
      module = await import('@/services/sse.service');
    });

    describe('getStepIndex函数', () => {
      it('应该返回正确的步骤索引', () => {
        expect(module.getStepIndex('data-collection')).toBe(0);
        expect(module.getStepIndex('intelligent-analysis')).toBe(1);
        expect(module.getStepIndex('insight-generation')).toBe(2);
        expect(module.getStepIndex('report-compilation')).toBe(3);
      });

      it('应该对无效步骤返回-1', () => {
        expect(module.getStepIndex('invalid-step')).toBe(-1);
      });
    });

    describe('calculateOverallProgress函数', () => {
      it('应该正确计算整体进度', () => {
        expect(module.calculateOverallProgress('data-collection', 50)).toBe(13);
        expect(module.calculateOverallProgress('intelligent-analysis', 0)).toBe(25);
        expect(module.calculateOverallProgress('report-compilation', 100)).toBe(100);
      });

      it('应该处理无效步骤', () => {
        expect(module.calculateOverallProgress('invalid-step', 50)).toBe(0);
      });
    });

    describe('formatRemainingTime函数', () => {
      it('应该正确格式化剩余时间', () => {
        expect(module.formatRemainingTime(30)).toBe('30秒');
        expect(module.formatRemainingTime(60)).toBe('1分钟');
        expect(module.formatRemainingTime(90)).toBe('1分30秒');
        expect(module.formatRemainingTime(120)).toBe('2分钟');
        expect(module.formatRemainingTime(150)).toBe('2分30秒');
      });
    });

    describe('ANALYSIS_STEPS常量', () => {
      it('应该包含所有分析步骤', () => {
        expect(module.ANALYSIS_STEPS).toHaveLength(4);
        expect(module.ANALYSIS_STEPS[0].step).toBe('data-collection');
        expect(module.ANALYSIS_STEPS[1].step).toBe('intelligent-analysis');
        expect(module.ANALYSIS_STEPS[2].step).toBe('insight-generation');
        expect(module.ANALYSIS_STEPS[3].step).toBe('report-compilation');
      });

      it('每个步骤应该有完整的配置', () => {
        module.ANALYSIS_STEPS.forEach((step: any) => {
          expect(step).toHaveProperty('step');
          expect(step).toHaveProperty('title');
          expect(step).toHaveProperty('description');
          expect(step).toHaveProperty('icon');
          expect(step).toHaveProperty('estimated_duration');
        });
      });
    });

    describe('realTimeTaskService单例', () => {
      it('应该导出单例实例', () => {
        expect(module.realTimeTaskService).toBeDefined();
        expect(module.realTimeTaskService).toBeInstanceOf(module.RealTimeTaskService);
      });
    });
  });
});