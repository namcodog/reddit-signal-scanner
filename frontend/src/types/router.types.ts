/**
 * 路由类型定义 - 100%类型安全
 * 基于Linus哲学：数据结构清晰，代码自然简洁
 */

// 路由路径常量 - 单一数据源
export const ROUTES = {
  INPUT: '/',
  ANALYSIS: '/analysis/:taskId',
  REPORT: '/report/:taskId',
} as const;

// 路由路径类型
export type RoutePath = typeof ROUTES[keyof typeof ROUTES];

// 路由参数映射
export interface RouteParamsMap {
  [ROUTES.INPUT]: undefined;
  [ROUTES.ANALYSIS]: { taskId: string };
  [ROUTES.REPORT]: { taskId: string };
}

// 导航步骤定义
export type NavigationStep = 'input' | 'analysis' | 'report';

export interface NavigationStepInfo {
  id: NavigationStep;
  path: RoutePath;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

// 导航状态
export interface NavigationState {
  currentStep: NavigationStep;
  completedSteps: NavigationStep[];
  canNavigateBack: boolean;
  taskId?: string;
}

// 路由守卫类型
export interface RouteGuard {
  canActivate: (to: RoutePath, params?: unknown) => boolean | Promise<boolean>;
  redirectTo?: RoutePath;
}