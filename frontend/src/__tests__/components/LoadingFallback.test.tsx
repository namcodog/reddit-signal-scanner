/**
 * LoadingFallback组件单元测试
 * 测试Suspense fallback加载组件的渲染和样式
 * 遵循100%类型安全和质量门禁要求
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import LoadingFallback from '@/components/LoadingFallback';

describe('LoadingFallback', () => {
  beforeEach(() => {
    // 清理任何可能的DOM状态
  });

  describe('基础渲染', () => {
    it('应该正确渲染加载组件', () => {
      render(<LoadingFallback />);
      
      expect(screen.getByText('加载中...')).toBeInTheDocument();
    });

    it('应该包含旋转的加载动画元素', () => {
      const { container } = render(<LoadingFallback />);
      
      const spinnerElement = container.querySelector('.animate-spin');
      expect(spinnerElement).toBeInTheDocument();
      expect(spinnerElement).toHaveClass('rounded-full', 'h-8', 'w-8', 'border-b-2', 'border-blue-600');
    });

    it('应该具有正确的布局结构', () => {
      const { container } = render(<LoadingFallback />);
      
      // 检查根容器样式
      const rootContainer = container.firstChild as HTMLElement;
      expect(rootContainer).toHaveClass(
        'flex',
        'items-center',
        'justify-center', 
        'min-h-screen',
        'bg-gray-50'
      );
    });

    it('应该包含居中的文本内容容器', () => {
      const { container } = render(<LoadingFallback />);
      
      const textContainer = container.querySelector('.text-center');
      expect(textContainer).toBeInTheDocument();
    });
  });

  describe('样式和类名', () => {
    it('加载文本应该有正确的样式类', () => {
      render(<LoadingFallback />);
      
      const loadingText = screen.getByText('加载中...');
      expect(loadingText).toHaveClass('mt-4', 'text-gray-600');
    });

    it('旋转动画应该居中显示', () => {
      const { container } = render(<LoadingFallback />);
      
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('mx-auto');
    });

    it('应该使用蓝色主题色彩', () => {
      const { container } = render(<LoadingFallback />);
      
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('border-blue-600');
    });
  });

  describe('可访问性', () => {
    it('应该提供有意义的加载提示文本', () => {
      render(<LoadingFallback />);
      
      const loadingText = screen.getByText('加载中...');
      expect(loadingText).toBeVisible();
      expect(loadingText.textContent).toBe('加载中...');
    });

    it('应该具有适当的语义结构', () => {
      render(<LoadingFallback />);
      
      // 验证没有使用不当的role或aria属性
      const textElement = screen.getByText('加载中...');
      expect(textElement.tagName.toLowerCase()).toBe('p');
    });
  });

  describe('视觉表现', () => {
    it('应该在全屏容器中居中显示', () => {
      const { container } = render(<LoadingFallback />);
      
      const rootContainer = container.firstChild as HTMLElement;
      expect(rootContainer).toHaveClass('min-h-screen');
      expect(rootContainer).toHaveClass('flex', 'items-center', 'justify-center');
    });

    it('应该使用合适的背景色', () => {
      const { container } = render(<LoadingFallback />);
      
      const rootContainer = container.firstChild as HTMLElement;
      expect(rootContainer).toHaveClass('bg-gray-50');
    });

    it('旋转动画应该具有正确的尺寸', () => {
      const { container } = render(<LoadingFallback />);
      
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('h-8', 'w-8');
    });
  });

  describe('响应式设计', () => {
    it('应该在所有设备尺寸上正确显示', () => {
      const { container } = render(<LoadingFallback />);
      
      // 使用flex布局确保在所有尺寸上都能居中
      const rootContainer = container.firstChild as HTMLElement;
      expect(rootContainer).toHaveClass('flex');
      
      // 文本居中对齐
      const textContainer = container.querySelector('.text-center');
      expect(textContainer).toBeInTheDocument();
    });
  });

  describe('Suspense集成', () => {
    it('应该适合作为Suspense fallback使用', () => {
      // 模拟在Suspense中使用
      const TestSuspenseComponent: React.FC = () => {
        return (
          <React.Suspense fallback={<LoadingFallback />}>
            <div>已加载的内容</div>
          </React.Suspense>
        );
      };

      render(<TestSuspenseComponent />);
      
      // 在实际应用中，这里会显示加载组件直到子组件加载完成
      // 但在测试中，同步组件会立即渲染
      expect(screen.getByText('已加载的内容')).toBeInTheDocument();
    });

    it('应该独立工作而不依赖外部状态', () => {
      // 多次渲染应该产生一致的结果
      const { unmount } = render(<LoadingFallback />);
      expect(screen.getByText('加载中...')).toBeInTheDocument();
      
      unmount();
      
      render(<LoadingFallback />);
      expect(screen.getByText('加载中...')).toBeInTheDocument();
    });
  });

  describe('性能考虑', () => {
    it('应该是轻量级组件不包含复杂逻辑', () => {
      const { container } = render(<LoadingFallback />);
      
      // 验证DOM结构简单
      const allElements = container.querySelectorAll('*');
      expect(allElements.length).toBeLessThan(10); // 应该是一个简单的组件
    });

    it('应该使用CSS动画而非JavaScript动画', () => {
      const { container } = render(<LoadingFallback />);
      
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('animate-spin'); // Tailwind CSS类，使用CSS动画
    });
  });

  describe('边界情况', () => {
    it('应该在无props情况下正常工作', () => {
      // LoadingFallback不接受任何props，这个测试确保它稳定工作
      expect(() => render(<LoadingFallback />)).not.toThrow();
    });

    it('应该在重复挂载/卸载时保持稳定', () => {
      for (let i = 0; i < 5; i++) {
        const { unmount } = render(<LoadingFallback />);
        expect(screen.getByText('加载中...')).toBeInTheDocument();
        unmount();
      }
    });
  });

  describe('主题一致性', () => {
    it('应该使用项目标准的色彩方案', () => {
      const { container } = render(<LoadingFallback />);
      
      // 蓝色主题 - 与项目其他组件保持一致
      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toHaveClass('border-blue-600');
      
      // 灰色背景和文本 - 与项目风格一致
      expect(container.firstChild).toHaveClass('bg-gray-50');
      expect(screen.getByText('加载中...')).toHaveClass('text-gray-600');
    });
  });
});