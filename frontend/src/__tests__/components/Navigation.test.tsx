/**
 * Navigation组件单元测试
 * 测试响应式导航、设备适配和导航状态管理
 * 遵循100%类型安全和质量门禁要求
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import Navigation from '@/components/Navigation';
import { NavigationStep } from '@/types/router.types';

// Mock Heroicons
vi.mock('@heroicons/react/24/outline', () => ({
  ChevronRightIcon: ({ className }: { className?: string }) => (
    <div data-testid="chevron-right-icon" className={className}>→</div>
  ),
  DocumentTextIcon: ({ className }: { className?: string }) => (
    <div data-testid="document-text-icon" className={className}>📄</div>
  ),
  ChartBarIcon: ({ className }: { className?: string }) => (
    <div data-testid="chart-bar-icon" className={className}>📊</div>
  ),
  LightBulbIcon: ({ className }: { className?: string }) => (
    <div data-testid="light-bulb-icon" className={className}>💡</div>
  ),
}));

// Mock hooks using vi.hoisted() to solve hoisting issues
const mocks = vi.hoisted(() => {
  return {
    navigateTo: vi.fn(),
    canNavigateTo: vi.fn(),
    useNavigation: vi.fn(() => ({
      currentStep: 'input' as NavigationStep,
      canNavigateTo: vi.fn(),
      navigateTo: vi.fn(),
    })),
    useDeviceDetection: vi.fn(() => ({
      type: 'desktop' as DeviceType,
      width: 1024,
      height: 768,
      isTouchDevice: false,
      isPortrait: false,
      pixelRatio: 1,
      hasHover: true,
      prefersReducedMotion: false,
    })),
  };
});

vi.mock('@/hooks/useNavigation', () => ({
  useNavigation: mocks.useNavigation,
}));

vi.mock('@/hooks/useDeviceDetection', () => ({
  useDeviceDetection: mocks.useDeviceDetection,
}));

// 设备类型定义
type DeviceType = 'mobile' | 'tablet' | 'desktop';

// 测试助手函数
const setupNavigationTest = (
  currentStep: NavigationStep = 'input',
  deviceType: DeviceType = 'desktop',
  isTouchDevice: boolean = false,
  canNavigateToResults: Record<NavigationStep, boolean> = {
    input: true,
    analysis: false,
    report: false,
  }
) => {
  mocks.useNavigation.mockReturnValue({
    currentStep,
    canNavigateTo: mocks.canNavigateTo.mockImplementation((step: NavigationStep) => 
      canNavigateToResults[step]
    ),
    navigateTo: mocks.navigateTo,
  });

  mocks.useDeviceDetection.mockReturnValue({
    type: deviceType,
    width: deviceType === 'mobile' ? 375 : deviceType === 'tablet' ? 768 : 1024,
    height: deviceType === 'mobile' ? 667 : deviceType === 'tablet' ? 1024 : 768,
    isTouchDevice,
    isPortrait: deviceType === 'mobile',
    pixelRatio: 1,
    hasHover: !isTouchDevice,
    prefersReducedMotion: false,
  });

  mocks.canNavigateTo.mockImplementation((step: NavigationStep) => 
    canNavigateToResults[step]
  );
};

describe('Navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupNavigationTest();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('基础渲染', () => {
    it('应该渲染所有导航步骤', () => {
      setupNavigationTest();
      render(<Navigation />);

      expect(screen.getByText('产品输入')).toBeInTheDocument();
      expect(screen.getByText('信号分析')).toBeInTheDocument();
      expect(screen.getByText('商业洞察')).toBeInTheDocument();
    });

    it('应该渲染步骤图标', () => {
      setupNavigationTest();
      render(<Navigation />);

      expect(screen.getByTestId('document-text-icon')).toBeInTheDocument();
      expect(screen.getByTestId('chart-bar-icon')).toBeInTheDocument();
      expect(screen.getByTestId('light-bulb-icon')).toBeInTheDocument();
    });

    it('应该在桌面端显示步骤描述', () => {
      setupNavigationTest('input', 'desktop');
      render(<Navigation />);

      expect(screen.getByText('描述您的产品')).toBeInTheDocument();
      expect(screen.getByText('处理洞察信息')).toBeInTheDocument();
      expect(screen.getByText('查看结果')).toBeInTheDocument();
    });

    it('应该渲染导航容器和基本结构', () => {
      setupNavigationTest();
      const { container } = render(<Navigation />);

      const nav = container.querySelector('nav');
      expect(nav).toBeInTheDocument();
      expect(nav).toHaveClass('bg-white', 'border-b', 'border-gray-200');
    });
  });

  describe('响应式设计', () => {
    describe('移动端布局', () => {
      it('应该在移动端使用紧凑布局', () => {
        setupNavigationTest('input', 'mobile');
        const { container } = render(<Navigation />);

        const stepContainer = container.querySelector('.space-x-1');
        expect(stepContainer).toBeInTheDocument();
      });

      it('应该在移动端隐藏分隔符', () => {
        setupNavigationTest('input', 'mobile');
        render(<Navigation />);

        expect(screen.queryByTestId('chevron-right-icon')).not.toBeInTheDocument();
      });

      it('应该在移动端隐藏步骤描述', () => {
        setupNavigationTest('input', 'mobile');
        render(<Navigation />);

        expect(screen.queryByText('描述您的产品')).not.toBeInTheDocument();
        expect(screen.queryByText('处理洞察信息')).not.toBeInTheDocument();
        expect(screen.queryByText('查看结果')).not.toBeInTheDocument();
      });

      it('应该在移动端使用列布局的按钮', () => {
        setupNavigationTest('input', 'mobile');
        const { container } = render(<Navigation />);

        const buttons = container.querySelectorAll('button');
        buttons.forEach(button => {
          expect(button).toHaveClass('flex-col', 'space-y-1');
        });
      });

      it('应该在移动端显示简化标题', () => {
        setupNavigationTest('input', 'mobile');
        render(<Navigation />);

        // 在移动端，步骤标题仍然显示，但位置和样式不同
        expect(screen.getByText('产品输入')).toBeInTheDocument();
        expect(screen.getByText('信号分析')).toBeInTheDocument();
        expect(screen.getByText('商业洞察')).toBeInTheDocument();
      });
    });

    describe('平板端布局', () => {
      it('应该在平板端隐藏步骤描述但显示标题', () => {
        setupNavigationTest('input', 'tablet');
        render(<Navigation />);

        expect(screen.getByText('产品输入')).toBeInTheDocument();
        expect(screen.queryByText('描述您的产品')).not.toBeInTheDocument();
      });

      it('应该在平板端显示分隔符', () => {
        setupNavigationTest('input', 'tablet');
        render(<Navigation />);

        expect(screen.getAllByTestId('chevron-right-icon')).toHaveLength(2);
      });

      it('应该在平板端使用中等间距', () => {
        setupNavigationTest('input', 'tablet');
        const { container } = render(<Navigation />);

        const buttons = container.querySelectorAll('button');
        buttons.forEach(button => {
          expect(button).toHaveClass('px-3', 'py-2', 'space-x-2');
        });
      });
    });

    describe('桌面端布局', () => {
      it('应该在桌面端显示完整的步骤信息', () => {
        setupNavigationTest('input', 'desktop');
        render(<Navigation />);

        expect(screen.getByText('产品输入')).toBeInTheDocument();
        expect(screen.getByText('描述您的产品')).toBeInTheDocument();
      });

      it('应该在桌面端使用较大的间距', () => {
        setupNavigationTest('input', 'desktop');
        const { container } = render(<Navigation />);

        const buttons = container.querySelectorAll('button');
        buttons.forEach(button => {
          expect(button).toHaveClass('px-4', 'py-2', 'space-x-2');
        });
      });
    });
  });

  describe('导航状态显示', () => {
    it('应该正确显示当前活动步骤', () => {
      setupNavigationTest('analysis', 'desktop');
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      const analysisButton = buttons.find(button => 
        button.textContent?.includes('信号分析')
      );

      expect(analysisButton).toHaveClass(
        'bg-blue-50',
        'text-blue-700',
        'border-2',
        'border-blue-200'
      );
    });

    it('应该正确显示已完成的步骤', () => {
      setupNavigationTest('report', 'desktop', false, {
        input: true,
        analysis: true,
        report: true,
      });
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      const inputButton = buttons.find(button => 
        button.textContent?.includes('产品输入')
      );

      expect(inputButton).toHaveClass(
        'text-gray-700',
        'hover:bg-gray-50',
        'cursor-pointer'
      );
    });

    it('应该正确显示禁用的步骤', () => {
      setupNavigationTest('input', 'desktop');
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      const analysisButton = buttons.find(button => 
        button.textContent?.includes('信号分析')
      );

      expect(analysisButton).toHaveClass(
        'text-gray-400',
        'cursor-not-allowed'
      );
      expect(analysisButton).toBeDisabled();
    });

    it('应该给活动步骤的图标添加特殊样式', () => {
      setupNavigationTest('analysis', 'desktop');
      const { container } = render(<Navigation />);

      const analysisButton = Array.from(container.querySelectorAll('button')).find(button => 
        button.textContent?.includes('信号分析')
      );

      const icon = analysisButton?.querySelector('[data-testid="chart-bar-icon"]');
      expect(icon).toHaveClass('text-blue-700');
    });
  });

  describe('触摸设备优化', () => {
    it('应该在触摸设备上添加触摸反馈', () => {
      setupNavigationTest('input', 'mobile', true, {
        input: true,
        analysis: true,
        report: false,
      });
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        if (!(button as HTMLButtonElement).disabled) {
          expect(button).toHaveClass('active:scale-95');
        }
      });
    });

    it('应该在非触摸设备上不添加触摸反馈', () => {
      setupNavigationTest('input', 'desktop', false);
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).not.toHaveClass('active:scale-95');
      });
    });
  });

  describe('用户交互', () => {
    it('应该在点击可导航步骤时调用navigateTo', () => {
      setupNavigationTest('analysis', 'desktop', false, {
        input: true,
        analysis: true,
        report: false,
      });
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      const inputButton = buttons.find(button => 
        button.textContent?.includes('产品输入')
      );

      fireEvent.click(inputButton!);
      expect(mocks.navigateTo).toHaveBeenCalledWith('input');
    });

    it('应该在点击不可导航步骤时不调用navigateTo', () => {
      setupNavigationTest('input', 'desktop');
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      const analysisButton = buttons.find(button => 
        button.textContent?.includes('信号分析')
      );

      fireEvent.click(analysisButton!);
      expect(mocks.navigateTo).not.toHaveBeenCalled();
    });

    it('应该在点击当前步骤时调用navigateTo（刷新效果）', () => {
      setupNavigationTest('input', 'desktop');
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      const inputButton = buttons.find(button => 
        button.textContent?.includes('产品输入')
      );

      fireEvent.click(inputButton!);
      expect(mocks.navigateTo).toHaveBeenCalledWith('input');
    });
  });

  describe('可访问性', () => {
    it('所有可点击的步骤应该有正确的focus样式', () => {
      setupNavigationTest('report', 'desktop', false, {
        input: true,
        analysis: true,
        report: true,
      });
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        if (!(button as HTMLButtonElement).disabled) {
          expect(button).toHaveClass(
            'focus-visible:outline-none',
            'focus-visible:ring-2',
            'focus-visible:ring-blue-500'
          );
        }
      });
    });

    it('禁用的步骤不应该有focus样式', () => {
      setupNavigationTest('input', 'desktop');
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      const disabledButtons = buttons.filter(button => (button as HTMLButtonElement).disabled);
      
      disabledButtons.forEach(button => {
        expect(button).not.toHaveClass('focus-visible:ring-2');
      });
    });

    it('应该使用语义化的导航元素', () => {
      setupNavigationTest();
      const { container } = render(<Navigation />);

      const nav = container.querySelector('nav');
      expect(nav).toBeInTheDocument();
    });
  });

  describe('Hook集成', () => {
    it('应该正确调用useNavigation hook', () => {
      render(<Navigation />);
      expect(mocks.useNavigation).toHaveBeenCalled();
    });

    it('应该正确调用useDeviceDetection hook', () => {
      render(<Navigation />);
      expect(mocks.useDeviceDetection).toHaveBeenCalled();
    });

    it('应该根据canNavigateTo结果正确设置按钮状态', () => {
      setupNavigationTest('analysis', 'desktop', false, {
        input: true,
        analysis: true,
        report: false,
      });
      render(<Navigation />);

      expect(mocks.canNavigateTo).toHaveBeenCalledWith('input');
      expect(mocks.canNavigateTo).toHaveBeenCalledWith('analysis');
      expect(mocks.canNavigateTo).toHaveBeenCalledWith('report');
    });
  });

  describe('图标渲染', () => {
    it('应该为每个步骤渲染正确的图标', () => {
      setupNavigationTest();
      render(<Navigation />);

      expect(screen.getByTestId('document-text-icon')).toBeInTheDocument();
      expect(screen.getByTestId('chart-bar-icon')).toBeInTheDocument();
      expect(screen.getByTestId('light-bulb-icon')).toBeInTheDocument();
    });

    it('应该根据设备类型调整图标大小', () => {
      setupNavigationTest('input', 'mobile');
      const { container } = render(<Navigation />);

      const icons = container.querySelectorAll('[data-testid*="-icon"]');
      icons.forEach(icon => {
        expect(icon).toHaveClass('w-5', 'h-5');
      });
    });

    it('应该在桌面端使用较小的图标', () => {
      setupNavigationTest('input', 'desktop');
      const { container } = render(<Navigation />);

      const icons = container.querySelectorAll('[data-testid*="-icon"]');
      icons.forEach(icon => {
        expect(icon).toHaveClass('w-4', 'h-4');
      });
    });
  });

  describe('边界情况', () => {
    it('应该处理所有步骤都禁用的情况', () => {
      setupNavigationTest('input', 'desktop', false, {
        input: false,
        analysis: false,
        report: false,
      });
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach((button, index) => {
        if (index === 0) {
          // 当前步骤(input)应该显示为active状态，而不是disabled
          expect(button).toHaveClass('bg-blue-50', 'text-blue-700');
          expect(button).toBeDisabled(); // 但仍然是disabled的
        } else {
          // 其他步骤应该是disabled状态
          expect(button).toBeDisabled();
          expect(button).toHaveClass('cursor-not-allowed');
        }
      });
    });

    it('应该处理所有步骤都可用的情况', () => {
      setupNavigationTest('report', 'desktop', false, {
        input: true,
        analysis: true,
        report: true,
      });
      render(<Navigation />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).not.toBeDisabled();
      });
    });

    it('应该处理未知设备类型', () => {
      // 使用类型断言来测试边界情况
      mocks.useDeviceDetection.mockReturnValue({
        type: 'unknown' as any,
        width: 1024,
        height: 768,
        isTouchDevice: false,
        isPortrait: false,
        pixelRatio: 1,
        hasHover: true,
        prefersReducedMotion: false,
      });

      expect(() => render(<Navigation />)).not.toThrow();
    });
  });

  describe('性能考虑', () => {
    it('应该为步骤渲染使用React.Fragment以避免不必要的DOM节点', () => {
      const { container } = render(<Navigation />);
      
      // 检查分隔符只在需要时渲染
      const separators = container.querySelectorAll('[data-testid="chevron-right-icon"]');
      expect(separators.length).toBe(2); // 3个步骤之间应该有2个分隔符
    });
  });

  describe('样式一致性', () => {
    it('应该在所有设备类型上使用一致的颜色方案', () => {
      const testCases: Array<'mobile' | 'tablet' | 'desktop'> = ['mobile', 'tablet', 'desktop'];

      testCases.forEach(deviceType => {
        setupNavigationTest('input', deviceType);
        const { container } = render(<Navigation />);
        
        const nav = container.querySelector('nav');
        expect(nav).toHaveClass('bg-white', 'border-b', 'border-gray-200');
      });
    });
  });
});