/**
 * 响应式布局组件 - v0风格统一容器
 * 特点：自适应、触摸优化、性能友好、v0美学
 */

import { ReactNode, forwardRef } from 'react';
import { useDeviceDetection } from '@/hooks/useDeviceDetection';
import { ResponsiveLayoutProps } from '@/types/responsive.types';

interface ExtendedResponsiveLayoutProps extends ResponsiveLayoutProps {
  children: ReactNode;
  className?: string;
}

const ResponsiveLayout = forwardRef<HTMLDivElement, ExtendedResponsiveLayoutProps>(({
  children,
  className = '',
  variant = 'comfortable',
  enablePadding = true,
  enableSafeArea = true,
}, ref) => {
  const { type, isTouchDevice, hasHover, prefersReducedMotion } = useDeviceDetection();

  // 根据设备类型和variant调整间距（v0风格）
  const getSpacingClass = (): string => {
    if (!enablePadding) return '';
    
    const baseSpacing = {
      compact: { mobile: 'px-3 py-2', tablet: 'px-4 py-3', desktop: 'px-6 py-4' },
      comfortable: { mobile: 'px-4 py-3', tablet: 'px-6 py-4', desktop: 'px-8 py-6' },
      spacious: { mobile: 'px-6 py-4', tablet: 'px-8 py-6', desktop: 'px-12 py-8' },
    };
    
    return baseSpacing[variant][type];
  };

  // 触摸设备优化类（v0交互优化）
  const getTouchOptimizationClass = (): string => {
    const touchClasses = [];
    
    if (isTouchDevice) {
      touchClasses.push('touch-manipulation', 'select-none');
    }
    
    if (!hasHover) {
      touchClasses.push('no-hover');
    }
    
    if (prefersReducedMotion) {
      touchClasses.push('reduce-motion');
    }
    
    return touchClasses.join(' ');
  };

  // 安全区域支持（iOS适配）
  const getSafeAreaClass = (): string => {
    return enableSafeArea && type === 'mobile' 
      ? 'safe-area-inset' 
      : '';
  };

  return (
    <div 
      ref={ref}
      className={`
        ${getSpacingClass()}
        ${getTouchOptimizationClass()}
        ${getSafeAreaClass()}
        transition-all duration-200
        ${className}
      `}
      style={{
        // v0级别的微交互
        willChange: prefersReducedMotion ? 'auto' : 'transform',
      }}
    >
      {children}
    </div>
  );
});

ResponsiveLayout.displayName = 'ResponsiveLayout';

export default ResponsiveLayout;