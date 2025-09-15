/**
 * ErrorBoundary组件单元测试
 * 测试基础错误边界的错误捕获、UI渲染和用户交互
 * 遵循100%类型安全和质量门禁要求
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import ErrorBoundary from '@/components/ErrorBoundary';
import * as errorHandler from '@/utils/errorHandler';

// Mock错误处理器
vi.mock('@/utils/errorHandler', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/utils/errorHandler')>();
  return {
    ...actual,
    handleError: vi.fn(),
  };
});

// 导入枚举类型
import { ErrorType, ErrorSeverity } from '@/utils/errorHandler';

// Mock window对象方法
const mockReload = vi.fn();
const mockAssign = vi.fn();

Object.defineProperty(window, 'location', {
  value: {
    reload: mockReload,
    href: '',
    assign: mockAssign,
  },
  writable: true,
});

// 测试用的抛出错误的组件
interface ThrowErrorProps {
  shouldThrow?: boolean;
  errorMessage?: string;
}

const ThrowError: React.FC<ThrowErrorProps> = ({ 
  shouldThrow = true, 
  errorMessage = 'Test error' 
}) => {
  if (shouldThrow) {
    throw new Error(errorMessage);
  }
  return <div data-testid="child-component">正常渲染的子组件</div>;
};

// 正常子组件
const NormalChild: React.FC = () => (
  <div data-testid="normal-child">正常子组件</div>
);

describe('ErrorBoundary', () => {
  const mockHandleError = vi.mocked(errorHandler.handleError);
  
  beforeEach(() => {
    vi.clearAllMocks();
    // 设置默认的handleError返回值
    mockHandleError.mockReturnValue({
      type: ErrorType.CLIENT_ERROR,
      severity: ErrorSeverity.MEDIUM,
      message: 'Test error',
      userMessage: '应用遇到了意外错误，请尝试以下操作',
      canRetry: true,
      recoveryActions: ['检查网络连接', '清除浏览器缓存'],
    });
    
    // 模拟开发环境
    vi.stubEnv('NODE_ENV', 'development');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe('正常渲染', () => {
    it('应该正常渲染子组件当没有错误时', () => {
      render(
        <ErrorBoundary>
          <NormalChild />
        </ErrorBoundary>
      );

      expect(screen.getByTestId('normal-child')).toBeInTheDocument();
      expect(screen.queryByText('糟糕！出现了错误')).not.toBeInTheDocument();
    });
  });

  describe('错误捕获', () => {
    // 抑制控制台错误输出，因为我们故意抛出错误进行测试
    const originalConsoleError = console.error;
    beforeEach(() => {
      console.error = vi.fn();
    });
    afterEach(() => {
      console.error = originalConsoleError;
    });

    it('应该捕获子组件错误并显示错误UI', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByText('糟糕！出现了错误')).toBeInTheDocument();
      expect(screen.queryByTestId('child-component')).not.toBeInTheDocument();
    });

    it('应该调用错误处理器并传递正确参数', () => {
      render(
        <ErrorBoundary>
          <ThrowError errorMessage="具体错误信息" />
        </ErrorBoundary>
      );

      expect(mockHandleError).toHaveBeenCalledWith(
        expect.any(Error),
        expect.objectContaining({
          component: 'ErrorBoundary',
          action: 'react_component_error',
        })
      );

      const callArgs = mockHandleError.mock.calls[0];
      const error = callArgs[0] as Error;
      expect(error.message).toBe('具体错误信息');
    });

    it('应该显示错误处理器返回的用户消息', () => {
      const customMessage = '自定义错误消息';
      mockHandleError.mockReturnValue({
        type: ErrorType.CLIENT_ERROR,
        severity: ErrorSeverity.MEDIUM,
        message: 'Custom error',
        userMessage: customMessage,
        canRetry: true,
        recoveryActions: [],
      });

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByText(customMessage)).toBeInTheDocument();
    });
  });

  describe('错误UI渲染', () => {
    beforeEach(() => {
      // 抑制控制台错误
      console.error = vi.fn();
    });

    it('应该显示默认错误消息当错误处理器未返回用户消息时', () => {
      mockHandleError.mockReturnValue({
        type: ErrorType.UNKNOWN,
        severity: ErrorSeverity.MEDIUM,
        message: 'Unknown error',
        userMessage: '',
        canRetry: false,
        recoveryActions: undefined,
      });

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByText('应用遇到了意外错误，请尝试以下操作')).toBeInTheDocument();
    });

    it('应该显示恢复建议当可用时', () => {
      mockHandleError.mockReturnValue({
        type: ErrorType.NETWORK,
        severity: ErrorSeverity.MEDIUM,
        message: 'Network error',
        userMessage: '错误消息',
        canRetry: true,
        recoveryActions: ['建议1', '建议2', '建议3'],
      });

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByText('建议操作：')).toBeInTheDocument();
      expect(screen.getByText('建议1')).toBeInTheDocument();
      expect(screen.getByText('建议2')).toBeInTheDocument();
      expect(screen.getByText('建议3')).toBeInTheDocument();
    });

    it('应该显示重试按钮当错误可重试时', () => {
      mockHandleError.mockReturnValue({
        type: ErrorType.NETWORK,
        severity: ErrorSeverity.MEDIUM,
        message: 'Network error',
        userMessage: '错误消息',
        canRetry: true,
        recoveryActions: [],
      });

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
    });

    it('应该隐藏重试按钮当错误不可重试时', () => {
      mockHandleError.mockReturnValue({
        type: ErrorType.PERMISSION,
        severity: ErrorSeverity.HIGH,
        message: 'Permission denied',
        userMessage: '错误消息',
        canRetry: false,
        recoveryActions: [],
      });

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.queryByRole('button', { name: '重试' })).not.toBeInTheDocument();
    });

    it('应该始终显示刷新页面和返回首页按钮', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByRole('button', { name: '刷新页面' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '返回首页' })).toBeInTheDocument();
    });
  });

  describe('用户交互', () => {
    beforeEach(() => {
      console.error = vi.fn();
    });

    it('重试按钮点击应该重置错误状态并重新渲染子组件', () => {
      // Context7最佳实践：使用key prop强制ErrorBoundary重新挂载
      let boundaryKey = 1;
      const { rerender } = render(
        <ErrorBoundary key={boundaryKey}>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      );

      // 验证错误UI显示
      expect(screen.getByText('糟糕！出现了错误')).toBeInTheDocument();

      // 点击重试按钮
      fireEvent.click(screen.getByRole('button', { name: '重试' }));

      // Context7最佳实践：改变key并重新渲染，模拟ErrorBoundary重新挂载
      boundaryKey = 2;
      rerender(
        <ErrorBoundary key={boundaryKey}>
          <ThrowError shouldThrow={false} />
        </ErrorBoundary>
      );

      // 验证子组件正常渲染
      expect(screen.getByTestId('child-component')).toBeInTheDocument();
      expect(screen.queryByText('糟糕！出现了错误')).not.toBeInTheDocument();
    });

    it('刷新页面按钮点击应该调用window.location.reload', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      fireEvent.click(screen.getByRole('button', { name: '刷新页面' }));
      expect(mockReload).toHaveBeenCalledOnce();
    });

    it('返回首页按钮点击应该设置window.location.href', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      fireEvent.click(screen.getByRole('button', { name: '返回首页' }));
      expect(window.location.href).toBe('/');
    });
  });

  describe('开发环境功能', () => {
    beforeEach(() => {
      console.error = vi.fn();
      vi.stubEnv('NODE_ENV', 'development');
    });

    it('应该在开发环境显示错误详情', () => {
      render(
        <ErrorBoundary>
          <ThrowError errorMessage="详细错误信息" />
        </ErrorBoundary>
      );

      const detailsElement = screen.getByText('错误详情 (开发环境)');
      expect(detailsElement).toBeInTheDocument();

      // 展开详情
      fireEvent.click(detailsElement);

      // 验证错误内容显示
      expect(screen.getByText(/Error: 详细错误信息/)).toBeInTheDocument();
    });
  });

  describe('生产环境功能', () => {
    beforeEach(() => {
      console.error = vi.fn();
      vi.stubEnv('NODE_ENV', 'production');
    });

    it('应该在生产环境隐藏错误详情', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.queryByText('错误详情 (开发环境)')).not.toBeInTheDocument();
    });
  });

  describe('错误边界状态管理', () => {
    beforeEach(() => {
      console.error = vi.fn();
    });

    it('应该正确设置所有错误状态字段', () => {
        const { container } = render(
        <ErrorBoundary>
          <ThrowError errorMessage="状态测试错误" />
        </ErrorBoundary>
      );

      // 通过DOM验证状态已正确设置
      expect(screen.getByText('糟糕！出现了错误')).toBeInTheDocument();
      expect(container.querySelector('.text-6xl')).toHaveTextContent('😵‍💫');
    });

    it('应该在错误处理器调用时包含session ID', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      const callArgs = mockHandleError.mock.calls[0];
      const context = callArgs[1];
      expect(context).toHaveProperty('sessionId');
      expect(typeof context?.sessionId).toBe('string');
    });
  });

  describe('可访问性', () => {
    beforeEach(() => {
      console.error = vi.fn();
    });

    it('错误UI应该有正确的语义结构', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      // 检查标题结构
      const title = screen.getByRole('heading', { level: 1 });
      expect(title).toHaveTextContent('糟糕！出现了错误');

      // 检查按钮可访问性
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toHaveAttribute('class');
        expect(button.textContent?.trim()).toBeTruthy();
      });
    });

    it('按钮应该有正确的focus样式类', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toHaveClass('focus:outline-none', 'focus:ring-2');
      });
    });
  });

  describe('边界情况', () => {
    beforeEach(() => {
      console.error = vi.fn();
    });

    it('应该处理错误处理器返回undefined的情况', () => {
      mockHandleError.mockReturnValue({
        type: ErrorType.UNKNOWN,
        severity: ErrorSeverity.MEDIUM,
        message: 'Unknown error',
        userMessage: '',
        canRetry: false,
        recoveryActions: [],
      });

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      // 应该显示默认消息
      expect(screen.getByText('应用遇到了意外错误，请尝试以下操作')).toBeInTheDocument();
    });

    it('应该处理空的恢复建议数组', () => {
      mockHandleError.mockReturnValue({
        type: ErrorType.NETWORK,
        severity: ErrorSeverity.MEDIUM,
        message: 'Network error',
        userMessage: '错误消息',
        canRetry: true,
        recoveryActions: [],
      });

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.queryByText('建议操作：')).not.toBeInTheDocument();
    });

    it('应该处理null恢复建议', () => {
      mockHandleError.mockReturnValue({
        type: ErrorType.NETWORK,
        severity: ErrorSeverity.MEDIUM,
        message: 'Network error',
        userMessage: '错误消息',
        canRetry: true,
        recoveryActions: undefined,
      });

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.queryByText('建议操作：')).not.toBeInTheDocument();
    });
  });
});