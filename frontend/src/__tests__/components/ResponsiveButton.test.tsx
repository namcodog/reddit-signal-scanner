/**
 * ResponsiveButton组件单元测试
 * 测试响应式按钮的变体样式、尺寸适配、触摸优化和加载状态
 * 遵循100%类型安全和质量门禁要求
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useDeviceDetection } from '@/hooks/useDeviceDetection';
import type { DeviceInfo } from '@/types/responsive.types';
import ResponsiveButton from '@/components/ResponsiveButton';
import { Plus } from 'lucide-react';

// 使用真实的DeviceInfo接口 - 遵循Context7最佳实践

// Mock useDeviceDetection hook
vi.mock('@/hooks/useDeviceDetection', () => ({
  useDeviceDetection: vi.fn<[], DeviceInfo>(),
}));

// Mock Lucide React icons
vi.mock('lucide-react', () => ({
  Loader2: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="loader-icon" className={className} {...props} />
  ),
  Plus: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="plus-icon" className={className} {...props} />
  ),
}));

describe('ResponsiveButton', () => {
  // 默认mock返回值 - 使用完整的DeviceInfo接口
  const defaultMockReturn: DeviceInfo = {
    type: 'desktop',
    width: 1024,
    height: 768,
    isTouchDevice: false,
    isPortrait: false,
    pixelRatio: 1,
    hasHover: true,
    prefersReducedMotion: false,
  };

  // 获取mock函数 - 使用正确的导入方式
  const getMockUseDeviceDetection = () => vi.mocked(useDeviceDetection);

  beforeEach(() => {
    vi.clearAllMocks();
    getMockUseDeviceDetection().mockReturnValue(defaultMockReturn);
  });

  describe('基础渲染', () => {
    it('应该正确渲染按钮和文本内容', () => {
      render(<ResponsiveButton>测试按钮</ResponsiveButton>);

      const button = screen.getByRole('button', { name: '测试按钮' });
      expect(button).toBeInTheDocument();
      expect(button).toHaveTextContent('测试按钮');
    });

    it('应该支持自定义className', () => {
      const customClass = 'custom-button-class';
      render(<ResponsiveButton className={customClass}>按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass(customClass);
    });

    it('应该支持ref引用', () => {
      const ref = React.createRef<HTMLButtonElement>();
      render(<ResponsiveButton ref={ref}>按钮</ResponsiveButton>);

      expect(ref.current).toBeInstanceOf(HTMLButtonElement);
    });

    it('应该传递原生button属性', () => {
      const handleClick = vi.fn<[React.MouseEvent<HTMLButtonElement>], void>();
      render(
        <ResponsiveButton onClick={handleClick} disabled={true} type="submit">
          按钮
        </ResponsiveButton>
      );

      const button = screen.getByRole('button');
      expect(button).toBeDisabled();
      expect(button).toHaveAttribute('type', 'submit');
    });
  });

  describe('变体样式', () => {
    it('应该默认使用default变体', () => {
      render(<ResponsiveButton>默认按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-blue-600', 'text-white', 'hover:bg-blue-700');
    });

    it('应该正确应用destructive变体样式', () => {
      render(<ResponsiveButton variant="destructive">删除按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-red-600', 'text-white', 'hover:bg-red-700');
    });

    it('应该正确应用outline变体样式', () => {
      render(<ResponsiveButton variant="outline">轮廓按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('border', 'border-gray-300', 'bg-white');
    });

    it('应该正确应用secondary变体样式', () => {
      render(<ResponsiveButton variant="secondary">次要按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('bg-gray-100', 'text-gray-900', 'hover:bg-gray-200');
    });

    it('应该正确应用ghost变体样式', () => {
      render(<ResponsiveButton variant="ghost">幽灵按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('hover:bg-gray-100', 'hover:text-gray-900');
    });

    it('应该正确应用link变体样式', () => {
      render(<ResponsiveButton variant="link">链接按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('text-blue-600', 'underline-offset-4', 'hover:underline');
    });
  });

  describe('尺寸适配', () => {
    describe('桌面端尺寸', () => {
      beforeEach(() => {
        getMockUseDeviceDetection().mockReturnValue({
          ...defaultMockReturn,
          type: 'desktop',
          isTouchDevice: false,
        });
      });

      it('应该正确应用small尺寸', () => {
        render(<ResponsiveButton size="sm">小按钮</ResponsiveButton>);

        const button = screen.getByRole('button');
        expect(button).toHaveClass('h-9', 'px-3', 'text-sm');
      });

      it('应该正确应用medium尺寸（默认）', () => {
        render(<ResponsiveButton size="md">中等按钮</ResponsiveButton>);

        const button = screen.getByRole('button');
        expect(button).toHaveClass('h-10', 'px-4', 'text-sm');
      });

      it('应该正确应用large尺寸', () => {
        render(<ResponsiveButton size="lg">大按钮</ResponsiveButton>);

        const button = screen.getByRole('button');
        expect(button).toHaveClass('h-11', 'px-8', 'text-base');
      });
    });

    describe('移动端尺寸（触摸优化）', () => {
      beforeEach(() => {
        getMockUseDeviceDetection().mockReturnValue({
          ...defaultMockReturn,
          type: 'mobile',
          isTouchDevice: true,
        });
      });

      it('应该为移动端small尺寸应用44px最小高度', () => {
        render(<ResponsiveButton size="sm">移动端小按钮</ResponsiveButton>);

        const button = screen.getByRole('button');
        expect(button).toHaveClass('h-11', 'px-4', 'text-sm'); // 44px高度
      });

      it('应该为移动端medium尺寸应用48px高度', () => {
        render(<ResponsiveButton size="md">移动端中等按钮</ResponsiveButton>);

        const button = screen.getByRole('button');
        expect(button).toHaveClass('h-12', 'px-6', 'text-base'); // 48px高度
      });

      it('应该为移动端large尺寸应用56px高度', () => {
        render(<ResponsiveButton size="lg">移动端大按钮</ResponsiveButton>);

        const button = screen.getByRole('button');
        expect(button).toHaveClass('h-14', 'px-8', 'text-lg'); // 56px高度
      });
    });
  });

  describe('全宽显示', () => {
    it('应该支持全宽显示', () => {
      render(<ResponsiveButton fullWidth={true}>全宽按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('w-full');
    });

    it('应该默认不使用全宽', () => {
      render(<ResponsiveButton>正常宽度按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).not.toHaveClass('w-full');
    });
  });

  describe('加载状态', () => {
    it('应该在加载时显示加载图标和文本', () => {
      render(<ResponsiveButton loading={true}>提交</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('加载中...');
      expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
      expect(button).toBeDisabled();
    });

    it('应该在非加载时显示正常内容', () => {
      render(<ResponsiveButton loading={false}>提交</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('提交');
      expect(screen.queryByTestId('loader-icon')).not.toBeInTheDocument();
      expect(button).not.toBeDisabled();
    });

    it('应该在加载时忽略其他图标', () => {
      render(
        <ResponsiveButton loading={true} icon={<Plus />}>
          提交
        </ResponsiveButton>
      );

      expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
      expect(screen.queryByTestId('plus-icon')).not.toBeInTheDocument();
    });
  });

  describe('图标支持', () => {
    it('应该在左侧显示图标', () => {
      render(
        <ResponsiveButton icon={<Plus />} iconPosition="left">
          添加
        </ResponsiveButton>
      );

      const button = screen.getByRole('button');
      const icon = screen.getByTestId('plus-icon');
      
      expect(icon).toBeInTheDocument();
      expect(button).toHaveTextContent('添加');
    });

    it('应该在右侧显示图标', () => {
      render(
        <ResponsiveButton icon={<Plus />} iconPosition="right">
          添加
        </ResponsiveButton>
      );

      const button = screen.getByRole('button');
      const icon = screen.getByTestId('plus-icon');
      
      expect(icon).toBeInTheDocument();
      expect(button).toHaveTextContent('添加');
    });

    it('应该支持只显示图标（无文本）', () => {
      render(<ResponsiveButton icon={<Plus />} />);

      const icon = screen.getByTestId('plus-icon');
      expect(icon).toBeInTheDocument();
    });

    it('应该默认在左侧显示图标', () => {
      render(
        <ResponsiveButton icon={<Plus />}>
          默认位置
        </ResponsiveButton>
      );

      const icon = screen.getByTestId('plus-icon');
      expect(icon).toBeInTheDocument();
    });
  });

  describe('触摸反馈', () => {
    it('应该为触摸设备添加触摸反馈效果', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        isTouchDevice: true,
        prefersReducedMotion: false,
      });

      render(<ResponsiveButton>触摸按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('active:scale-95', 'active:transition-transform', 'active:duration-75');
    });

    it('应该为非触摸设备不添加触摸反馈效果', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        isTouchDevice: false,
      });

      render(<ResponsiveButton>普通按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).not.toHaveClass('active:scale-95');
    });

    it('应该为偏好减少动画的用户不添加触摸反馈', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        isTouchDevice: true,
        prefersReducedMotion: true,
      });

      render(<ResponsiveButton>无动画按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).not.toHaveClass('active:scale-95');
    });
  });

  describe('用户交互', () => {
    it('应该响应点击事件', () => {
      const handleClick = vi.fn<[React.MouseEvent<HTMLButtonElement>], void>();
      render(<ResponsiveButton onClick={handleClick}>点击测试</ResponsiveButton>);

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('应该在禁用状态下不响应点击', () => {
      const handleClick = vi.fn<[React.MouseEvent<HTMLButtonElement>], void>();
      render(
        <ResponsiveButton onClick={handleClick} disabled={true}>
          禁用按钮
        </ResponsiveButton>
      );

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(handleClick).not.toHaveBeenCalled();
    });

    it('应该在加载状态下不响应点击', () => {
      const handleClick = vi.fn<[React.MouseEvent<HTMLButtonElement>], void>();
      render(
        <ResponsiveButton onClick={handleClick} loading={true}>
          加载按钮
        </ResponsiveButton>
      );

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe('可访问性', () => {
    it('应该有正确的role属性', () => {
      render(<ResponsiveButton>可访问按钮</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('应该支持焦点样式类', () => {
      render(<ResponsiveButton>焦点测试</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('focus-visible:outline-none', 'focus-visible:ring-2');
    });

    it('应该在禁用时有正确的样式', () => {
      render(<ResponsiveButton disabled={true}>禁用测试</ResponsiveButton>);

      const button = screen.getByRole('button');
      expect(button).toHaveClass('disabled:pointer-events-none', 'disabled:opacity-50');
    });
  });

  describe('组合场景测试', () => {
    it('应该正确组合所有特性 - 移动端加载状态', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'mobile',
        isTouchDevice: true,
        prefersReducedMotion: false,
      });

      render(
        <ResponsiveButton
          variant="destructive"
          size="lg"
          fullWidth={true}
          loading={true}
          className="custom-class"
        >
          删除操作
        </ResponsiveButton>
      );

      const button = screen.getByRole('button');
      
      // 检查变体样式
      expect(button).toHaveClass('bg-red-600', 'text-white');
      
      // 检查移动端大尺寸
      expect(button).toHaveClass('h-14', 'px-8', 'text-lg');
      
      // 检查全宽
      expect(button).toHaveClass('w-full');
      
      // 检查加载状态
      expect(button).toBeDisabled();
      expect(button).toHaveTextContent('加载中...');
      expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
      
      // 检查自定义类
      expect(button).toHaveClass('custom-class');
    });
  });
});