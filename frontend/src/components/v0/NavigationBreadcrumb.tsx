import React from 'react';
import { FileText, BarChart3, Lightbulb, ChevronRight } from 'lucide-react';

export type StepKey = 'input' | 'analysis' | 'report';

interface NavigationBreadcrumbProps {
  currentStep: StepKey;
  onNavigate?: (step: StepKey) => void;
  canNavigateBack?: boolean;
}

const steps: Array<{
  id: StepKey;
  title: string;
  description: string;
  icon: React.ReactNode;
}> = [
  {
    id: 'input',
    title: '产品输入',
    description: '描述您的产品',
    icon: <FileText className="size-4" />,
  },
  {
    id: 'analysis',
    title: '信号分析',
    description: '处理洞察信息',
    icon: <BarChart3 className="size-4" />,
  },
  {
    id: 'report',
    title: '商业洞察',
    description: '查看结果',
    icon: <Lightbulb className="size-4" />,
  },
];

const NavigationBreadcrumb: React.FC<NavigationBreadcrumbProps> = ({ currentStep, onNavigate, canNavigateBack = true }) => {
  const currentIndex = steps.findIndex((step) => step.id === currentStep);

  return (
    <nav className="flex flex-wrap items-center justify-center gap-2 text-sm">
      {steps.map((step, index) => {
        const isActive = step.id === currentStep;
        const isCompleted = index < currentIndex;
        const allowNavigation = Boolean(onNavigate);
        const isAccessible = allowNavigation && (isActive || (canNavigateBack ? index <= currentIndex : index === currentIndex));

        return (
          <React.Fragment key={step.id}>
            {index > 0 && <ChevronRight className="size-4 text-muted-foreground" />}
            <button
              type="button"
              aria-current={isActive ? 'step' : undefined}
              onClick={() => (isAccessible && onNavigate ? onNavigate(step.id) : undefined)}
              disabled={!isAccessible}
              className={`flex items-center space-x-2 rounded-md px-3 py-1 transition-colors ${
                isActive
                  ? 'bg-secondary text-secondary-foreground'
                  : isCompleted
                    ? 'text-foreground hover:bg-muted'
                    : allowNavigation
                      ? 'text-muted-foreground hover:text-foreground'
                      : 'text-muted-foreground'
              } ${isAccessible ? 'hover:shadow-sm' : ''}`}
            >
              <span className="inline-flex items-center justify-center">
                {step.icon}
              </span>
              <span className="text-left">
                <span className="block font-medium leading-tight">{step.title}</span>
                <span
                  className={`block text-xs ${
                    isActive ? 'text-secondary-foreground/80' : 'text-muted-foreground/80'
                  }`}
                >
                  {step.description}
                </span>
              </span>
            </button>
          </React.Fragment>
        );
      })}
    </nav>
  );
};

export default NavigationBreadcrumb;
