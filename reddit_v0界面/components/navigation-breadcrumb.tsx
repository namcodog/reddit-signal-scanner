"use client"

import { ChevronRight, FileText, BarChart3, Lightbulb } from "lucide-react"

interface NavigationBreadcrumbProps {
  currentStep: "input" | "analysis" | "report"
  onNavigate: (step: "input" | "analysis" | "report") => void
  canNavigateBack?: boolean
}

export default function NavigationBreadcrumb({
  currentStep,
  onNavigate,
  canNavigateBack = true,
}: NavigationBreadcrumbProps) {
  const steps = [
    {
      id: "input" as const,
      title: "产品输入",
      icon: <FileText className="w-4 h-4" />,
      description: "描述您的产品",
    },
    {
      id: "analysis" as const,
      title: "信号分析",
      icon: <BarChart3 className="w-4 h-4" />,
      description: "处理洞察信息",
    },
    {
      id: "report" as const,
      title: "商业洞察",
      icon: <Lightbulb className="w-4 h-4" />,
      description: "查看结果",
    },
  ]

  const currentStepIndex = steps.findIndex((step) => step.id === currentStep)

  return (
    <nav className="flex items-center justify-center space-x-2 text-sm mb-8">
      {steps.map((step, index) => {
        const isActive = step.id === currentStep
        const isCompleted = index < currentStepIndex
        const isAccessible = canNavigateBack || index <= currentStepIndex

        return (
          <div key={step.id} className="flex items-center space-x-2">
            {index > 0 && <ChevronRight className="w-4 h-4 text-muted-foreground" />}
            <button
              onClick={() => (isAccessible ? onNavigate(step.id) : undefined)}
              disabled={!isAccessible}
              className={`flex items-center space-x-2 px-3 py-1 rounded-md transition-colors ${
                isActive
                  ? "bg-secondary text-secondary-foreground"
                  : isCompleted
                    ? "text-foreground hover:bg-muted"
                    : isAccessible
                      ? "text-muted-foreground hover:text-foreground"
                      : "text-muted-foreground/50 cursor-not-allowed"
              }`}
            >
              {step.icon}
              <div className="text-left">
                <div className="font-medium">{step.title}</div>
                <div className="text-xs opacity-75">{step.description}</div>
              </div>
            </button>
          </div>
        )
      })}
    </nav>
  )
}
