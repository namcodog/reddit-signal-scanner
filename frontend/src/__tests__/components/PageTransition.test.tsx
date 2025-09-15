/**
 * PageTransition组件单元测试
 * 测试页面过渡动画的路由响应和动画状态
 * 遵循100%类型安全和质量门禁要求
 */

import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import PageTransition from '@/components/PageTransition';
import { 
  advanceTimersAndWait, 
  setupFakeTimers, 
  cleanupFakeTimers,
  actAndWait
} from '@/test-utils';

// Mock useLocation hook
const mockLocation = {
  pathname: '/',
  search: '',
  hash: '',
  state: null,
  key: 'default',
};

const mockUseLocation = vi.fn(() => mockLocation);
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useLocation: () => mockUseLocation(),
  };
});

// 测试组件包装器
const TestWrapper: React.FC<{ children: React.ReactNode; initialPath?: string }> = ({ 
  children, 
  initialPath = '/' 
}) => (
  <MemoryRouter initialEntries={[initialPath]}>
    {children}
  </MemoryRouter>
);

// 测试子组件
const TestChild: React.FC<{ content?: string }> = ({ content = '测试内容' }) => (
  <div data-testid="test-child">{content}</div>
);

describe('PageTransition', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupFakeTimers();
    mockUseLocation.mockReturnValue({
      ...mockLocation,
      pathname: '/',
    });
  });

  afterEach(() => {
    cleanupFakeTimers();
  });

  describe('基础渲染', () => {
    it('应该正确渲染子组件', () => {
      render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      expect(screen.getByTestId('test-child')).toBeInTheDocument();
      expect(screen.getByText('测试内容')).toBeInTheDocument();
    });

    it('应该有正确的容器类名', () => {
      const { container } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      const transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toBeInTheDocument();
      expect(transitionContainer).toHaveClass(
        'transition-all',
        'duration-300',
        'ease-in-out'
      );
    });

    it('应该初始时为可见状态', () => {
      const { container } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      const transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-100', 'translate-y-0');
      expect(transitionContainer).not.toHaveClass('opacity-0', 'translate-y-2');
    });
  });

  describe('路由变化动画', () => {
    it('应该在路由变化时触发淡出动画', async () => {
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/',
      });

      const { container, rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 初始状态应该是可见的
      let transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-100', 'translate-y-0');

      // 模拟路由变化
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/analysis',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild content="新页面内容" />
          </PageTransition>
        </TestWrapper>
      );

      // 应该立即变为不可见状态
      transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-0', 'translate-y-2');
    });

    it('应该在150ms后触发淡入动画', async () => {
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/',
      });

      const { container, rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 模拟路由变化
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/report',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild content="报告页面" />
          </PageTransition>
        </TestWrapper>
      );

      // 立即检查应该是不可见状态
      let transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-0', 'translate-y-2');

      // 快进150ms并等待异步操作完成
      await advanceTimersAndWait(150);

      // 应该变为可见状态
      transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-100', 'translate-y-0');
    });

    it('应该在多次路由变化时正确处理定时器', async () => {
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/',
      });

      const { container, rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 第一次路由变化
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/analysis',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild content="分析页面" />
          </PageTransition>
        </TestWrapper>
      );

      // 快进150ms
      await advanceTimersAndWait(150);

      // 第二次路由变化（应该清除之前的定时器）
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/report',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild content="报告页面" />
          </PageTransition>
        </TestWrapper>
      );

      // 再快进150ms
      await advanceTimersAndWait(150);

      // 应该变为可见状态
      const transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-100', 'translate-y-0');
    });
  });

  describe('动画状态管理', () => {
    it('应该在相同路径时保持可见状态', () => {
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/analysis',
      });

      const { container, rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild content="原始内容" />
          </PageTransition>
        </TestWrapper>
      );

      // 相同路径，不同内容（例如状态更新）
      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild content="更新内容" />
          </PageTransition>
        </TestWrapper>
      );

      // 应该保持可见状态
      const transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-100', 'translate-y-0');
    });

    it('应该正确处理路径参数的变化', () => {
      const { container, rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 从 '/analysis/123' 到 '/analysis/456'
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/analysis/123',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild content="任务123" />
          </PageTransition>
        </TestWrapper>
      );

      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/analysis/456',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild content="任务456" />
          </PageTransition>
        </TestWrapper>
      );

      // 应该触发动画
      const transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-0', 'translate-y-2');
    });
  });

  describe('子组件处理', () => {
    it('应该支持多个子组件', () => {
      render(
        <TestWrapper>
          <PageTransition>
            <div data-testid="child-1">子组件1</div>
            <div data-testid="child-2">子组件2</div>
            <div data-testid="child-3">子组件3</div>
          </PageTransition>
        </TestWrapper>
      );

      expect(screen.getByTestId('child-1')).toBeInTheDocument();
      expect(screen.getByTestId('child-2')).toBeInTheDocument();
      expect(screen.getByTestId('child-3')).toBeInTheDocument();
    });

    it('应该支持复杂的React元素作为子组件', () => {
      const ComplexChild: React.FC = () => (
        <div>
          <h1>标题</h1>
          <p>段落内容</p>
          <button>按钮</button>
        </div>
      );

      render(
        <TestWrapper>
          <PageTransition>
            <ComplexChild />
          </PageTransition>
        </TestWrapper>
      );

      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
      expect(screen.getByText('段落内容')).toBeInTheDocument();
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('应该支持字符串作为子组件', () => {
      render(
        <TestWrapper>
          <PageTransition>
            简单的文本内容
          </PageTransition>
        </TestWrapper>
      );

      expect(screen.getByText('简单的文本内容')).toBeInTheDocument();
    });
  });

  describe('CSS类和样式', () => {
    it('应该应用正确的过渡样式', () => {
      const { container } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      const transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass(
        'transition-all',
        'duration-300',
        'ease-in-out'
      );
    });

    it('可见状态应该有正确的透明度和变换类', () => {
      const { container } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      const transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-100', 'translate-y-0');
    });

    it('不可见状态应该有正确的透明度和变换类', () => {
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/',
      });

      const { container, rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 触发路由变化
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/new-page',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      const transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-0', 'translate-y-2');
    });
  });

  describe('性能和内存管理', () => {
    it('应该在卸载时清理定时器', () => {
      const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');
      
      // 开始时在首页
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/',
      });

      const { unmount, rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 触发路由变化以创建定时器
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/new-page',
      });

      // 重新渲染以触发路径变化和定时器创建
      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild content="新页面内容" />
          </PageTransition>
        </TestWrapper>
      );

      // 卸载组件，这会触发cleanup函数调用clearTimeout
      unmount();

      // 验证clearTimeout被调用（符合PRD零技术债务要求）
      expect(clearTimeoutSpy).toHaveBeenCalled();
      clearTimeoutSpy.mockRestore();
    });

    it('应该在重复路由变化时正确清理之前的定时器', () => {
      const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');
      
      const { rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 第一次路由变化
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/page1',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 第二次路由变化（应该清理第一次的定时器）
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/page2',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      expect(clearTimeoutSpy).toHaveBeenCalled();
      clearTimeoutSpy.mockRestore();
    });
  });

  describe('边界情况', () => {
    it('应该处理undefined子组件', () => {
      expect(() => {
        render(
          <TestWrapper>
            <PageTransition>
              {undefined}
            </PageTransition>
          </TestWrapper>
        );
      }).not.toThrow();
    });

    it('应该处理null子组件', () => {
      expect(() => {
        render(
          <TestWrapper>
            <PageTransition>
              {null}
            </PageTransition>
          </TestWrapper>
        );
      }).not.toThrow();
    });

    it('应该处理空字符串子组件', () => {
      render(
        <TestWrapper>
          <PageTransition>
            {''}
          </PageTransition>
        </TestWrapper>
      );

      const { container } = render(
        <TestWrapper>
          <PageTransition>
            {''}
          </PageTransition>
        </TestWrapper>
      );

      expect(container.querySelector('.page-transition-container')).toBeInTheDocument();
    });

    it('应该处理路由对象的其他属性变化', () => {
      const { container, rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 只改变search参数，路径不变
      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/',
        search: '?param=1',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      // 不应该触发动画，因为pathname没有变化
      const transitionContainer = container.querySelector('.page-transition-container');
      expect(transitionContainer).toHaveClass('opacity-100', 'translate-y-0');
    });
  });

  describe('定时器精度', () => {
    it('应该使用150ms的正确定时器延迟', () => {
      const setTimeoutSpy = vi.spyOn(global, 'setTimeout');
      
      const { rerender } = render(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      mockUseLocation.mockReturnValue({
        ...mockLocation,
        pathname: '/new-page',
      });

      rerender(
        <TestWrapper>
          <PageTransition>
            <TestChild />
          </PageTransition>
        </TestWrapper>
      );

      expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 150);
      setTimeoutSpy.mockRestore();
    });
  });
});