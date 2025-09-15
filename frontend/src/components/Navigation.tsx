/**
 * 导航组件 - v0风格 + 移动端响应式优化
 * 特点：优雅简化、自适应布局、触摸友好
 */

import React from 'react';
import { 
  ChevronRightIcon,
  DocumentTextIcon,
  ChartBarIcon,
  LightBulbIcon 
} from '@heroicons/react/24/outline';
import { NavigationStepInfo, ROUTES } from '@/types/router.types';
import { useNavigation } from '@/hooks/useNavigation';
import { useDeviceDetection } from '@/hooks/useDeviceDetection';

const NAVIGATION_STEPS: NavigationStepInfo[] = [
  {
    id: 'input',
    path: ROUTES.INPUT,
    title: '产品输入',
    description: '描述您的产品',
    icon: DocumentTextIcon,
  },
  {
    id: 'analysis',
    path: ROUTES.ANALYSIS,
    title: '信号分析',
    description: '处理洞察信息',
    icon: ChartBarIcon,
  },
  {
    id: 'report',
    path: ROUTES.REPORT,
    title: '商业洞察',
    description: '查看结果',
    icon: LightBulbIcon,
  },
];

const Navigation: React.FC = () => {
  const { currentStep, canNavigateTo, navigateTo } = useNavigation();
  const { type, isTouchDevice } = useDeviceDetection();
  
  const handleStepClick = (step: NavigationStepInfo): void => {
    if (canNavigateTo(step.id)) {
      navigateTo(step.id);
    }
  };
  
  // 移动端布局判断
  const isMobile = type === 'mobile';
  const isTablet = type === 'tablet';
  
  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="container mx-auto px-4 py-3">
        <div className={`
          flex items-center justify-center
          ${isMobile ? 'space-x-1' : 'space-x-2'}
        `}>
          {NAVIGATION_STEPS.map((step, index) => {
            const isActive = currentStep === step.id;
            const isCompleted = canNavigateTo(step.id) && !isActive;
            const isClickable = canNavigateTo(step.id);
            
            return (
              <React.Fragment key={step.id}>
                {/* 分隔符 - 移动端隐藏 */}
                {index > 0 && !isMobile && (
                  <ChevronRightIcon className="w-4 h-4 text-gray-400" />
                )}
                
                <button
                  onClick={() => handleStepClick(step)}
                  disabled={!isClickable}
                  className={`
                    flex items-center rounded-lg transition-all duration-200
                    ${isMobile 
                      ? 'p-2 flex-col space-y-1 min-w-[60px]' 
                      : isTablet 
                        ? 'px-3 py-2 space-x-2'
                        : 'px-4 py-2 space-x-2'
                    }
                    ${isActive 
                      ? 'bg-blue-50 text-blue-700 border-2 border-blue-200' 
                      : isCompleted
                        ? 'text-gray-700 hover:bg-gray-50 cursor-pointer'
                        : 'text-gray-400 cursor-not-allowed'
                    }
                    ${isTouchDevice ? 'active:scale-95' : ''}
                    ${isClickable ? 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500' : ''}
                  `}
                >
                  <step.icon className={`
                    ${isMobile ? 'w-5 h-5' : 'w-4 h-4'}
                    ${isActive ? 'text-blue-700' : ''}
                  `} />
                  
                  {/* 文字内容 - 响应式显示 */}
                  {!isMobile && (
                    <div className="text-left">
                      <div className={`text-sm font-medium ${isActive ? 'text-blue-700' : ''}`}>
                        {step.title}
                      </div>
                      {!isTablet && (
                        <div className="text-xs opacity-75">{step.description}</div>
                      )}
                    </div>
                  )}
                  
                  {/* 移动端简化标题 */}
                  {isMobile && (
                    <div className={`text-xs font-medium ${isActive ? 'text-blue-700' : ''}`}>
                      {step.title}
                    </div>
                  )}
                </button>
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </nav>
  );
};

export default Navigation;