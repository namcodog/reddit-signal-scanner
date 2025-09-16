/**
 * 导航Hook - 统一的导航状态管理
 * 原则：单一数据源，类型安全
 */

import { useCallback, useMemo } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { NavigationStep, NavigationState, ROUTES } from '@/types/router.types';

interface UseNavigationReturn {
  currentStep: NavigationStep;
  taskId: string | undefined;
  canNavigateTo: (step: NavigationStep) => boolean;
  navigateTo: (step: NavigationStep) => void;
  goBack: () => void;
  state: NavigationState;
}

export const useNavigation = (): UseNavigationReturn => {
  const location = useLocation();
  const navigate = useNavigate();
  const { taskId } = useParams<{ taskId: string }>();
  
  // 确定当前步骤
  const currentStep = useMemo((): NavigationStep => {
    const path = location.pathname;
    
    if (path === ROUTES.INPUT) return 'input';
    if (path.startsWith('/analysis/')) return 'analysis';
    if (path.startsWith('/report/')) return 'report';
    
    return 'input';
  }, [location.pathname]);
  
  // 导航状态
  const state = useMemo((): NavigationState => {
    const completedSteps: NavigationStep[] = [];
    
    if (currentStep === 'analysis' || currentStep === 'report') {
      completedSteps.push('input');
    }
    if (currentStep === 'report') {
      completedSteps.push('analysis');
    }
    
    return {
      currentStep,
      completedSteps,
      canNavigateBack: currentStep !== 'analysis', // 分析中不允许返回
      taskId,
    };
  }, [currentStep, taskId]);
  
  // 检查是否可以导航到某步骤
  const canNavigateTo = useCallback((step: NavigationStep): boolean => {
    // 当前步骤总是可以访问
    if (step === currentStep) return true;
    
    // 分析中不允许导航
    if (currentStep === 'analysis') return false;
    
    // 检查是否已完成
    return state.completedSteps.includes(step) || step === 'input';
  }, [currentStep, state.completedSteps]);
  
  // 导航到指定步骤
  const navigateTo = useCallback((step: NavigationStep): void => {
    if (!canNavigateTo(step)) return;
    
    switch (step) {
      case 'input':
        navigate(ROUTES.INPUT);
        break;
      case 'analysis':
        if (taskId) {
          navigate(ROUTES.ANALYSIS.replace(':taskId', taskId));
        }
        break;
      case 'report':
        if (taskId) {
          navigate(ROUTES.REPORT.replace(':taskId', taskId));
        }
        break;
    }
  }, [navigate, taskId, canNavigateTo]);
  
  // 返回上一步
  const goBack = useCallback((): void => {
    if (!state.canNavigateBack) return;
    
    const steps: NavigationStep[] = ['input', 'analysis', 'report'];
    const currentIndex = steps.indexOf(currentStep);
    
    if (currentIndex > 0) {
      navigateTo(steps[currentIndex - 1]);
    }
  }, [currentStep, state.canNavigateBack, navigateTo]);
  
  return {
    currentStep,
    taskId,
    canNavigateTo,
    navigateTo,
    goBack,
    state,
  };
};