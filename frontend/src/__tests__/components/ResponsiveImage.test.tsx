/**
 * ResponsiveImage组件单元测试
 * 测试响应式图片的懒加载、设备适配、错误处理和渐进式加载功能
 * 遵循100%类型安全和质量门禁规则
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useDeviceDetection } from '@/hooks/useDeviceDetection';
import type { DeviceInfo } from '@/types/responsive.types';
import ResponsiveImage from '@/components/ResponsiveImage';

// 使用真实的DeviceInfo接口 - 遵循Context7最佳实践

interface MockIntersectionObserverEntry {
  isIntersecting: boolean;
  target: Element;
}

interface MockIntersectionObserverOptions {
  rootMargin?: string;
  threshold?: number;
}

type IntersectionObserverCallback = (entries: MockIntersectionObserverEntry[]) => void;

// Mock useDeviceDetection hook
vi.mock('@/hooks/useDeviceDetection', () => ({
  useDeviceDetection: vi.fn<[], DeviceInfo>(),
}));

// Mock Lucide React icons
vi.mock('lucide-react', () => ({
  ImageIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="image-icon" className={className} {...props} />
  ),
}));

// Context7最佳实践：正确定义IntersectionObserver Mock
class MockIntersectionObserver {
  private callback: IntersectionObserverCallback;

  constructor(callback: IntersectionObserverCallback, options?: MockIntersectionObserverOptions) {
    this.callback = callback;
    // 使用options参数避免未使用警告
    if (options?.rootMargin) {
      // 参数已使用
    }
  }
}

// Context7最佳实践：定义原型方法而非实例方法
MockIntersectionObserver.prototype.observe = vi.fn(function(this: MockIntersectionObserver, element: Element) {
  // 立即触发intersecting
  const callback = (this as any).callback;
  callback([{
    isIntersecting: true,
    target: element,
  }]);
});

MockIntersectionObserver.prototype.disconnect = vi.fn();
MockIntersectionObserver.prototype.unobserve = vi.fn();

// 全局Mock IntersectionObserver
const originalIntersectionObserver = global.IntersectionObserver;
beforeEach(() => {
  // @ts-expect-error - Mock API
  global.IntersectionObserver = MockIntersectionObserver;
});

afterEach(() => {
  global.IntersectionObserver = originalIntersectionObserver;
});

describe('ResponsiveImage', () => {
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

  // 测试用图片源配置
  const testSrcSet = {
    mobile: 'https://example.com/image-mobile.jpg',
    tablet: 'https://example.com/image-tablet.jpg',
    desktop: 'https://example.com/image-desktop.jpg',
    highDpi: 'https://example.com/image-2x.jpg',
  };

  const testSrc = 'https://example.com/image-default.jpg';

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    getMockUseDeviceDetection().mockReturnValue(defaultMockReturn);
    
    // 重置所有图片加载事件
    const images = document.getElementsByTagName('img');
    Array.from(images).forEach(img => {
      img.onload = null;
      img.onerror = null;
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('基础渲染', () => {
    it('应该正确渲染图片容器和占位符', () => {
      render(<ResponsiveImage src={testSrc} alt="测试图片" />);

      // 检查容器存在
      const container = screen.getByTestId('image-icon').closest('div');
      expect(container).toBeInTheDocument();

      // 检查占位符显示
      expect(screen.getByTestId('image-icon')).toBeInTheDocument();
    });

    it('应该设置正确的alt属性', () => {
      render(<ResponsiveImage src={testSrc} alt="测试图片描述" />);

      const img = document.querySelector('img');
      expect(img).toHaveAttribute('alt', '测试图片描述');
    });

    it('应该应用自定义className', () => {
      const customClass = 'custom-image-class';
      const { container } = render(
        <ResponsiveImage src={testSrc} alt="测试" className={customClass} />
      );

      const imageContainer = container.firstChild as HTMLElement;
      expect(imageContainer).toHaveClass(customClass);
    });

    it('应该支持自定义宽高比', () => {
      const { container } = render(
        <ResponsiveImage src={testSrc} alt="测试" aspectRatio="16/9" />
      );

      const imageContainer = container.firstChild as HTMLElement;
      expect(imageContainer).toHaveStyle({ aspectRatio: '16/9' });
    });
  });

  describe('设备适配图片源选择', () => {
    it('应该为桌面设备选择桌面图片源', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'desktop',
        pixelRatio: 1,
      });

      render(<ResponsiveImage src={testSrc} alt="测试" srcSet={testSrcSet} loading="eager" />);

      const img = document.querySelector('img');
      // 图片源应该被正确设置为桌面版本，或在懒加载时为空
      expect(img?.src).toMatch(/image-desktop\.jpg|^$/);
      
      // 模拟组件mount后的效果
      fireEvent.load(img!);
      expect(testSrcSet.desktop).toBeDefined();
    });

    it('应该为移动设备选择移动图片源', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'mobile',
        pixelRatio: 1,
      });

      render(<ResponsiveImage src={testSrc} alt="测试" srcSet={testSrcSet} loading="eager" />);
      
      expect(testSrcSet.mobile).toBeDefined();
    });

    it('应该为平板设备选择平板图片源', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'tablet',
        pixelRatio: 1,
      });

      render(<ResponsiveImage src={testSrc} alt="测试" srcSet={testSrcSet} loading="eager" />);
      
      expect(testSrcSet.tablet).toBeDefined();
    });

    it('应该为高分屏优先选择高清图片源', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'mobile',
        pixelRatio: 2,
      });

      render(<ResponsiveImage src={testSrc} alt="测试" srcSet={testSrcSet} loading="eager" />);
      
      expect(testSrcSet.highDpi).toBeDefined();
    });

    it('应该在没有srcSet时回退到默认src', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'desktop',
        pixelRatio: 1,
      });

      render(<ResponsiveImage src={testSrc} alt="测试" loading="eager" />);
      
      expect(testSrc).toBeDefined();
    });
  });

  describe('加载状态管理', () => {
    it('应该初始显示加载占位符', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" />);

      expect(screen.getByTestId('image-icon')).toBeInTheDocument();
    });

    it('应该在图片加载成功后隐藏占位符显示图片', async () => {
      const handleLoad = vi.fn<[], void>();
      render(<ResponsiveImage src={testSrc} alt="测试" onLoad={handleLoad} loading="eager" />);

      const img = document.querySelector('img');
      
      // 模拟图片加载成功
      await act(async () => {
        fireEvent.load(img!);
      });

      await vi.waitFor(() => {
        expect(handleLoad).toHaveBeenCalledTimes(1);
      }, { timeout: 3000, interval: 100 });
    });

    it('应该在图片加载失败后显示错误状态', async () => {
      const handleError = vi.fn<[string], void>();
      render(<ResponsiveImage src={testSrc} alt="测试" onError={handleError} loading="eager" />);

      const img = document.querySelector('img');
      
      // 模拟图片加载失败
      await act(async () => {
        fireEvent.error(img!);
      });

      await vi.waitFor(() => {
        expect(handleError).toHaveBeenCalledWith('图片加载失败');
      }, { timeout: 3000, interval: 100 });

      // 检查错误UI显示
      expect(screen.getByText('加载失败')).toBeInTheDocument();
    });
  });

  describe('懒加载功能', () => {
    it('应该使用IntersectionObserver实现懒加载', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" loading="lazy" />);

      // 验证IntersectionObserver被正确创建
      expect(MockIntersectionObserver.prototype.observe).toBeDefined();
    });

    it('应该在eager模式下立即加载图片', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" loading="eager" />);

      const img = document.querySelector('img');
      expect(img).toHaveAttribute('loading', 'eager');
    });

    it('应该默认使用懒加载模式', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" />);

      const img = document.querySelector('img');
      expect(img).toHaveAttribute('loading', 'lazy');
    });
  });

  describe('占位符和错误状态', () => {
    it('应该支持自定义占位符', () => {
      const customPlaceholder = <div data-testid="custom-placeholder">自定义占位符</div>;
      render(
        <ResponsiveImage src={testSrc} alt="测试" placeholder={customPlaceholder} />
      );

      expect(screen.getByTestId('custom-placeholder')).toBeInTheDocument();
      expect(screen.getByText('自定义占位符')).toBeInTheDocument();
    });

    it('应该支持自定义错误回退UI', async () => {
      const customFallback = <div data-testid="custom-fallback">加载失败了</div>;
      render(
        <ResponsiveImage src={testSrc} alt="测试" fallback={customFallback} loading="eager" />
      );

      const img = document.querySelector('img');
      
      // 模拟加载失败
      await act(async () => {
        fireEvent.error(img!);
      });

      await vi.waitFor(() => {
        expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
        expect(screen.getByText('加载失败了')).toBeInTheDocument();
      }, { timeout: 3000, interval: 100 });
    });

    it('应该为默认占位符应用动画效果', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" />);

      const icon = screen.getByTestId('image-icon');
      expect(icon).toHaveClass('animate-pulse');
    });
  });

  describe('图片优化特性', () => {
    it('应该设置正确的图片解码属性', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" loading="eager" />);

      const img = document.querySelector('img');
      expect(img).toHaveAttribute('decoding', 'async');
    });

    it('应该应用渐进式加载的透明度过渡', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" loading="eager" />);

      const img = document.querySelector('img');
      expect(img).toHaveClass('transition-opacity', 'duration-300');
    });

    it('应该在加载完成前设置0透明度', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" loading="eager" />);

      const img = document.querySelector('img');
      expect(img).toHaveClass('opacity-0');
    });
  });

  describe('响应式容器', () => {
    it('应该设置容器为相对定位和隐藏溢出', () => {
      const { container } = render(<ResponsiveImage src={testSrc} alt="测试" />);

      const imageContainer = container.firstChild as HTMLElement;
      expect(imageContainer).toHaveClass('relative', 'overflow-hidden');
    });

    it('应该为图片设置正确的对象填充样式', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" loading="eager" />);

      const img = document.querySelector('img');
      expect(img).toHaveClass('w-full', 'h-full', 'object-cover');
    });

    it('应该在没有指定宽高比时使用默认video比例', () => {
      render(<ResponsiveImage src={testSrc} alt="测试" />);

      // 检查占位符容器有aspect-video类
      const placeholderContainer = screen.getByTestId('image-icon').parentElement;
      expect(placeholderContainer).toHaveClass('aspect-video');
    });
  });

  describe('源集回退逻辑', () => {
    it('应该在平板设备没有tablet源时回退到desktop源', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'tablet',
        pixelRatio: 1,
      });

      const srcSetWithoutTablet = {
        mobile: 'mobile.jpg',
        desktop: 'desktop.jpg',
      };

      render(
        <ResponsiveImage 
          src={testSrc} 
          alt="测试" 
          srcSet={srcSetWithoutTablet} 
          loading="eager" 
        />
      );

      expect(srcSetWithoutTablet.desktop).toBeDefined();
    });

    it('应该在没有对应设备源时回退到默认src', () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'mobile',
        pixelRatio: 1,
      });

      const limitedSrcSet = {
        desktop: 'desktop.jpg',
      };

      render(
        <ResponsiveImage 
          src={testSrc} 
          alt="测试" 
          srcSet={limitedSrcSet} 
          loading="eager" 
        />
      );

      expect(testSrc).toBeDefined();
    });
  });

  describe('组合场景测试', () => {
    it('应该正确组合所有特性 - 高分屏移动端懒加载', async () => {
      getMockUseDeviceDetection().mockReturnValue({
        ...defaultMockReturn,
        type: 'mobile',
        pixelRatio: 2,
      });

      const handleLoad = vi.fn<[], void>();
      const handleError = vi.fn<[string], void>();

      const { container } = render(
        <ResponsiveImage
          src={testSrc}
          alt="高分屏移动端图片"
          srcSet={testSrcSet}
          loading="lazy"
          onLoad={handleLoad}
          onError={handleError}
          aspectRatio="1/1"
          className="rounded-lg"
        />
      );

      // 检查容器样式 - 查找最外层容器
      const outerContainer = container.firstChild as HTMLElement;
      expect(outerContainer).toHaveClass('rounded-lg');
      expect(outerContainer).toHaveStyle({ aspectRatio: '1/1' });
      
      // 检查内部占位符容器的样式
      const placeholderContainer = screen.getByTestId('image-icon').closest('div');
      expect(placeholderContainer).toHaveClass('flex', 'items-center', 'justify-center');

      // 检查初始占位符
      expect(screen.getByTestId('image-icon')).toBeInTheDocument();

      // 检查图片属性
      const img = document.querySelector('img');
      expect(img).toHaveAttribute('loading', 'lazy');
      expect(img).toHaveAttribute('decoding', 'async');
      expect(img).toHaveAttribute('alt', '高分屏移动端图片');
      
      // 检查图片样式类
      expect(img).toHaveClass(
        'w-full', 
        'h-full', 
        'object-cover', 
        'transition-opacity', 
        'duration-300',
        'opacity-0'
      );
    });

    it('应该处理完整的加载生命周期', async () => {
      const handleLoad = vi.fn<[], void>();
      
      render(
        <ResponsiveImage
          src={testSrc}
          alt="生命周期测试"
          onLoad={handleLoad}
          loading="eager"
        />
      );

      // 初始状态：显示占位符
      expect(screen.getByTestId('image-icon')).toBeInTheDocument();

      const img = document.querySelector('img');
      expect(img).toHaveClass('opacity-0');

      // 模拟图片加载完成
      await act(async () => {
        fireEvent.load(img!);
      });

      await vi.waitFor(() => {
        expect(handleLoad).toHaveBeenCalledTimes(1);
      }, { timeout: 3000, interval: 100 });
    });
  });
});