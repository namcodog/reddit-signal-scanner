/**
 * 响应式设计类型定义 - 100%类型安全 + v0设计融合
 * 基于Linus哲学：数据结构驱动响应式设计
 */

// 设备类型定义（参考v0分类）
export type DeviceType = 'mobile' | 'tablet' | 'desktop';

// 断点定义（与Tailwind保持一致，兼容v0设计）
export const BREAKPOINTS = {
  sm: 640,   // 小屏手机
  md: 768,   // 大屏手机/小平板
  lg: 1024,  // 平板/小桌面
  xl: 1280,  // 桌面
  '2xl': 1536, // 大桌面
} as const;

// 断点类型
export type Breakpoint = keyof typeof BREAKPOINTS;

// 设备信息接口（扩展v0设备检测）
export interface DeviceInfo {
  type: DeviceType;
  width: number;
  height: number;
  isTouchDevice: boolean;
  isPortrait: boolean;
  pixelRatio: number;
  hasHover: boolean; // 检测悬停支持
  prefersReducedMotion: boolean; // 无障碍支持
}

// 响应式配置接口
export interface ResponsiveConfig {
  mobileMaxWidth: number;
  tabletMaxWidth: number;
  enableTouchGestures: boolean;
  enableLazyLoading: boolean;
  enableDarkMode: boolean; // v0特性
}

// 触摸手势类型（v0交互扩展）
export type GestureType = 'swipe' | 'pinch' | 'tap' | 'longPress';

export interface GestureEvent {
  type: GestureType;
  direction?: 'left' | 'right' | 'up' | 'down';
  distance?: number;
  scale?: number;
  target: HTMLElement;
}

// v0风格的主题类型
export type Theme = 'light' | 'dark' | 'system';

// 响应式布局类型
export type LayoutVariant = 'compact' | 'comfortable' | 'spacious';

export interface ResponsiveLayoutProps {
  variant?: LayoutVariant;
  enablePadding?: boolean;
  enableSafeArea?: boolean; // iOS安全区域
}