/**
 * 响应式按钮组件 - v0设计语言 + 移动端优化
 * 满足最小44px触摸目标 + v0美学标准
 */

import React, { ButtonHTMLAttributes, forwardRef } from 'react';
import { useDeviceDetection } from '@/hooks/useDeviceDetection';
import { Loader2 } from 'lucide-react';

interface ResponsiveButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
}

const ResponsiveButton = forwardRef<HTMLButtonElement, ResponsiveButtonProps>(
  ({
    children,
    variant = 'default',
    size = 'md',
    fullWidth = false,
    loading = false,
    icon,
    iconPosition = 'left',
    className = '',
    disabled,
    ...props
  }, ref) => {
    const { type, isTouchDevice, prefersReducedMotion } = useDeviceDetection();

    // v0风格的尺寸计算（移动端优化）
    const getSizeClasses = (): string => {
      const isMobile = type === 'mobile';
      
      if (isTouchDevice || isMobile) {
        // 移动端最小高度44px（Apple HIG标准）
        switch (size) {
          case 'sm':
            return 'h-11 px-4 text-sm'; // 44px高度
          case 'md':
            return 'h-12 px-6 text-base'; // 48px高度
          case 'lg':
            return 'h-14 px-8 text-lg'; // 56px高度
          default:
            return 'h-12 px-6 text-base';
        }
      }
      
      // 桌面端正常尺寸（v0标准）
      switch (size) {
        case 'sm':
          return 'h-9 px-3 text-sm';
        case 'md':
          return 'h-10 px-4 text-sm';
        case 'lg':
          return 'h-11 px-8 text-base';
        default:
          return 'h-10 px-4 text-sm';
      }
    };

    // v0风格的变体样式
    const getVariantClasses = (): string => {
      const baseClasses = 'inline-flex items-center justify-center whitespace-nowrap rounded-md font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50';
      
      const variantClasses = {
        default: 'bg-blue-600 text-white hover:bg-blue-700',
        destructive: 'bg-red-600 text-white hover:bg-red-700',
        outline: 'border border-gray-300 bg-white hover:bg-gray-50 hover:text-gray-900',
        secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200',
        ghost: 'hover:bg-gray-100 hover:text-gray-900',
        link: 'text-blue-600 underline-offset-4 hover:underline',
      };
      
      return `${baseClasses} ${variantClasses[variant]}`;
    };

    // 触摸反馈效果（v0微交互）
    const getTouchFeedbackClass = (): string => {
      if (isTouchDevice && !prefersReducedMotion) {
        return 'active:scale-95 active:transition-transform active:duration-75';
      }
      return '';
    };

    // 图标渲染
    const renderIcon = () => {
      if (loading) {
        return <Loader2 className="h-4 w-4 animate-spin" />;
      }
      return icon;
    };

    return (
      <button
        ref={ref}
        className={`
          ${getSizeClasses()}
          ${getVariantClasses()}
          ${getTouchFeedbackClass()}
          ${fullWidth ? 'w-full' : ''}
          ${className}
        `}
        disabled={disabled || loading}
        data-loading={loading}
        data-testid="responsive-button"
        {...props}
      >
        {renderIcon() && iconPosition === 'left' && (
          <span className={children ? 'mr-2' : ''}>
            {renderIcon()}
          </span>
        )}
        
        {loading ? '加载中...' : children}
        
        {renderIcon() && iconPosition === 'right' && (
          <span className={children ? 'ml-2' : ''}>
            {renderIcon()}
          </span>
        )}
      </button>
    );
  }
);

ResponsiveButton.displayName = 'ResponsiveButton';

export default ResponsiveButton;