import React from 'react';
import { FileText, BarChart3, Lightbulb } from 'lucide-react';

export type StepKey = 'input' | 'analysis' | 'report';

interface NavigationBreadcrumbProps {
  currentStep: StepKey;
  onNavigate?: (step: StepKey) => void;
  canNavigateBack?: boolean;
}

const STEPS: Array<{
  id: StepKey;
  title: string;
  description: string;
  icon: React.ReactNode;
}> = [
  {
    id: 'input',
    title: '产品输入',
    description: '描述您的产品想法',
    icon: <FileText className="h-4 w-4" />,
  },
  {
    id: 'analysis',
    title: '信号分析',
    description: '实时扫描与处理',
    icon: <BarChart3 className="h-4 w-4" />,
  },
  {
    id: 'report',
    title: '商业洞察',
    description: '查看分析结果',
    icon: <Lightbulb className="h-4 w-4" />,
  },
];

const NavigationBreadcrumb: React.FC<NavigationBreadcrumbProps> = ({
  currentStep,
  onNavigate,
  canNavigateBack = true,
}) => {
  const currentIndex = STEPS.findIndex((step) => step.id === currentStep);

  return (
    <nav className="flex flex-wrap items-center justify-center gap-2 text-sm">
      {STEPS.map((step, index) => {
        const isActive = step.id === currentStep;
        const isCompleted = index < currentIndex;
        const isDisabled = !onNavigate || (!isActive && (!canNavigateBack || index > currentIndex));

        return (
          <React.Fragment key={step.id}>
            {index > 0 ? (
              <span className="text-muted-foreground/60">/</span>
            ) : null}
            <button
              type="button"
              disabled={isDisabled}
              onClick={() => (onNavigate && !isDisabled ? onNavigate(step.id) : undefined)}
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary/40 focus-visible:ring-offset-2 ${
                isActive
                  ? 'bg-secondary text-secondary-foreground shadow-sm'
                  : isCompleted
                    ? 'bg-muted/70 text-foreground'
                    : 'bg-muted text-muted-foreground'
              } ${isDisabled ? 'cursor-default opacity-80' : 'hover:bg-secondary/80 hover:text-secondary-foreground'} `}
            >
              <span className="flex items-center gap-2">
                {step.icon}
                <span className="font-medium">{step.title}</span>
              </span>
              <span className="hidden text-xs text-secondary-foreground/80 sm:inline">{step.description}</span>
            </button>
          </React.Fragment>
        );
      })}
    </nav>
  );
};

export default NavigationBreadcrumb;
