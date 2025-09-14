"use client"

import { Check, Circle, Clock } from "lucide-react"

interface StepIndicatorProps {
  currentStep: "input" | "analysis" | "report"
  className?: string
}

export default function StepIndicator({ currentStep, className = "" }: StepIndicatorProps) {
  const steps = [
    { id: "input", title: "产品输入", number: 1 },
    { id: "analysis", title: "信号分析", number: 2 },
    { id: "report", title: "商业洞察", number: 3 },
  ]

  const currentStepIndex = steps.findIndex((step) => step.id === currentStep)

  return (
    <div className={`flex items-center justify-center space-x-4 ${className}`}>
      {steps.map((step, index) => {
        const isActive = step.id === currentStep
        const isCompleted = index < currentStepIndex
        const isUpcoming = index > currentStepIndex

        return (
          <div key={step.id} className="flex items-center space-x-2">
            <div className="flex flex-col items-center space-y-2">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all ${
                  isCompleted
                    ? "bg-green-500 border-green-500 text-white"
                    : isActive
                      ? "bg-secondary border-secondary text-secondary-foreground animate-pulse"
                      : "border-muted-foreground/30 text-muted-foreground"
                }`}
              >
                {isCompleted ? (
                  <Check className="w-5 h-5" />
                ) : isActive ? (
                  <Clock className="w-5 h-5" />
                ) : (
                  <Circle className="w-5 h-5" />
                )}
              </div>
              <div className="text-center">
                <div
                  className={`text-sm font-medium ${
                    isActive ? "text-foreground" : isCompleted ? "text-green-600" : "text-muted-foreground"
                  }`}
                >
                  {step.title}
                </div>
                <div className="text-xs text-muted-foreground">第 {step.number} 步</div>
              </div>
            </div>
            {index < steps.length - 1 && (
              <div className={`w-12 h-0.5 ${index < currentStepIndex ? "bg-green-500" : "bg-muted-foreground/30"}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
