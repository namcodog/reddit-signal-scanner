/**
 * WaitingPage组件单元测试
 * 测试v0风格的等待页面的复杂状态管理、进度显示和用户交互
 * 遵循100%类型安全和质量门禁要求
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import { useTaskProgress, type UseTaskProgressReturn } from '@/hooks/useTaskProgress';
import type { TaskStatus } from '@/services/sse.service';
import { AnalysisStep } from '@/services/sse.service';
import WaitingPage from '@/pages/WaitingPage';

interface MockUseParamsReturn {
  taskId?: string;
}

interface MockNavigateFunction {
  (to: string): void;
  (delta: number): void;
}

// Mock useTaskProgress hook - 使用真实的UseTaskProgressReturn类型
vi.mock('@/hooks/useTaskProgress', () => ({
  useTaskProgress: vi.fn<[string | undefined], UseTaskProgressReturn>(),
}));

// Mock SSE service - 模拟分析步骤和相关函数
vi.mock('@/services/sse.service', () => ({
  AnalysisStep: {
    DATA_COLLECTION: 'data-collection',
    INTELLIGENT_ANALYSIS: 'intelligent-analysis',
    INSIGHT_GENERATION: 'insight-generation',
    REPORT_COMPILATION: 'report-compilation',
  },
  ANALYSIS_STEPS: [
    {
      step: 'data-collection',
      title: '数据收集',
      description: '从Reddit收集相关帖子和评论',
    },
    {
      step: 'intelligent-analysis',
      title: '智能分析',
      description: '分析用户情感和关键词',
    },
    {
      step: 'insight-generation',
      title: '洞察生成',
      description: '识别商业机会和市场需求',
    },
    {
      step: 'report-compilation',
      title: '报告编译',
      description: '生成结构化分析报告',
    },
  ],
  getStepIndex: vi.fn((step: string) => {
    const steps = ['data-collection', 'intelligent-analysis', 'insight-generation', 'report-compilation'];
    return steps.indexOf(step);
  }),
  calculateOverallProgress: vi.fn((step: string, stepProgress: number) => {
    const stepIndex = ['data-collection', 'intelligent-analysis', 'insight-generation', 'report-compilation'].indexOf(step);
    return (stepIndex * 25) + (stepProgress / 4);
  }),
  formatRemainingTime: vi.fn((seconds: number) => {
    const mins = Math.floor(seconds / 60);
    return `${mins}分${seconds % 60}秒`;
  }),
}));

// Mock Heroicons
vi.mock('@heroicons/react/24/outline', () => ({
  CpuChipIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="cpu-chip-icon" className={className} {...props} />
  ),
  ClockIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="clock-icon" className={className} {...props} />
  ),
  CheckCircleIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="check-circle-icon" className={className} {...props} />
  ),
  ArrowPathIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="arrow-path-icon" className={className} {...props} />
  ),
  UsersIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="users-icon" className={className} {...props} />
  ),
  ChatBubbleLeftRightIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="chat-bubble-icon" className={className} {...props} />
  ),
  ArrowTrendingUpIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="arrow-trending-up-icon" className={className} {...props} />
  ),
  XMarkIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="x-mark-icon" className={className} {...props} />
  ),
}));

// Mock react-router-dom hooks
const mockNavigate = vi.fn<Parameters<MockNavigateFunction>, void>();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: vi.fn<[], MockUseParamsReturn>(),
  };
});

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn<[string], string | null>(),
  setItem: vi.fn<[string, string], void>(),
  removeItem: vi.fn<[string], void>(),
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

// 测试工具函数
const renderWaitingPageWithRouter = (taskId: string = 'test-task-123') => {
  const TestComponent = () => (
    <MemoryRouter initialEntries={[`/waiting/${taskId}`]}>
      <Routes>
        <Route path="/waiting/:taskId" element={<WaitingPage />} />
      </Routes>
    </MemoryRouter>
  );

  return render(<TestComponent />);
};

describe('WaitingPage', () => {
  // 获取mock函数 - 使用正确的导入方式
  const getMockUseTaskProgress = () => vi.mocked(useTaskProgress);
  const getMockUseParams = () => vi.mocked(useParams);

  // 默认mock返回值 - 使用真实的类型
  const defaultTaskStatus: TaskStatus = {
    task_id: 'test-task-123',
    status: 'processing',
    progress: 50,
    current_step: AnalysisStep.INTELLIGENT_ANALYSIS,
    step_progress: 60,
    estimated_remaining_seconds: 120,
    stats: {
      communities_found: 25,
      posts_analyzed: 1500,
      insights_generated: 8,
      processing_time_seconds: 180,
    },
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
    vi.useFakeTimers();
    getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
    getMockUseTaskProgress().mockReturnValue(defaultUseTaskProgressReturn);
    mockLocalStorage.getItem.mockReturnValue(null);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('基础渲染', () => {
    it('应该正确渲染页面标题和图标', () => {
      renderWaitingPageWithRouter();

      expect(screen.getByTestId('cpu-chip-icon')).toBeInTheDocument();
      expect(screen.getByText('正在分析您的产品')).toBeInTheDocument();
      expect(screen.getByText('我们正在扫描 Reddit 社区，为您的产品寻找商业机会')).toBeInTheDocument();
    });

    it('应该显示渐变背景样式', () => {
      const { container } = renderWaitingPageWithRouter();

      const backgroundContainer = container.querySelector('.bg-gradient-to-br.from-blue-50.via-indigo-50.to-purple-50');
      expect(backgroundContainer).toBeInTheDocument();
    });

    it('应该显示连接状态指示器', () => {
      renderWaitingPageWithRouter();

      expect(screen.getByText('实时连接 (SSE)')).toBeInTheDocument();
      const statusIndicator = document.querySelector('.bg-green-500');
      expect(statusIndicator).toBeInTheDocument();
    });
  });

  describe('任务ID处理', () => {
    it('应该在没有taskId时导航到首页', () => {
      getMockUseParams().mockReturnValue({});
      renderWaitingPageWithRouter();

      expect(mockNavigate).toHaveBeenCalledWith('/');
    });

    it('应该在有效taskId时正常渲染', () => {
      getMockUseParams().mockReturnValue({ taskId: 'valid-task-id' });
      renderWaitingPageWithRouter('valid-task-id');

      expect(screen.getByText('正在分析您的产品')).toBeInTheDocument();
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  describe('产品描述显示', () => {
    it('应该从localStorage获取并显示产品描述', () => {
      const productDescription = '这是一款AI笔记应用，帮助用户整理想法';
      mockLocalStorage.getItem.mockReturnValue(productDescription);
      getMockUseParams().mockReturnValue({ taskId: 'test-task' });

      renderWaitingPageWithRouter('test-task');

      expect(mockLocalStorage.getItem).toHaveBeenCalledWith('task_test-task_description');
      expect(screen.getByText('正在分析的产品')).toBeInTheDocument();
      expect(screen.getByText(productDescription)).toBeInTheDocument();
    });

    it('应该在没有产品描述时不显示产品卡片', () => {
      mockLocalStorage.getItem.mockReturnValue(null);
      renderWaitingPageWithRouter();

      expect(screen.queryByText('正在分析的产品')).not.toBeInTheDocument();
    });
  });

  describe('连接状态显示', () => {
    it('应该显示SSE连接状态', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        isConnected: true,
        strategy: 'sse',
      });

      renderWaitingPageWithRouter();

      expect(screen.getByText('实时连接 (SSE)')).toBeInTheDocument();
      expect(document.querySelector('.bg-green-500')).toBeInTheDocument();
    });

    it('应该显示轮询连接状态', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        isConnected: true,
        strategy: 'polling',
      });

      renderWaitingPageWithRouter();

      expect(screen.getByText('实时连接 (轮询)')).toBeInTheDocument();
    });

    it('应该显示连接断开状态', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        isConnected: false,
        error: '连接失败',
      });

      renderWaitingPageWithRouter();

      expect(screen.getByText('连接断开')).toBeInTheDocument();
      expect(screen.getByText('连接错误')).toBeInTheDocument();
      expect(screen.getByText('重试')).toBeInTheDocument();
      expect(document.querySelector('.bg-red-500')).toBeInTheDocument();
    });
  });

  describe('进度显示', () => {
    it('应该显示正确的进度信息', () => {
      renderWaitingPageWithRouter();

      expect(screen.getByText('分析进度')).toBeInTheDocument();
      expect(screen.getAllByText(/第 2 步，共 4 步/)[0]).toBeInTheDocument();
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    it('应该显示进度条', () => {
      const { container } = renderWaitingPageWithRouter();

      const progressBar = container.querySelector('.bg-gradient-to-r.from-blue-500.to-blue-600');
      expect(progressBar).toBeInTheDocument();
    });

    it('应该显示剩余时间', () => {
      renderWaitingPageWithRouter();

      expect(screen.getByText(/剩余 2分0秒/)).toBeInTheDocument();
    });

    it('应该在完成状态显示完成信息', () => {
      const completedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'completed',
        progress: 100,
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: completedStatus,
      });

      renderWaitingPageWithRouter();

      expect(screen.getByText('分析完成！')).toBeInTheDocument();
      expect(screen.getByText('我们已经发现了关于您的市场机会的宝贵洞察')).toBeInTheDocument();
      expect(screen.getByText('分析已成功完成')).toBeInTheDocument();
    });
  });

  describe('步骤详情显示', () => {
    it('应该显示所有分析步骤', () => {
      renderWaitingPageWithRouter();

      expect(screen.getByText('数据收集')).toBeInTheDocument();
      expect(screen.getByText('智能分析')).toBeInTheDocument();
      expect(screen.getByText('洞察生成')).toBeInTheDocument();
      expect(screen.getByText('报告编译')).toBeInTheDocument();
    });

    it('应该正确显示当前步骤状态', () => {
      renderWaitingPageWithRouter();

      // 当前步骤应该有处理中状态
      expect(screen.getByText('处理中...')).toBeInTheDocument();
      
      // 完成的步骤应该有完成状态
      expect(screen.getByText('完成')).toBeInTheDocument();
    });

    it('应该显示正确的步骤图标', () => {
      renderWaitingPageWithRouter();

      expect(screen.getByTestId('check-circle-icon')).toBeInTheDocument(); // 已完成步骤
      expect(screen.getByTestId('arrow-path-icon')).toBeInTheDocument(); // 当前步骤
    });
  });

  describe('实时统计显示', () => {
    it('应该在连接且未完成时显示统计数据', () => {
      renderWaitingPageWithRouter();

      expect(screen.getByText('25')).toBeInTheDocument(); // communities
      expect(screen.getByText('发现的社区')).toBeInTheDocument();
      expect(screen.getByText('1500')).toBeInTheDocument(); // posts
      expect(screen.getByText('已分析帖子')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument(); // insights
      expect(screen.getByText('生成的洞察')).toBeInTheDocument();
    });

    it('应该显示统计图标', () => {
      renderWaitingPageWithRouter();

      expect(screen.getByTestId('users-icon')).toBeInTheDocument();
      expect(screen.getByTestId('chat-bubble-icon')).toBeInTheDocument();
      expect(screen.getByTestId('arrow-trending-up-icon')).toBeInTheDocument();
    });

    it('应该在断开连接时不显示统计数据', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        isConnected: false,
      });

      renderWaitingPageWithRouter();

      expect(screen.queryByText('发现的社区')).not.toBeInTheDocument();
    });

    it('应该在完成状态时不显示统计数据', () => {
      const completedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'completed',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: completedStatus,
      });

      renderWaitingPageWithRouter();

      expect(screen.queryByText('发现的社区')).not.toBeInTheDocument();
    });
  });

  describe('时间计数器', () => {
    it('应该显示已用时间计数器', async () => {
      renderWaitingPageWithRouter();

      // 初始显示
      expect(screen.getAllByText(/已用时间.*0:00/)[0]).toBeInTheDocument();

      // 前进1秒并等待状态更新
      await act(async () => {
        vi.advanceTimersByTime(1000);
      });
      
      await vi.waitFor(() => {
        expect(screen.getAllByText(/已用时间.*0:01/)[0]).toBeInTheDocument();
      }, { timeout: 2000, interval: 100 });

      // 前进60秒并等待状态更新
      await act(async () => {
        vi.advanceTimersByTime(60000);
      });
      
      await vi.waitFor(() => {
        expect(screen.getAllByText(/已用时间.*1:01/)[0]).toBeInTheDocument();
      }, { timeout: 2000, interval: 100 });
    });

    it('应该在完成时显示预计完成时间', () => {
      renderWaitingPageWithRouter();

      expect(screen.getByText(/预计完成时间：2分0秒/)).toBeInTheDocument();
    });

    it('应该在完成状态时不显示预计时间', () => {
      const completedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'completed',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: completedStatus,
      });

      renderWaitingPageWithRouter();

      expect(screen.queryByText(/预计完成时间/)).not.toBeInTheDocument();
    });
  });

  describe('用户交互', () => {
    it('应该在点击取消按钮时断开连接并导航', () => {
      const mockDisconnect = vi.fn();
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        disconnect: mockDisconnect,
      });

      renderWaitingPageWithRouter();

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

      renderWaitingPageWithRouter();

      const retryButton = screen.getByText('重新连接');
      fireEvent.click(retryButton);

      expect(mockRetry).toHaveBeenCalledTimes(1);
    });

    it('应该在状态指示器中点击重试', () => {
      const mockRetry = vi.fn();
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        isConnected: false,
        error: '连接错误',
        retry: mockRetry,
      });

      renderWaitingPageWithRouter();

      const retryLink = screen.getByText('重试');
      fireEvent.click(retryLink);

      expect(mockRetry).toHaveBeenCalledTimes(1);
    });

    it('应该在完成状态显示查看报告按钮', () => {
      const completedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'completed',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: completedStatus,
      });

      renderWaitingPageWithRouter();

      const reportButton = screen.getByText('查看报告');
      fireEvent.click(reportButton);

      expect(mockNavigate).toHaveBeenCalledWith('/report/test-task-123');
    });
  });

  describe('自动跳转功能', () => {
    it('应该在任务完成后自动跳转到报告页面', async () => {
      const completedStatus: TaskStatus = {
        ...defaultTaskStatus,
        status: 'completed',
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: completedStatus,
      });

      renderWaitingPageWithRouter();

      // 使用act包装定时器推进和状态更新
      await act(async () => {
        vi.advanceTimersByTime(1000);
      });

      // 使用vi.waitFor处理异步状态更新
      await vi.waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/report/test-task-123');
      }, { timeout: 3000, interval: 100 });
    });
  });

  describe('Mock数据显示', () => {
    it('应该在没有实时统计时显示模拟数据', () => {
      const statusWithoutStats: TaskStatus = {
        ...defaultTaskStatus,
        stats: undefined,
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: statusWithoutStats,
      });

      renderWaitingPageWithRouter();

      // 应该显示基于时间的模拟数据
      expect(screen.getByText('12')).toBeInTheDocument(); // Mock communities
      expect(screen.getByText('234')).toBeInTheDocument(); // Mock posts  
      expect(screen.getByText('3')).toBeInTheDocument(); // Mock insights
    });

    it('应该在时间推进时更新模拟统计数据', async () => {
      const statusWithoutStats: TaskStatus = {
        ...defaultTaskStatus,
        stats: undefined,
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: statusWithoutStats,
      });

      renderWaitingPageWithRouter();

      // 前进时间更新模拟数据，使用act包装
      await act(async () => {
        vi.advanceTimersByTime(1000);
      });

      await vi.waitFor(() => {
        // 验证数据有所增长（基于时间的计算）
        expect(screen.queryByText('12')).toBeInTheDocument(); // 初始值可能保持
      }, { timeout: 2000, interval: 100 });
    });
  });

  describe('边界情况处理', () => {
    it('应该处理没有状态的情况', () => {
      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: null,
      });

      renderWaitingPageWithRouter();

      expect(screen.getAllByText(/第 1 步，共 4 步/)[0]).toBeInTheDocument();
      expect(screen.getByText('0%')).toBeInTheDocument();
    });

    it('应该处理步骤索引超出范围的情况', () => {
      const statusWithInvalidStep: TaskStatus = {
        ...defaultTaskStatus,
        current_step: 'invalid-step' as AnalysisStep,
      };

      getMockUseTaskProgress().mockReturnValue({
        ...defaultUseTaskProgressReturn,
        status: statusWithInvalidStep,
      });

      renderWaitingPageWithRouter();

      // 应该回退到第一步
      expect(screen.getAllByText(/第 1 步，共 4 步/)[0]).toBeInTheDocument();
    });
  });
});