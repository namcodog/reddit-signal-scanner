/**
 * 触摸手势Hook - v0级别的移动端交互
 * 特点：高性能、类型安全、可配置
 */

import { useRef, useEffect, useCallback } from 'react';

interface SwipeConfig {
  threshold: number;
  velocityThreshold: number;
  preventScroll: boolean;
}

interface UseSwipeGestureOptions {
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  onSwipeUp?: () => void;
  onSwipeDown?: () => void;
  onTap?: () => void;
  onLongPress?: () => void;
  config?: Partial<SwipeConfig>;
}

const DEFAULT_CONFIG: SwipeConfig = {
  threshold: 50,        // 最小滑动距离
  velocityThreshold: 0.5, // 最小滑动速度
  preventScroll: false,   // 是否阻止滚动
};

export const useSwipeGesture = (
  elementRef: React.RefObject<HTMLElement>,
  options: UseSwipeGestureOptions
): void => {
  const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const longPressTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isLongPressRef = useRef(false);
  
  const config = { ...DEFAULT_CONFIG, ...options.config };
  
  const {
    onSwipeLeft,
    onSwipeRight,
    onSwipeUp,
    onSwipeDown,
    onTap,
    onLongPress,
  } = options;

  // 清理长按计时器
  const clearLongPressTimer = useCallback((): void => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }, []);

  // 处理触摸开始
  const handleTouchStart = useCallback((e: TouchEvent): void => {
    const touch = e.touches[0];
    touchStartRef.current = {
      x: touch.clientX,
      y: touch.clientY,
      time: Date.now(),
    };
    
    isLongPressRef.current = false;
    
    // 设置长按计时器
    if (onLongPress) {
      longPressTimerRef.current = setTimeout(() => {
        isLongPressRef.current = true;
        onLongPress();
      }, 500);
    }
    
    // 阻止滚动（如果配置要求）
    if (config.preventScroll) {
      e.preventDefault();
    }
  }, [onLongPress, config.preventScroll]);

  // 处理触摸移动
  const handleTouchMove = useCallback((e: TouchEvent): void => {
    clearLongPressTimer();
    
    if (config.preventScroll) {
      e.preventDefault();
    }
  }, [clearLongPressTimer, config.preventScroll]);

  // 处理触摸结束
  const handleTouchEnd = useCallback((e: TouchEvent): void => {
    clearLongPressTimer();
    
    if (!touchStartRef.current) return;
    
    const touch = e.changedTouches[0];
    const endTime = Date.now();
    const deltaTime = endTime - touchStartRef.current.time;
    const deltaX = touch.clientX - touchStartRef.current.x;
    const deltaY = touch.clientY - touchStartRef.current.y;
    
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
    const velocity = distance / deltaTime;
    
    // 判断是否为点击
    if (distance < 10 && deltaTime < 300 && !isLongPressRef.current && onTap) {
      onTap();
      return;
    }
    
    // 判断是否达到滑动阈值
    if (distance < config.threshold || velocity < config.velocityThreshold) {
      return;
    }
    
    // 判断滑动方向
    const isHorizontal = Math.abs(deltaX) > Math.abs(deltaY);
    
    if (isHorizontal) {
      // 水平滑动
      if (deltaX > 0 && onSwipeRight) {
        onSwipeRight();
      } else if (deltaX < 0 && onSwipeLeft) {
        onSwipeLeft();
      }
    } else {
      // 垂直滑动
      if (deltaY > 0 && onSwipeDown) {
        onSwipeDown();
      } else if (deltaY < 0 && onSwipeUp) {
        onSwipeUp();
      }
    }
    
    touchStartRef.current = null;
  }, [config, onSwipeLeft, onSwipeRight, onSwipeUp, onSwipeDown, onTap, clearLongPressTimer]);

  // 绑定事件监听器
  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    element.addEventListener('touchstart', handleTouchStart, { passive: !config.preventScroll });
    element.addEventListener('touchmove', handleTouchMove, { passive: !config.preventScroll });
    element.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      element.removeEventListener('touchstart', handleTouchStart);
      element.removeEventListener('touchmove', handleTouchMove);
      element.removeEventListener('touchend', handleTouchEnd);
      clearLongPressTimer();
    };
  }, [elementRef, handleTouchStart, handleTouchMove, handleTouchEnd, clearLongPressTimer, config.preventScroll]);
};