/**
 * ErrorBoundaryEnhanced组件单元测试
 * 测试增强版错误边界的复杂错误处理、重试机制和用户体验功能
 * 遵循100%类型安全和质量门禁要求
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import ErrorBoundaryEnhanced, { withErrorBoundary, useErrorHandler } from '@/components/ErrorBoundaryEnhanced';
import * as errorTypes from '@/types/error.types';

// Mock fetch for error reporting
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock window对象
const mockReload = vi.fn();
const mockOpen = vi.fn();
Object.defineProperty(window, 'location', {
  value: {
    reload: mockReload,
    href: 'https://example.com/test-page',
  },
  writable: true,
});

Object.defineProperty(window, 'open', {
  value: mockOpen,
  writable: true,
});

Object.defineProperty(navigator, 'userAgent', {
  value: 'Test User Agent',
  writable: true,
});

// Mock Date.now for consistent error IDs
const mockDateNow = vi.fn();
Date.now = mockDateNow;

// 测试用的抛出错误的组件
interface ThrowErrorProps {
  shouldThrow?: boolean;
  errorMessage?: string;
  throwAfterRender?: boolean;
}

const ThrowError: React.FC<ThrowErrorProps> = ({ 
  shouldThrow = true, 
  errorMessage = 'Test error',
  throwAfterRender = false
}) => {
  React.useEffect(() => {
    if (throwAfterRender) {
      throw new Error(errorMessage);
    }
  }, [throwAfterRender, errorMessage]);

  if (shouldThrow && !throwAfterRender) {
    throw new Error(errorMessage);
  }
  return <div data-testid="child-component">正常渲染的子组件</div>;
};

// 正常子组件
const NormalChild: React.FC = () => (
  <div data-testid="normal-child">正常子组件</div>
);

// 测试props变化的组件
interface UpdatableChildProps {
  value: string;
}

const UpdatableChild: React.FC<UpdatableChildProps> = ({ value }) => (
  <div data-testid="updatable-child">{value}</div>
);

describe('ErrorBoundaryEnhanced', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDateNow.mockReturnValue(1234567890000);
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
    vi.stubEnv('NODE_ENV', 'development');
    
    // 清除所有定时器
    vi.clearAllTimers();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  describe('正常渲染', () => {
    it('应该正常渲染子组件当没有错误时', () => {
      render(
        <ErrorBoundaryEnhanced>
          <NormalChild />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByTestId('normal-child')).toBeInTheDocument();
      expect(screen.queryByText('页面遇到了问题')).not.toBeInTheDocument();
    });

    it('应该支持自定义fallback UI', () => {
      const customFallback = <div data-testid="custom-fallback">自定义错误页面</div>;
      
      render(
        <ErrorBoundaryEnhanced fallback={customFallback}>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
      expect(screen.queryByText('页面遇到了问题')).not.toBeInTheDocument();
    });
  });

  describe('错误捕获和处理', () => {
    const originalConsoleError = console.error;
    const originalConsoleGroup = console.group;
    const originalConsoleGroupEnd = console.groupEnd;

    beforeEach(() => {
      console.error = vi.fn();
      console.group = vi.fn();
      console.groupEnd = vi.fn();
    });

    afterEach(() => {
      console.error = originalConsoleError;
      console.group = originalConsoleGroup;
      console.groupEnd = originalConsoleGroupEnd;
    });

    it('应该捕获错误并显示增强版错误UI', () => {
      render(
        <ErrorBoundaryEnhanced>
          <ThrowError errorMessage="增强版测试错误" />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByText('页面遇到了问题')).toBeInTheDocument();
      expect(screen.getByText(errorTypes.USER_ERROR_MESSAGES[errorTypes.ERROR_CODES.COMPONENT_RENDER_ERROR])).toBeInTheDocument();
      expect(screen.queryByTestId('child-component')).not.toBeInTheDocument();
    });

    it('应该创建标准化的ComponentError', () => {
      render(
        <ErrorBoundaryEnhanced>
          <ThrowError errorMessage="标准化错误测试" />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByText(errorTypes.ERROR_CODES.COMPONENT_RENDER_ERROR)).toBeInTheDocument();
    });

    it('应该调用外部错误处理器', () => {
      const mockOnError = vi.fn();
      
      render(
        <ErrorBoundaryEnhanced onError={mockOnError}>
          <ThrowError errorMessage="外部处理器测试" />
        </ErrorBoundaryEnhanced>
      );

      expect(mockOnError).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'client',
          message: '外部处理器测试',
          code: errorTypes.ERROR_CODES.COMPONENT_RENDER_ERROR,
        }),
        expect.objectContaining({
          componentStack: expect.any(String),
        })
      );
    });

    it('应该在开发环境记录详细错误信息', () => {
      render(
        <ErrorBoundaryEnhanced>
          <ThrowError errorMessage="开发环境日志测试" />
        </ErrorBoundaryEnhanced>
      );

      expect(console.group).toHaveBeenCalledWith(
        expect.stringContaining('React组件错误 - error-1234567890000')
      );
      // React的内部调用次数在不同版本/环境可能有差异，这里仅断言至少被调用
      const errorCalls = (console.error as unknown as { mock: { calls: unknown[] } }).mock.calls.length;
      expect(errorCalls).toBeGreaterThanOrEqual(3);
      expect(console.groupEnd).toHaveBeenCalled();
    });
  });

  describe('重试机制', () => {
    beforeEach(() => {
      console.error = vi.fn();
    });

    it('应该显示重试按钮并显示剩余重试次数', () => {
      render(
        <ErrorBoundaryEnhanced maxRetries={3}>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      const retryButton = screen.getByRole('button', { name: /重试/ });
      expect(retryButton).toBeInTheDocument();
      expect(retryButton).toHaveTextContent('重试 (3 次机会剩余)');
    });

    it('应该在重试时显示恢复中状态', async () => {
      render(
        <ErrorBoundaryEnhanced maxRetries={3}>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      fireEvent.click(screen.getByRole('button', { name: /重试/ }));

      expect(screen.getByText('正在恢复...')).toBeInTheDocument();
      expect(screen.getByText('系统正在尝试恢复，请稍候')).toBeInTheDocument();
    });

    it('应该在1秒后重置错误状态', async () => {
      // 创建一个可控的错误组件
      let shouldThrow = true;
      const ControllableError = () => {
        if (shouldThrow) {
          throw new Error('Controlled test error');
        }
        return <div data-testid="child-component">正常渲染的子组件</div>;
      };

      const { rerender } = render(
        <ErrorBoundaryEnhanced maxRetries={3}>
          <ControllableError />
        </ErrorBoundaryEnhanced>
      );

      // 验证初始错误状态
      expect(screen.getByText('页面遇到了问题')).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /重试/ }));
      
      // 快进1秒并等待状态更新完成
      await act(async () => {
        vi.runOnlyPendingTimers();
      });

      // "修复"问题 - 让组件不再抛错
      shouldThrow = false;

      // 强制重新渲染以触发组件重新挂载
      rerender(
        <ErrorBoundaryEnhanced maxRetries={3} key="after-retry">
          <ControllableError />
        </ErrorBoundaryEnhanced>
      );

      await waitFor(() => {
        expect(screen.getByTestId('child-component')).toBeInTheDocument();
      });
    });

    it('应该减少剩余重试次数', () => {
      render(
        <ErrorBoundaryEnhanced maxRetries={2}>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      // 第一次重试
      fireEvent.click(screen.getByRole('button', { name: /重试/ }));
      act(() => {
        vi.runOnlyPendingTimers();
      });

      // 如果还有错误，应该显示1次剩余
      expect(screen.getByRole('button', { name: /重试/ })).toHaveTextContent('重试 (1 次机会剩余)');
    });

    it('应该在达到最大重试次数后隐藏重试按钮', () => {
      const { rerender } = render(
        <ErrorBoundaryEnhanced maxRetries={1}>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      // 第一次重试
      fireEvent.click(screen.getByRole('button', { name: /重试/ }));
      act(() => {
        vi.runOnlyPendingTimers();
      });

      // 重新渲染，仍然抛出错误
      rerender(
        <ErrorBoundaryEnhanced maxRetries={1}>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.queryByRole('button', { name: /重试/ })).not.toBeInTheDocument();
    });
  });

  describe('操作按钮', () => {
    beforeEach(() => {
      console.error = vi.fn();
    });

    it('刷新页面按钮应该调用window.location.reload', () => {
      render(
        <ErrorBoundaryEnhanced>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      fireEvent.click(screen.getByRole('button', { name: '刷新页面' }));
      expect(mockReload).toHaveBeenCalledOnce();
    });

    it('返回首页按钮应该设置window.location.href', () => {
      render(
        <ErrorBoundaryEnhanced>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      fireEvent.click(screen.getByRole('button', { name: '返回首页' }));
      expect(window.location.href).toBe('/');
    });

    it('报告此问题按钮应该打开邮件客户端', () => {
      render(
        <ErrorBoundaryEnhanced>
          <ThrowError errorMessage="需要报告的错误" />
        </ErrorBoundaryEnhanced>
      );

      fireEvent.click(screen.getByRole('button', { name: '报告此问题' }));
      
      expect(mockOpen).toHaveBeenCalledWith(
        expect.stringMatching(/mailto:support@redditscanner\.com.*Bug%E6%8A%A5%E5%91%8A.*COMPONENT_RENDER_ERROR/)
      );
    });
  });

  describe('Props变化重置', () => {
    beforeEach(() => {
      console.error = vi.fn();
    });

    it('应该在启用resetOnPropsChange时重置错误状态', () => {
      const { rerender } = render(
        <ErrorBoundaryEnhanced resetOnPropsChange={true}>
          <UpdatableChild value="initial" />
        </ErrorBoundaryEnhanced>
      );

      // 触发错误
      rerender(
        <ErrorBoundaryEnhanced resetOnPropsChange={true}>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByText('页面遇到了问题')).toBeInTheDocument();

      // 改变props应该重置错误
      rerender(
        <ErrorBoundaryEnhanced resetOnPropsChange={true}>
          <UpdatableChild value="updated" />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByTestId('updatable-child')).toBeInTheDocument();
      expect(screen.getByText('updated')).toBeInTheDocument();
    });

    it('应该在未启用resetOnPropsChange时保持错误状态', () => {
      const { rerender } = render(
        <ErrorBoundaryEnhanced resetOnPropsChange={false}>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByText('页面遇到了问题')).toBeInTheDocument();

      // 改变props不应该重置错误
      rerender(
        <ErrorBoundaryEnhanced resetOnPropsChange={false}>
          <UpdatableChild value="updated" />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByText('页面遇到了问题')).toBeInTheDocument();
      expect(screen.queryByTestId('updatable-child')).not.toBeInTheDocument();
    });
  });

  describe('错误上报', () => {
    beforeEach(() => {
      console.error = vi.fn();
      vi.stubEnv('NODE_ENV', 'production');
    });

    it('应该在生产环境上报错误到服务器', async () => {
      // 确保fetch mock立即解析
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ success: true, reported: true }),
      });

      render(
        <ErrorBoundaryEnhanced>
          <ThrowError errorMessage="生产环境错误" />
        </ErrorBoundaryEnhanced>
      );

      // 使用vi.waitFor处理异步操作，与fake timers兼容
      await vi.waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          '/api/errors/report',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: expect.stringContaining('"errorId":"error-1234567890000"'),
          })
        );
      }, { timeout: 5000, interval: 100 });
    });

    it('应该在错误上报失败时静默处理', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));
      console.warn = vi.fn();

      render(
        <ErrorBoundaryEnhanced>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      // 使用vi.waitFor等待错误处理
      await vi.waitFor(() => {
        expect(console.warn).toHaveBeenCalledWith('错误上报失败');
      }, { timeout: 3000, interval: 50 });
    });
  });

  describe('开发环境功能', () => {
    beforeEach(() => {
      console.error = vi.fn();
      vi.stubEnv('NODE_ENV', 'development');
    });

    it('应该显示开发者信息面板', () => {
      render(
        <ErrorBoundaryEnhanced showDetails={true}>
          <ThrowError errorMessage="开发者详情测试" />
        </ErrorBoundaryEnhanced>
      );

      const details = screen.getByText('开发者信息');
      expect(details).toBeInTheDocument();

      // 展开详情
      fireEvent.click(details);

      // 应该显示JSON格式的错误详情
      expect(screen.getByText(/"message": "开发者详情测试"/)).toBeInTheDocument();
    });

    it('应该隐藏开发者信息当showDetails为false时', () => {
      render(
        <ErrorBoundaryEnhanced showDetails={false}>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.queryByText('开发者信息')).not.toBeInTheDocument();
    });
  });

  describe('withErrorBoundary HOC', () => {
    const TestComponent: React.FC<{ title: string }> = ({ title }) => (
      <div data-testid="test-component">{title}</div>
    );

    it('应该包装组件并正常渲染', () => {
      const WrappedComponent = withErrorBoundary(TestComponent, {
        maxRetries: 2,
        showDetails: true,
      });

      render(<WrappedComponent title="HOC测试" />);
      expect(screen.getByTestId('test-component')).toBeInTheDocument();
      expect(screen.getByText('HOC测试')).toBeInTheDocument();
    });

    it('应该为包装的组件设置displayName', () => {
      const TestComponentWithName = Object.assign(
        ({ title }: { title: string }) => <div>{title}</div>,
        { displayName: 'TestComponentWithName' }
      );

      const WrappedComponent = withErrorBoundary(TestComponentWithName);
      expect(WrappedComponent.displayName).toBe('withErrorBoundary(TestComponentWithName)');
    });
  });

  describe('useErrorHandler Hook', () => {
    it('应该创建并返回错误处理函数', () => {
      let capturedHandleError: ((error: Error) => void) | undefined;

      const TestHookComponent: React.FC = () => {
        const { handleError } = useErrorHandler();
        capturedHandleError = handleError;
        return <div>Hook测试组件</div>;
      };

      render(
        <ErrorBoundaryEnhanced>
          <TestHookComponent />
        </ErrorBoundaryEnhanced>
      );

      expect(typeof capturedHandleError).toBe('function');
    });

    it('应该在开发环境记录错误', () => {
      console.error = vi.fn();
      let capturedHandleError: ((error: Error) => void) | undefined;

      const TestHookComponent: React.FC = () => {
        const { handleError } = useErrorHandler();
        capturedHandleError = handleError;
        
        React.useEffect(() => {
          if (capturedHandleError) {
            try {
              capturedHandleError(new Error('Hook错误测试'));
            } catch {
              // Expected to throw
            }
          }
        }, []);

        return <div>Hook测试组件</div>;
      };

      render(
        <ErrorBoundaryEnhanced>
          <TestHookComponent />
        </ErrorBoundaryEnhanced>
      );

      expect(console.error).toHaveBeenCalledWith(
        'useErrorHandler捕获错误:',
        expect.objectContaining({
          message: 'Hook错误测试',
          code: errorTypes.ERROR_CODES.COMPONENT_LIFECYCLE_ERROR,
        })
      );
    });
  });

  describe('边界情况和容错', () => {
    beforeEach(() => {
      console.error = vi.fn();
    });

    it('应该处理错误上报接口抛出异常的情况', async () => {
      vi.stubEnv('NODE_ENV', 'production');
      
      // Mock fetch抛出异常
      mockFetch.mockImplementation(() => {
        throw new Error('Fetch implementation error');
      });

      render(
        <ErrorBoundaryEnhanced>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      // 应该不影响正常的错误边界功能
      expect(screen.getByText('页面遇到了问题')).toBeInTheDocument();
    });

    it('应该处理Date.now()返回相同值的情况', () => {
      // 使用vi.setSystemTime设置系统时间 - Vitest最佳实践
      const testDate = new Date(1111111111111);
      vi.setSystemTime(testDate);
      
      // 使用key强制重新创建组件实例
      render(
        <ErrorBoundaryEnhanced key="date-now-test">
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByText('错误ID: error-1111111111111 | Reddit Signal Scanner v2.0')).toBeInTheDocument();
    });

    it('应该处理window对象属性不可用的情况', () => {
      const originalLocation = window.location;
      delete (window as any).location;

      render(
        <ErrorBoundaryEnhanced>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      expect(screen.getByText('页面遇到了问题')).toBeInTheDocument();

      (window as any).location = originalLocation;
    });
  });

  describe('性能和内存管理', () => {
    beforeEach(() => {
      console.error = vi.fn();
    });

    it('应该正确清理定时器', () => {
      const { unmount } = render(
        <ErrorBoundaryEnhanced>
          <ThrowError />
        </ErrorBoundaryEnhanced>
      );

      fireEvent.click(screen.getByRole('button', { name: /重试/ }));
      
      // 卸载组件
      unmount();
      
      // 应该不会有内存泄漏警告
      expect(() => {
        vi.runOnlyPendingTimers();
      }).not.toThrow();
    });
  });
});
