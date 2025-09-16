/**
 * NotFoundPage组件单元测试
 * 测试404错误页面的渲染和导航功能
 * 遵循100%类型安全和质量门禁要求
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import NotFoundPage from '@/pages/NotFoundPage';

// 类型定义 - 严格遵循质量门禁规则
interface MockNavigateFunction {
  (to: string): void;
  (delta: number): void;
}

// Mock react-router-dom
const mockNavigate = vi.fn<Parameters<MockNavigateFunction>, void>();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock window.history
const mockHistoryBack = vi.fn();
Object.defineProperty(window, 'history', {
  value: {
    back: mockHistoryBack,
  },
  writable: true,
});

// 测试工具函数
const renderNotFoundPageWithRouter = () => {
  return render(
    <MemoryRouter>
      <NotFoundPage />
    </MemoryRouter>
  );
};

describe('NotFoundPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('基础渲染', () => {
    it('应该正确渲染404页面标题和内容', () => {
      renderNotFoundPageWithRouter();

      expect(screen.getByText('404')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 1, name: '页面未找到' })).toBeInTheDocument();
      expect(screen.getByText('抱歉，您要访问的页面不存在。可能是链接错误或页面已被移动。')).toBeInTheDocument();
    });

    it('应该显示大号的404文字', () => {
      const { container } = renderNotFoundPageWithRouter();

      const notFoundNumber = container.querySelector('.text-9xl.font-bold.text-gray-400');
      expect(notFoundNumber).toBeInTheDocument();
      expect(notFoundNumber).toHaveTextContent('404');
    });

    it('应该居中显示所有内容', () => {
      const { container } = renderNotFoundPageWithRouter();

      const centerContainer = container.querySelector('.text-center');
      expect(centerContainer).toBeInTheDocument();

      const flexContainer = container.querySelector('.min-h-screen.bg-gray-50.flex.items-center.justify-center');
      expect(flexContainer).toBeInTheDocument();
    });
  });

  describe('导航按钮', () => {
    it('应该渲染返回首页和返回上页按钮', () => {
      renderNotFoundPageWithRouter();

      const homeButton = screen.getByRole('link', { name: '返回首页' });
      const backButton = screen.getByRole('button', { name: '返回上页' });

      expect(homeButton).toBeInTheDocument();
      expect(backButton).toBeInTheDocument();
    });

    it('返回首页按钮应该链接到根路径', () => {
      renderNotFoundPageWithRouter();

      const homeButton = screen.getByRole('link', { name: '返回首页' });
      expect(homeButton).toHaveAttribute('href', '/');
    });

    it('返回上页按钮应该调用window.history.back', () => {
      renderNotFoundPageWithRouter();

      const backButton = screen.getByRole('button', { name: '返回上页' });
      fireEvent.click(backButton);

      expect(mockHistoryBack).toHaveBeenCalledTimes(1);
    });
  });

  describe('按钮样式', () => {
    it('返回首页按钮应该有正确的样式类', () => {
      renderNotFoundPageWithRouter();

      const homeButton = screen.getByRole('link', { name: '返回首页' });
      expect(homeButton).toHaveClass(
        'inline-flex',
        'items-center',
        'px-4',
        'py-2',
        'border',
        'border-transparent',
        'text-base',
        'font-medium',
        'rounded-md',
        'text-white',
        'bg-blue-600',
        'hover:bg-blue-700',
        'focus:outline-none',
        'focus:ring-2',
        'focus:ring-blue-500',
        'focus:ring-offset-2'
      );
    });

    it('返回上页按钮应该有正确的样式类', () => {
      renderNotFoundPageWithRouter();

      const backButton = screen.getByRole('button', { name: '返回上页' });
      expect(backButton).toHaveClass(
        'inline-flex',
        'items-center',
        'px-4',
        'py-2',
        'border',
        'border-gray-300',
        'text-base',
        'font-medium',
        'rounded-md',
        'text-gray-700',
        'bg-white',
        'hover:bg-gray-50',
        'focus:outline-none',
        'focus:ring-2',
        'focus:ring-blue-500',
        'focus:ring-offset-2'
      );
    });

    it('按钮容器应该有正确的间距', () => {
      const { container } = renderNotFoundPageWithRouter();

      const buttonContainer = container.querySelector('.space-x-4');
      expect(buttonContainer).toBeInTheDocument();
    });
  });

  describe('页面布局和样式', () => {
    it('应该有正确的背景色和布局', () => {
      const { container } = renderNotFoundPageWithRouter();

      const mainContainer = container.querySelector('.min-h-screen.bg-gray-50');
      expect(mainContainer).toBeInTheDocument();
    });

    it('应该有合适的内边距', () => {
      const { container } = renderNotFoundPageWithRouter();

      const paddingContainer = container.querySelector('.px-4');
      expect(paddingContainer).toBeInTheDocument();
    });

    it('404数字应该有正确的颜色和大小', () => {
      const { container } = renderNotFoundPageWithRouter();

      const notFoundText = container.querySelector('.text-9xl.font-bold.text-gray-400');
      expect(notFoundText).toBeInTheDocument();
    });

    it('标题应该有正确的样式', () => {
      renderNotFoundPageWithRouter();

      const title = screen.getByRole('heading', { level: 1 });
      expect(title).toHaveClass('text-2xl', 'font-bold', 'text-gray-900', 'mb-4');
    });

    it('描述文本应该有正确的样式和最大宽度', () => {
      const { container } = renderNotFoundPageWithRouter();

      const description = container.querySelector('.text-gray-600.mb-8.max-w-md');
      expect(description).toBeInTheDocument();
      expect(description).toHaveTextContent('抱歉，您要访问的页面不存在。可能是链接错误或页面已被移动。');
    });
  });

  describe('品牌信息', () => {
    it('应该显示项目品牌信息', () => {
      renderNotFoundPageWithRouter();

      expect(screen.getByText('Reddit Signal Scanner')).toBeInTheDocument();
      expect(screen.getByText('基于 Linus Torvalds 设计哲学')).toBeInTheDocument();
    });

    it('品牌信息应该有正确的样式和位置', () => {
      const { container } = renderNotFoundPageWithRouter();

      const brandContainer = container.querySelector('.mt-12.text-sm.text-gray-500');
      expect(brandContainer).toBeInTheDocument();
    });
  });

  describe('可访问性', () => {
    it('应该具有正确的语义HTML结构', () => {
      renderNotFoundPageWithRouter();

      // 检查标题层级
      const h1 = screen.getByRole('heading', { level: 1 });
      expect(h1).toHaveTextContent('页面未找到');
    });

    it('按钮应该支持键盘导航', () => {
      renderNotFoundPageWithRouter();

      const homeButton = screen.getByRole('link', { name: '返回首页' });
      const backButton = screen.getByRole('button', { name: '返回上页' });

      expect(homeButton).not.toHaveAttribute('tabIndex', '-1');
      expect(backButton).not.toHaveAttribute('tabIndex', '-1');
    });

    it('按钮应该具有焦点样式', () => {
      renderNotFoundPageWithRouter();

      const homeButton = screen.getByRole('link', { name: '返回首页' });
      const backButton = screen.getByRole('button', { name: '返回上页' });

      expect(homeButton).toHaveClass('focus:outline-none', 'focus:ring-2');
      expect(backButton).toHaveClass('focus:outline-none', 'focus:ring-2');
    });

    it('按钮应该有适当的颜色对比度', () => {
      renderNotFoundPageWithRouter();

      const homeButton = screen.getByRole('link', { name: '返回首页' });
      const backButton = screen.getByRole('button', { name: '返回上页' });

      // 主要按钮：白色文字 + 蓝色背景
      expect(homeButton).toHaveClass('text-white', 'bg-blue-600');
      
      // 次要按钮：深色文字 + 白色背景
      expect(backButton).toHaveClass('text-gray-700', 'bg-white');
    });
  });

  describe('响应式设计', () => {
    it('应该在不同屏幕尺寸下正确显示', () => {
      const { container } = renderNotFoundPageWithRouter();

      // 检查响应式容器
      const responsiveContainer = container.querySelector('.min-h-screen');
      expect(responsiveContainer).toBeInTheDocument();
    });

    it('文本应该有合适的最大宽度以保持可读性', () => {
      const { container } = renderNotFoundPageWithRouter();

      const textContainer = container.querySelector('.max-w-md');
      expect(textContainer).toBeInTheDocument();
    });
  });

  describe('用户体验', () => {
    it('应该提供两种导航选项', () => {
      renderNotFoundPageWithRouter();

      // 用户可以选择回到首页或者回到上一页
      expect(screen.getByRole('link', { name: '返回首页' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '返回上页' })).toBeInTheDocument();
    });

    it('应该有友好的错误消息', () => {
      renderNotFoundPageWithRouter();

      const message = screen.getByText('抱歉，您要访问的页面不存在。可能是链接错误或页面已被移动。');
      expect(message).toBeInTheDocument();
      
      // 消息应该解释可能的原因
      expect(message.textContent).toContain('链接错误');
      expect(message.textContent).toContain('页面已被移动');
    });

    it('错误页面应该保持品牌一致性', () => {
      renderNotFoundPageWithRouter();

      // 显示项目名称
      expect(screen.getByText('Reddit Signal Scanner')).toBeInTheDocument();
      
      // 显示设计哲学，保持品牌调性
      expect(screen.getByText('基于 Linus Torvalds 设计哲学')).toBeInTheDocument();
    });
  });

  describe('边界情况处理', () => {
    it('应该在history.back不可用时正常渲染', () => {
      // 临时删除history.back
      const originalBack = window.history.back;
      delete (window.history as { back?: () => void }).back;

      renderNotFoundPageWithRouter();

      expect(screen.getByRole('button', { name: '返回上页' })).toBeInTheDocument();

      // 恢复
      window.history.back = originalBack;
    });

    it('应该在多次点击返回上页按钮时正常工作', () => {
      renderNotFoundPageWithRouter();

      const backButton = screen.getByRole('button', { name: '返回上页' });
      
      // 多次点击
      fireEvent.click(backButton);
      fireEvent.click(backButton);
      fireEvent.click(backButton);

      expect(mockHistoryBack).toHaveBeenCalledTimes(3);
    });

    it('应该处理快速连续的按钮点击', () => {
      renderNotFoundPageWithRouter();

      const backButton = screen.getByRole('button', { name: '返回上页' });
      
      // 快速连续点击
      fireEvent.click(backButton);
      fireEvent.click(backButton);

      // 应该都被调用
      expect(mockHistoryBack).toHaveBeenCalledTimes(2);
    });
  });

  describe('页面元数据', () => {
    it('应该包含所有必要的文本内容', () => {
      renderNotFoundPageWithRouter();

      const expectedTexts = [
        '404',
        '页面未找到',
        '抱歉，您要访问的页面不存在。可能是链接错误或页面已被移动。',
        '返回首页',
        '返回上页',
        'Reddit Signal Scanner',
        '基于 Linus Torvalds 设计哲学',
      ];

      expectedTexts.forEach((text) => {
        expect(screen.getByText(text)).toBeInTheDocument();
      });
    });
  });
});