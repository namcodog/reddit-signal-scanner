/**
 * AnalysisPage组件单元测试
 * 测试SSE实时进度显示、错误处理和自动跳转功能
 * 遵循100%类型安全和质量门禁要求
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import { useTaskProgress, type UseTaskProgressReturn } from '@/hooks/useTaskProgress';
import type { TaskStatus } from '@/services/sse.service';
import AnalysisPage from '@/pages/AnalysisPage';

interface MockNavigateFunction {
  (to: string): void;
  (delta: number): void;
}


interface MockFallbackUIProps {
  taskId: string;
  error: string;
  onRetry: () => void;
}

// Mock useTaskProgress hook - 使用真实的UseTaskProgressReturn类型
vi.mock('@/hooks/useTaskProgress', () => ({
  useTaskProgress: vi.fn<[string | undefined], UseTaskProgressReturn>(),
}));

// Mock FallbackUI component
vi.mock('@/components/FallbackUI', () => ({
  default: ({ taskId, error, onRetry }: MockFallbackUIProps) => (
    <div data-testid="fallback-ui">
      <div>Fallback UI for task: {taskId}</div>
      <div>Error: {error}</div>
      <button data-testid="fallback-retry" onClick={onRetry}>
        Fallback Retry
      </button>
    </div>
  ),
}));

// Mock react-router-dom hooks
const mockNavigate = vi.fn<Parameters<MockNavigateFunction>, void>();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: vi.fn<[], { taskId?: string }>(),
  };
});

// 测试工具函数
const renderAnalysisPageWithRouter = (taskId: string = 'test-task-123') => {
  const TestComponent = () => (
    <MemoryRouter initialEntries={[`/analysis/${taskId}`]}>
      <Routes>
        <Route path="/analysis/:taskId" element={<AnalysisPage />} />
      </Routes>
    </MemoryRouter>
  );

  return render(<TestComponent />);
};

describe('AnalysisPage', () => {
  // 获取mock函数 - 使用正确的导入方式
  const getMockUseTaskProgress = () => vi.mocked(useTaskProgress);
  const getMockUseParams = () => vi.mocked(useParams);

  // 默认mock返回值 - 使用真实的类型
  const defaultTaskStatus: TaskStatus = {
    task_id: 'test-task-123',
    status: 'processing',
    progress: 50,
    message: '分析进行中...',
    created_at: new Date().toISOString(),
  };

  const defaultUseTaskProgressReturn: UseTaskProgressReturn = {
    status: defaultTaskStatus,
    error: null,
    isConnected: true,
    strategy: 'sse',
    retry: vi.fn(),
    disconnect: vi.fn(),
    connectionAttempts: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
    getMockUseTaskProgress().mockReturnValue(defaultUseTaskProgressReturn);
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('基础渲染', () => {
    it('应该正确渲染页面标题和任务ID', () => {
      renderAnalysisPageWithRouter();

      expect(screen.getByText('Reddit 信号分析进行中')).toBeInTheDocument();
      expect(screen.getByText('test-task-123')).toBeInTheDocument();
    });

    it('应该显示连接状态指示器', () => {
      renderAnalysisPageWithRouter();

      expect(screen.getByText('实时连接 (SSE)')).toBeInTheDocument();
      const statusIndicator = document.querySelector('.bg-green-500');
      expect(statusIndicator).toBeInTheDocument();
    });

    it('应该显示进度条和进度信息', () => {
      renderAnalysisPageWithRouter();

      expect(screen.getByText('分析进度')).toBeInTheDocument();
      expect(screen.getAllByText('50%')[0]).toBeInTheDocument();
      expect(screen.getByText('分析进行中...')).toBeInTheDocument();
    });
  });

  describe('任务ID处理', () => {
    it('应该在没有taskId时导航到首页', () => {
      getMockUseParams().mockReturnValue({});
      renderAnalysisPageWithRouter();

      expect(mockNavigate).toHaveBeenCalledWith('/');
    });

    it('应该在有效taskId时正常渲染', () => {
      getMockUseParams().mockReturnValue({ taskId: 'valid-task-id' });
      renderAnalysisPageWithRouter('valid-task-id');

      expect(screen.getByText('valid-task-id')).toBeInTheDocument();
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  describe('连接状态显示', () => {
    it('应该显示连接状态为SSE', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        isConnected: true,
        strategy: 'sse',
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByText('实时连接 (SSE)')).toBeInTheDocument();
      const indicator = document.querySelector('.bg-green-500');
      expect(indicator).toBeInTheDocument();
    });

    it('应该显示连接状态为轮询', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        isConnected: true,
        strategy: 'polling',
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByText('实时连接 (轮询)')).toBeInTheDocument();
    });

    it('应该显示连接断开状态', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        isConnected: false,
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByText('连接断开')).toBeInTheDocument();
      const indicator = document.querySelector('.bg-red-500');
      expect(indicator).toBeInTheDocument();
    });
  });

  describe('进度状态映射', () => {
    it('应该正确显示pending状态', () => {
      const pendingStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'pending',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: pendingStatus,
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByText('任务排队中...')).toBeInTheDocument();
      expect(screen.getByText('10%')).toBeInTheDocument();
    });

    it('应该正确显示processing状态', () => {
      const processingStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'processing',
        progress: 75,
        message: '正在分析用户评论',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: processingStatus,
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByText('正在分析用户评论')).toBeInTheDocument();
      expect(screen.getAllByText('75%')[0]).toBeInTheDocument();
    });

    it('应该正确显示completed状态', () => {
      const completedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'completed',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: completedStatus,
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByText('分析完成！')).toBeInTheDocument();
      expect(screen.getAllByText('100%')[0]).toBeInTheDocument();
    });

    it('应该正确显示failed状态', () => {
      const failedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'failed',
        error_message: '分析过程中发生错误',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: failedStatus,
      });

      renderAnalysisPageWithRouter();

      expect(screen.getAllByText('分析失败')[0]).toBeInTheDocument();
      expect(screen.getByText('分析过程中发生错误')).toBeInTheDocument();
    });

    it('应该处理没有状态的情况', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: null,
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByText('正在连接服务器...')).toBeInTheDocument();
      expect(screen.getByText('0%')).toBeInTheDocument();
    });
  });

  describe('错误处理', () => {
    it('应该显示错误信息和重试按钮', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        error: '连接超时',
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByText('连接错误')).toBeInTheDocument();
      expect(screen.getByText('连接超时')).toBeInTheDocument();
      expect(screen.getByText('重新连接')).toBeInTheDocument();
    });

    it('应该在点击错误重试按钮时调用retry', () => {
      const mockRetry = vi.fn();
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        error: '连接失败',
        retry: mockRetry,
      });

      renderAnalysisPageWithRouter();

      const retryButton = screen.getByText('重新连接');
      fireEvent.click(retryButton);

      expect(mockRetry).toHaveBeenCalledTimes(1);
    });

    it('应该显示失败状态的重新开始按钮', () => {
      const failedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'failed',
        error_message: '服务器内部错误',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: failedStatus,
      });

      renderAnalysisPageWithRouter();

      expect(screen.getAllByText('分析失败')[0]).toBeInTheDocument();
      expect(screen.getByText('服务器内部错误')).toBeInTheDocument();
      
      const restartButton = screen.getByText('重新开始');
      fireEvent.click(restartButton);
      
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  describe('用户交互', () => {
    it('应该在点击取消按钮时断开连接并导航', () => {
      const mockDisconnect = vi.fn();
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        disconnect: mockDisconnect,
      });

      renderAnalysisPageWithRouter();

      const cancelButton = screen.getByText('取消分析');
      fireEvent.click(cancelButton);

      expect(mockDisconnect).toHaveBeenCalledTimes(1);
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });

    it('应该在连接断开时显示重新连接按钮', () => {
      const mockRetry = vi.fn();
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        isConnected: false,
        retry: mockRetry,
      });

      renderAnalysisPageWithRouter();

      const retryButton = screen.getByText('重新连接');
      fireEvent.click(retryButton);

      expect(mockRetry).toHaveBeenCalledTimes(1);
    });
  });

  describe('自动跳转功能', () => {
    it('应该在任务完成后自动跳转到报告页面', async () => {
      vi.useFakeTimers();

      const completedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'completed',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: completedStatus,
      });

      renderAnalysisPageWithRouter();

      // 等待2秒后应该跳转
      vi.advanceTimersByTime(2000);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/report/test-task-123');
      });
      
      // 已经恢复真实定时器，无需再次设置
    });

    it('应该在状态改变前清除之前的定时器', async () => {
      vi.useFakeTimers();

      const { rerender } = renderAnalysisPageWithRouter();

      // 第一次设置为completed
      const completedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'completed',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: completedStatus,
      });

      rerender(
        <MemoryRouter initialEntries={['/analysis/test-task-123']}>
          <Routes>
            <Route path="/analysis/:taskId" element={<AnalysisPage />} />
          </Routes>
        </MemoryRouter>
      );

      // 快速改为processing
      const processingStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'processing',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: processingStatus,
      });

      rerender(
        <MemoryRouter initialEntries={['/analysis/test-task-123']}>
          <Routes>
            <Route path="/analysis/:taskId" element={<AnalysisPage />} />
          </Routes>
        </MemoryRouter>
      );

      // 2秒后不应该跳转
      vi.advanceTimersByTime(2000);
      expect(mockNavigate).not.toHaveBeenCalledWith('/report/test-task-123');

      vi.useRealTimers();
    });
  });

  describe('降级处理', () => {
    it('应该在连接失败3次后显示降级UI', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        connectionAttempts: 3,
        isConnected: false,
        status: null,
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByTestId('fallback-ui')).toBeInTheDocument();
      expect(screen.getByText('Fallback UI for task: test-task-123')).toBeInTheDocument();
      expect(screen.getByText('Error: 无法建立连接')).toBeInTheDocument();
    });

    it('应该在降级UI中支持重试', () => {
      const mockRetry = vi.fn();
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        connectionAttempts: 3,
        isConnected: false,
        status: null,
        retry: mockRetry,
      });

      renderAnalysisPageWithRouter();

      const fallbackRetryButton = screen.getByTestId('fallback-retry');
      fireEvent.click(fallbackRetryButton);

      expect(mockRetry).toHaveBeenCalledTimes(1);
    });

    it('应该在有状态但连接失败时不显示降级UI', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        connectionAttempts: 3,
        isConnected: false,
        status: defaultTaskStatus, // 有状态
      });

      renderAnalysisPageWithRouter();

      expect(screen.queryByTestId('fallback-ui')).not.toBeInTheDocument();
      expect(screen.getByText('Reddit 信号分析进行中')).toBeInTheDocument();
    });
  });

  describe('时间显示', () => {
    it('应该显示任务创建时间', () => {
      const statusWithTime: TaskStatus = {
        ...defaultTaskStatus,
        created_at: '2023-12-01T10:30:00.000Z',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: statusWithTime,
      });

      renderAnalysisPageWithRouter();

      expect(screen.getByText(/开始时间:/)).toBeInTheDocument();
    });

    it('应该在没有创建时间时不显示时间信息', () => {
      const statusWithoutTime: TaskStatus = {
        ...defaultTaskStatus,
        created_at: undefined,
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: statusWithoutTime,
      });

      renderAnalysisPageWithRouter();

      expect(screen.queryByText(/开始时间:/)).not.toBeInTheDocument();
    });
  });
});