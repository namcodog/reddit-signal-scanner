"use client"

import { useState, useEffect, useCallback } from "react"
import type { AnalysisTask } from "@/types"
import { analysisSteps } from "@/config/app"

interface AnalysisProgress {
  currentStep: number
  totalSteps: number
  overallProgress: number
  currentStepProgress: number
  estimatedTimeRemaining: number
  isComplete: boolean
  isFailed: boolean
}

export function useAnalysisProgress(task: AnalysisTask | null) {
  const [progress, setProgress] = useState<AnalysisProgress>({
    currentStep: 0,
    totalSteps: analysisSteps.length,
    overallProgress: 0,
    currentStepProgress: 0,
    estimatedTimeRemaining: 0,
    isComplete: false,
    isFailed: false,
  })

  const calculateProgress = useCallback((task: AnalysisTask) => {
    const currentStepIndex = analysisSteps.findIndex((step) => step.key === task.currentStep.name)

    const overallProgress = task.progress
    const currentStepProgress = task.currentStep.progress

    // Calculate estimated time remaining
    const totalDuration = analysisSteps.reduce((sum, step) => sum + step.estimatedDuration, 0)
    const completedDuration = analysisSteps
      .slice(0, currentStepIndex)
      .reduce((sum, step) => sum + step.estimatedDuration, 0)
    const currentStepDuration = analysisSteps[currentStepIndex]?.estimatedDuration || 0
    const currentStepCompleted = (currentStepProgress / 100) * currentStepDuration

    const estimatedTimeRemaining = Math.max(0, totalDuration - completedDuration - currentStepCompleted)

    return {
      currentStep: currentStepIndex + 1,
      totalSteps: analysisSteps.length,
      overallProgress,
      currentStepProgress,
      estimatedTimeRemaining,
      isComplete: task.status === "completed",
      isFailed: task.status === "failed",
    }
  }, [])

  useEffect(() => {
    if (task) {
      setProgress(calculateProgress(task))
    } else {
      setProgress({
        currentStep: 0,
        totalSteps: analysisSteps.length,
        overallProgress: 0,
        currentStepProgress: 0,
        estimatedTimeRemaining: 0,
        isComplete: false,
        isFailed: false,
      })
    }
  }, [task, calculateProgress])

  return progress
}
