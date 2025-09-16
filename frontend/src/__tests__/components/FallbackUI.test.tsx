/**
 * FallbackUI组件单元测试
 * 测试降级UI的错误处理、用户交互和导航功能
 * 遵循100%类型安全和质量门禁要求
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import FallbackUI from '@/components/FallbackUI';

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock window.location
const mockReload = vi.fn();
Object.defineProperty(window, 'location', {
  value: {
    reload: mockReload,
  },
  writable: true,
});

// 测试组件包装器
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>{children}</BrowserRouter>
);

// 测试用的props
interface TestFallbackUIProps {
  taskId?: string;
  error?: string;
  onRetry?: () => void;
}

const defaultProps: Required<TestFallbackUIProps> = {
  taskId: 'test-task-123',
  error: '网络连接失败',
  onRetry: vi.fn(),
};

const renderFallbackUI = (props: Partial<TestFallbackUIProps> = {}) => {
  const finalProps = { ...defaultProps, ...props };
  return render(
    <TestWrapper>
      <FallbackUI {...finalProps} />
    </TestWrapper>
  );
};

describe('FallbackUI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('基础渲染', () => {
    it('应该正确渲染所有基本元素', () => {
      renderFallbackUI();

      expect(screen.getByText('连接中断')).toBeInTheDocument();
      expect(screen.getByText('实时连接失败：网络连接失败')).toBeInTheDocument();
      expect(screen.getByText('你的任务正在后台继续处理：')).toBeInTheDocument();
      expect(screen.getByText('test-task-123')).toBeInTheDocument();
    });

    it('应该显示警告图标', () => {
      const { container } = renderFallbackUI();
      
      const warningIcon = container.querySelector('.text-6xl');
      expect(warningIcon).toBeInTheDocument();
      expect(warningIcon).toHaveTextContent('⚠️');
    });

    it('应该显示所有操作按钮', () => {
      renderFallbackUI();

      expect(screen.getByRole('button', { name: '重新连接' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '手动检查状态' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '重新开始分析' })).toBeInTheDocument();
    });

    it('应该显示提示信息', () => {
      renderFallbackUI();

      expect(screen.getByText('分析任务会继续在后台运行')).toBeInTheDocument();
      expect(screen.getByText('你可以稍后返回查看结果')).toBeInTheDocument();
    });
  });

  describe('Props处理', () => {
    it('应该正确显示自定义taskId', () => {
      renderFallbackUI({ taskId: 'custom-task-456' });

      expect(screen.getByText('custom-task-456')).toBeInTheDocument();
      expect(screen.queryByText('test-task-123')).not.toBeInTheDocument();
    });

    it('应该正确显示自定义错误信息', () => {
      renderFallbackUI({ error: 'WebSocket连接超时' });

      expect(screen.getByText('实时连接失败：WebSocket连接超时')).toBeInTheDocument();
      expect(screen.queryByText('实时连接失败：网络连接失败')).not.toBeInTheDocument();
    });

    it('应该接受自定义onRetry回调函数', () => {
      const customOnRetry = vi.fn();
      renderFallbackUI({ onRetry: customOnRetry });

      fireEvent.click(screen.getByRole('button', { name: '重新连接' }));
      expect(customOnRetry).toHaveBeenCalledOnce();
    });
  });

  describe('用户交互', () => {
    it('重新连接按钮应该调用onRetry回调', () => {
      const mockOnRetry = vi.fn();
      renderFallbackUI({ onRetry: mockOnRetry });

      fireEvent.click(screen.getByRole('button', { name: '重新连接' }));
      expect(mockOnRetry).toHaveBeenCalledOnce();
    });

    it('手动检查状态按钮应该刷新页面', () => {
      renderFallbackUI();

      fireEvent.click(screen.getByRole('button', { name: '手动检查状态' }));
      expect(mockReload).toHaveBeenCalledOnce();
    });

    it('重新开始分析按钮应该导航到首页', () => {
      renderFallbackUI();

      fireEvent.click(screen.getByRole('button', { name: '重新开始分析' }));
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  describe('样式和布局', () => {
    it('应该有正确的主容器样式', () => {
      const { container } = renderFallbackUI();

      const mainContainer = container.firstChild as HTMLElement;
      expect(mainContainer).toHaveClass(
        'min-h-screen',
        'bg-gray-50',
        'flex',
        'items-center',
        'justify-center',
        'px-4'
      );
    });

    it('应该有正确的卡片容器样式', () => {
      const { container } = renderFallbackUI();

      const cardContainer = container.querySelector('.max-w-md');
      expect(cardContainer).toHaveClass(
        'max-w-md',
        'w-full',
        'bg-white',
        'rounded-lg',
        'shadow-lg',
        'p-8',
        'text-center'
      );
    });

    it('应该有正确的任务信息区域样式', () => {
      const { container } = renderFallbackUI();

      const taskInfoArea = container.querySelector('.bg-gray-50.rounded-lg.p-4.mb-6');
      expect(taskInfoArea).toHaveClass('bg-gray-50', 'rounded-lg', 'p-4', 'mb-6');
    });

    it('taskId应该以代码格式显示', () => {
      renderFallbackUI();

      const taskIdElement = screen.getByText('test-task-123');
      expect(taskIdElement.tagName.toLowerCase()).toBe('code');
      expect(taskIdElement).toHaveClass(
        'text-xs',
        'bg-white',
        'px-2',
        'py-1',
        'rounded',
        'border'
      );
    });
  });

  describe('按钮样式和交互状态', () => {
    it('重新连接按钮应该有正确的样式', () => {
      renderFallbackUI();

      const reconnectButton = screen.getByRole('button', { name: '重新连接' });
      expect(reconnectButton).toHaveClass(
        'w-full',
        'px-4',
        'py-3',
        'bg-blue-600',
        'text-white',
        'rounded-lg',
        'hover:bg-blue-700',
        'focus:outline-none',
        'focus:ring-2',
        'focus:ring-blue-500'
      );
    });

    it('手动检查状态按钮应该有正确的样式', () => {
      renderFallbackUI();

      const checkButton = screen.getByRole('button', { name: '手动检查状态' });
      expect(checkButton).toHaveClass(
        'w-full',
        'px-4',
        'py-3',
        'bg-green-600',
        'text-white',
        'rounded-lg',
        'hover:bg-green-700',
        'focus:outline-none',
        'focus:ring-2',
        'focus:ring-green-500'
      );
    });

    it('重新开始分析按钮应该有正确的样式', () => {
      renderFallbackUI();

      const restartButton = screen.getByRole('button', { name: '重新开始分析' });
      expect(restartButton).toHaveClass(
        'w-full',
        'px-4',
        'py-3',
        'bg-gray-600',
        'text-white',
        'rounded-lg',
        'hover:bg-gray-700',
        'focus:outline-none',
        'focus:ring-2',
        'focus:ring-gray-500'
      );
    });
  });

  describe('可访问性', () => {
    it('应该有正确的语义结构', () => {
      renderFallbackUI();

      const title = screen.getByRole('heading', { level: 2 });
      expect(title).toHaveTextContent('连接中断');
    });

    it('所有按钮应该可以通过键盘访问', () => {
      renderFallbackUI();

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toHaveClass('focus:outline-none');
        expect(button).toHaveClass('focus:ring-2');
      });
    });

    it('应该提供有意义的文本内容', () => {
      renderFallbackUI();

      expect(screen.getByText('连接中断')).toBeVisible();
      expect(screen.getByText(/实时连接失败/)).toBeVisible();
      expect(screen.getByText(/你的任务正在后台继续处理/)).toBeVisible();
    });
  });

  describe('错误场景处理', () => {
    it('应该处理空字符串taskId', () => {
      renderFallbackUI({ taskId: '' });

      const emptyElements = screen.getAllByText('');
      expect(emptyElements[0]).toBeInTheDocument(); // 空taskId仍然渲染
    });

    it('应该处理空字符串error', () => {
      renderFallbackUI({ error: '' });

      expect(screen.getByText('实时连接失败：')).toBeInTheDocument();
    });

    it('应该处理长taskId不影响布局', () => {
      const longTaskId = 'very-long-task-id-that-might-break-layout-1234567890-abcdef-ghijk-lmnop-qrstuv-wxyz';
      renderFallbackUI({ taskId: longTaskId });

      const taskIdElement = screen.getByText(longTaskId);
      expect(taskIdElement).toBeInTheDocument();
      expect(taskIdElement).toHaveClass('text-xs'); // 小字体处理长文本
    });

    it('应该处理长错误信息', () => {
      const longError = '这是一个非常长的错误信息，可能会影响页面布局，我们需要确保它能够正确显示而不会破坏整体的用户界面体验';
      renderFallbackUI({ error: longError });

      expect(screen.getByText(`实时连接失败：${longError}`)).toBeInTheDocument();
    });
  });

  describe('组件集成', () => {
    it('应该正确集成react-router-dom', () => {
      renderFallbackUI();

      // 测试组件能正常渲染，说明路由集成正常
      expect(screen.getByText('连接中断')).toBeInTheDocument();
    });

  });

  describe('用户体验', () => {
    it('应该提供清晰的后续行动指引', () => {
      renderFallbackUI();

      // 检查所有行动按钮都有清晰的标签
      expect(screen.getByRole('button', { name: '重新连接' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '手动检查状态' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '重新开始分析' })).toBeInTheDocument();

      // 检查用户安心信息
      expect(screen.getByText('分析任务会继续在后台运行')).toBeInTheDocument();
      expect(screen.getByText('你可以稍后返回查看结果')).toBeInTheDocument();
    });

    it('应该按逻辑优先级排列操作按钮', () => {
      const { container } = renderFallbackUI();

      const buttons = container.querySelectorAll('button');
      expect(buttons[0]).toHaveTextContent('重新连接'); // 首选操作
      expect(buttons[1]).toHaveTextContent('手动检查状态'); // 次选操作
      expect(buttons[2]).toHaveTextContent('重新开始分析'); // 最后选择
    });
  });

  describe('边界情况', () => {
    it('应该处理onRetry为undefined的情况', () => {
      // 虽然TypeScript要求onRetry，但我们测试运行时安全性
      const propsWithUndefinedCallback = {
        taskId: 'test-task',
        error: 'test error',
        onRetry: undefined as any,
      };

      expect(() => {
        render(
          <TestWrapper>
            <FallbackUI {...propsWithUndefinedCallback} />
          </TestWrapper>
        );
      }).not.toThrow();
    });

    it('应该处理特殊字符在taskId中的情况', () => {
      const specialCharTaskId = 'task-<>&"\'123';
      renderFallbackUI({ taskId: specialCharTaskId });

      expect(screen.getByText(specialCharTaskId)).toBeInTheDocument();
    });
  });

  describe('响应式设计考虑', () => {
    it('应该使用响应式布局类', () => {
      const { container } = renderFallbackUI();

      const mainContainer = container.firstChild as HTMLElement;
      expect(mainContainer).toHaveClass('px-4'); // 响应式内边距

      const cardContainer = container.querySelector('.max-w-md');
      expect(cardContainer).toHaveClass('max-w-md', 'w-full'); // 响应式宽度
    });
  });
});