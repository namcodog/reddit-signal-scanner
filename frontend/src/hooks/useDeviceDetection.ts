/**
 * 设备检测Hook - 响应式设计核心 + v0特性检测
 * 原则：单一数据源，实时响应，v0级别体验
 */

import { useState, useEffect, useMemo } from 'react';
import { DeviceType, DeviceInfo, BREAKPOINTS } from '@/types/responsive.types';

export const useDeviceDetection = (): DeviceInfo => {
  const [windowSize, setWindowSize] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 1024,
    height: typeof window !== 'undefined' ? window.innerHeight : 768,
  });

  // 监听窗口大小变化（v0级别防抖）
  useEffect(() => {
    const handleResize = (): void => {
      setWindowSize({
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };

    // 高性能防抖处理
    let timeoutId: NodeJS.Timeout;
    let animationId: number;
    
    const debouncedResize = (): void => {
      cancelAnimationFrame(animationId);
      clearTimeout(timeoutId);
      
      animationId = requestAnimationFrame(() => {
        timeoutId = setTimeout(handleResize, 100);
      });
    };

    window.addEventListener('resize', debouncedResize, { passive: true });
    
    return () => {
      window.removeEventListener('resize', debouncedResize);
      cancelAnimationFrame(animationId);
      clearTimeout(timeoutId);
    };
  }, []);

  // 计算设备信息（v0级别检测精度）
  const deviceInfo = useMemo((): DeviceInfo => {
    const { width, height } = windowSize;
    
    // 确定设备类型（细化分类）
    let type: DeviceType;
    if (width < BREAKPOINTS.md) {
      type = 'mobile';
    } else if (width < BREAKPOINTS.lg) {
      type = 'tablet';
    } else {
      type = 'desktop';
    }

    // 全面的设备特性检测
    type DocumentTouchCtor = { new (): unknown };
    const w = window as unknown as { DocumentTouch?: DocumentTouchCtor };
    const isTouchDevice = 
      typeof window !== 'undefined' &&
      ('ontouchstart' in window || 
       navigator.maxTouchPoints > 0 ||
       (w.DocumentTouch !== undefined && document instanceof (w.DocumentTouch as unknown as { new (): Document }) ));

    // 悬停能力检测（v0交互优化）
    const hasHover = 
      typeof window !== 'undefined' &&
      window.matchMedia('(hover: hover)').matches;

    // 无障碍支持检测
    const prefersReducedMotion = 
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    return {
      type,
      width,
      height,
      isTouchDevice,
      isPortrait: height > width,
      pixelRatio: typeof window !== 'undefined' ? window.devicePixelRatio : 1,
      hasHover,
      prefersReducedMotion,
    };
  }, [windowSize]);

  return deviceInfo;
};

// v0风格的主题检测Hook
export const useThemeDetection = () => {
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system');
  
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if (theme === 'system') {
        // 系统主题变化时更新
        document.documentElement.classList.toggle('dark', mediaQuery.matches);
      }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    handleChange(); // 初始设置
    
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme]);
  
  return { theme, setTheme };
};