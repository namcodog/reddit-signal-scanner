/**
 * ResponsiveLayout组件单元测试
 * 测试响应式布局的设备适配、间距管理和触摸优化功能
 * 遵循100%类型安全和质量门禁要求
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { useDeviceDetection } from '@/hooks/useDeviceDetection';
import type { DeviceInfo } from '@/types/responsive.types';
import ResponsiveLayout from '@/components/ResponsiveLayout';

interface TestChildProps {
  children: React.ReactNode;
}

// Mock useDeviceDetection hook - 使用真实的DeviceInfo接口
vi.mock('@/hooks/useDeviceDetection', () => ({
  useDeviceDetection: vi.fn<[], DeviceInfo>(),
}));

// 测试子组件 - 明确类型定义
const TestChild: React.FC<TestChildProps> = ({ children }) => (
  <div data-testid="test-child">{children}</div>
);

describe('ResponsiveLayout', () => {
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
    it('应该正确渲染子组件', () => {
      render(
        <ResponsiveLayout>
          <TestChild>测试内容</TestChild>
        </ResponsiveLayout>
      );

      expect(screen.getByTestId('test-child')).toBeInTheDocument();
      expect(screen.getByText('测试内容')).toBeInTheDocument();
    });

    it('应该应用自定义className', () => {
      const customClass = 'custom-layout-class';
      const { container } = render(
        <ResponsiveLayout className={customClass}>
          <TestChild>内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveClass(customClass);
    });

    it('应该支持ref引用', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(
        <ResponsiveLayout ref={ref}>
          <TestChild>内容</TestChild>
        </ResponsiveLayout>
      );

      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  describe('设备类型适配', () => {
    it('应该为移动设备应用正确的间距类', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'mobile',
      });

      const { container } = render(
        <ResponsiveLayout variant="comfortable">
          <TestChild>移动端内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveClass('px-4', 'py-3');
    });

    it('应该为平板设备应用正确的间距类', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'tablet',
      });

      const { container } = render(
        <ResponsiveLayout variant="comfortable">
          <TestChild>平板端内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveClass('px-6', 'py-4');
    });

    it('应该为桌面设备应用正确的间距类', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'desktop',
      });

      const { container } = render(
        <ResponsiveLayout variant="comfortable">
          <TestChild>桌面端内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveClass('px-8', 'py-6');
    });
  });

  describe('变体间距管理', () => {
    it('应该为compact变体应用紧凑间距', () => {
      const { container } = render(
        <ResponsiveLayout variant="compact">
          <TestChild>紧凑内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      // 桌面端compact间距
      expect(layoutElement).toHaveClass('px-6', 'py-4');
    });

    it('应该为spacious变体应用宽松间距', () => {
      const { container } = render(
        <ResponsiveLayout variant="spacious">
          <TestChild>宽松内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      // 桌面端spacious间距
      expect(layoutElement).toHaveClass('px-12', 'py-8');
    });

    it('应该默认使用comfortable变体', () => {
      const { container } = render(
        <ResponsiveLayout>
          <TestChild>默认内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      // 桌面端comfortable间距
      expect(layoutElement).toHaveClass('px-8', 'py-6');
    });
  });

  describe('触摸设备优化', () => {
    it('应该为触摸设备添加触摸优化类', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        isTouchDevice: true,
      });

      const { container } = render(
        <ResponsiveLayout>
          <TestChild>触摸设备内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveClass('touch-manipulation', 'select-none');
    });

    it('应该为无hover设备添加no-hover类', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        hasHover: false,
      });

      const { container } = render(
        <ResponsiveLayout>
          <TestChild>无hover设备内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveClass('no-hover');
    });

    it('应该为偏好减少动画的用户添加reduce-motion类', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        prefersReducedMotion: true,
      });

      const { container } = render(
        <ResponsiveLayout>
          <TestChild>减少动画内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveClass('reduce-motion');
    });
  });

  describe('安全区域支持', () => {
    it('应该为移动设备添加安全区域类', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'mobile',
      });

      const { container } = render(
        <ResponsiveLayout enableSafeArea={true}>
          <TestChild>移动端安全区域内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveClass('safe-area-inset');
    });

    it('应该在非移动设备上不添加安全区域类', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'desktop',
      });

      const { container } = render(
        <ResponsiveLayout enableSafeArea={true}>
          <TestChild>桌面端内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).not.toHaveClass('safe-area-inset');
    });

    it('应该支持禁用安全区域', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'mobile',
      });

      const { container } = render(
        <ResponsiveLayout enableSafeArea={false}>
          <TestChild>禁用安全区域内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).not.toHaveClass('safe-area-inset');
    });
  });

  describe('间距控制', () => {
    it('应该支持禁用间距', () => {
      const { container } = render(
        <ResponsiveLayout enablePadding={false}>
          <TestChild>无间距内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      // 检查不包含任何padding类
      expect(layoutElement.className).not.toMatch(/px-\d+/);
      expect(layoutElement.className).not.toMatch(/py-\d+/);
    });

    it('应该默认启用间距', () => {
      const { container } = render(
        <ResponsiveLayout>
          <TestChild>默认间距内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      // 检查包含padding类
      expect(layoutElement.className).toMatch(/px-\d+/);
      expect(layoutElement.className).toMatch(/py-\d+/);
    });
  });

  describe('动画偏好处理', () => {
    it('应该为偏好减少动画的用户设置willChange为auto', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        prefersReducedMotion: true,
      });

      const { container } = render(
        <ResponsiveLayout>
          <TestChild>减少动画内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveStyle({ willChange: 'auto' });
    });

    it('应该为正常用户设置willChange为transform', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        prefersReducedMotion: false,
      });

      const { container } = render(
        <ResponsiveLayout>
          <TestChild>正常动画内容</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      expect(layoutElement).toHaveStyle({ willChange: 'transform' });
    });
  });

  describe('组合场景测试', () => {
    it('应该在移动触摸设备上正确组合所有特性', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'mobile',
        isTouchDevice: true,
        hasHover: false,
        prefersReducedMotion: false,
      });

      const { container } = render(
        <ResponsiveLayout variant="compact" enableSafeArea={true} className="custom-class">
          <TestChild>移动端组合特性测试</TestChild>
        </ResponsiveLayout>
      );

      const layoutElement = container.firstChild as HTMLElement;
      
      // 检查间距类
      expect(layoutElement).toHaveClass('px-3', 'py-2');
      
      // 检查触摸优化类
      expect(layoutElement).toHaveClass('touch-manipulation', 'select-none', 'no-hover');
      
      // 检查安全区域类
      expect(layoutElement).toHaveClass('safe-area-inset');
      
      // 检查自定义类
      expect(layoutElement).toHaveClass('custom-class');
      
      // 检查过渡动画类
      expect(layoutElement).toHaveClass('transition-all', 'duration-200');
      
      // 检查willChange样式
      expect(layoutElement).toHaveStyle({ willChange: 'transform' });
    });
  });
});