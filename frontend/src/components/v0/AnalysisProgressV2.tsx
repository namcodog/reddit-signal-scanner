"use client"

import type React from "react"
import { useEffect, useMemo, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Search, Brain, Clock, CheckCircle, Loader2, Users, MessageSquare, TrendingUp, X } from "lucide-react"
import type { AnalysisState } from "@/hooks/useAppStateV2"

interface AnalysisProgressProps {
  productDescription: string
  analysis: AnalysisState
  onComplete?: (taskId: string) => void
  onCancel: () => void
}

type StepStatus = "pending" | "in-progress" | "completed"

const STEP_DEFINITIONS = [
  {
    id: "data-collection",
    title: "数据收集与处理",
    description: "全面收集和处理相关市场数据",
    icon: <Search className="w-5 h-5" />,
  },
  {
    id: "intelligent-analysis",
    title: "智能分析与洞察生成",
    description: "运用AI技术深度分析并生成商业洞察",
    icon: <Brain className="w-5 h-5" />,
  },
]

const formatTime = (seconds: number): string => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

const resolveStepStatus = (progress: number, stepIndex: number): StepStatus => {
  if (progress >= 100) {
    return "completed"
  }

  if (stepIndex === 0) {
    if (progress === 0) return "pending"
    return progress >= 50 ? "completed" : "in-progress"
  }

  if (stepIndex === 1) {
    if (progress < 50) return "pending"
    return progress >= 99 ? "completed" : "in-progress"
  }

  return "pending"
}

const renderStepIcon = (status: StepStatus): React.ReactNode => {
  switch (status) {
    case "completed":
      return <CheckCircle className="w-5 h-5 text-green-500" />
    case "in-progress":
      return <Loader2 className="w-5 h-5 text-secondary animate-spin" />
    default:
      return <div className="w-5 h-5 rounded-full border-2 border-muted-foreground/30" />
  }
}

export default function AnalysisProgressV2({ productDescription, analysis, onComplete, onCancel }: AnalysisProgressProps) {
  const hasNotifiedCompletion = useRef(false)

  const progress = analysis.progress
  const liveStats = analysis.stats

  const timeElapsed = useMemo(() => {
    if (!analysis.currentTask?.created_at) return 0
    const created = new Date(analysis.currentTask.created_at).getTime()
    if (Number.isNaN(created)) return 0
    return Math.max(0, Math.floor((Date.now() - created) / 1000))
  }, [analysis.currentTask?.created_at])

  // 移除自动跳转逻辑，改为手动点击"查看报告"按钮
  const handleViewReport = () => {
    if (analysis.currentTask?.id && onComplete && !hasNotifiedCompletion.current) {
      hasNotifiedCompletion.current = true
      onComplete(analysis.currentTask.id)
    }
  }

  const steps = useMemo(() =>
    STEP_DEFINITIONS.map((step, index) => ({
      ...step,
      status: resolveStepStatus(progress, index),
    })),
  [progress])

  useEffect(() => {
    hasNotifiedCompletion.current = false
  }, [analysis.currentTask?.id])

  return (
    <div className="mx-auto max-w-4xl space-y-10 px-4">
      <div className="flex flex-col items-center space-y-4 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-secondary/10">
          <Brain className="h-6 w-6 text-secondary animate-pulse" />
        </div>
        <div className="space-y-2">
          <h2 className="text-3xl font-semibold text-foreground">分析进行中</h2>
          <p className="text-base text-muted-foreground">
            我们正在扫描 Reddit 社区，为您的产品识别最有价值的商业信号
          </p>
        </div>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2 text-lg">
                <Clock className="h-5 w-5 text-secondary" />
                实时分析进度
              </CardTitle>
              <CardDescription>
                {analysis.isRunning
                  ? `已运行 ${formatTime(timeElapsed)} · 预计还需 ${formatTime(analysis.estimatedTimeRemaining)}`
                  : "分析已完成，正在生成最终报告"}
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-base font-semibold">
              {Math.round(progress)}%
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <Progress value={progress} className="h-2.5" />

          <div className="grid gap-3 pt-2 sm:grid-cols-3">
            <div className="rounded-xl border border-border/80 bg-card/80 p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary/10">
                  <Users className="h-5 w-5 text-secondary" />
                </div>
                <span className="text-2xl font-semibold text-foreground">{liveStats.communities}</span>
              </div>
              <p className="mt-3 text-sm font-medium text-muted-foreground">社区发现</p>
            </div>
            <div className="rounded-xl border border-border/80 bg-card/80 p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary/10">
                  <MessageSquare className="h-5 w-5 text-secondary" />
                </div>
                <span className="text-2xl font-semibold text-foreground">{liveStats.posts}</span>
              </div>
              <p className="mt-3 text-sm font-medium text-muted-foreground">帖子分析</p>
            </div>
            <div className="rounded-xl border border-border/80 bg-card/80 p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary/10">
                  <TrendingUp className="h-5 w-5 text-secondary" />
                </div>
                <span className="text-2xl font-semibold text-foreground">{liveStats.insights}</span>
              </div>
              <p className="mt-3 text-sm font-medium text-muted-foreground">洞察生成</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border border-dashed border-secondary/40 bg-card/80 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">分析中的产品简介</CardTitle>
          <CardDescription>模型会围绕以下内容持续生成洞察</CardDescription>
        </CardHeader>
        <CardContent className="pb-6">
          <p className="rounded-lg bg-muted/50 p-4 text-sm leading-relaxed text-muted-foreground">
            {productDescription}
          </p>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-foreground">分析步骤</h3>
        <div className="space-y-3">
          {steps.map(step => {
            const stateClass =
              step.status === "completed"
                ? "border-emerald-400/50 bg-emerald-50/70"
                : step.status === "in-progress"
                  ? "border-secondary/60 bg-secondary/10 shadow-sm"
                  : "border-border/70 bg-card/70"

            return (
              <div
                key={step.id}
                className={`flex items-center gap-4 rounded-xl border px-4 py-4 transition-all ${stateClass}`}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full border border-border/60 bg-white shadow-sm">
                  {renderStepIcon(step.status)}
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-9 w-9 items-center justify-center rounded-lg ${
                        step.status === "completed"
                          ? "bg-emerald-500/10 text-emerald-600"
                          : step.status === "in-progress"
                            ? "bg-secondary text-secondary-foreground"
                            : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {step.icon}
                    </div>
                    <h4 className="text-base font-semibold text-foreground">{step.title}</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">{step.description}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {!analysis.isRunning && (
        <Card className="border border-emerald-400/70 bg-emerald-50/80 shadow-sm">
          <CardContent className="space-y-4 p-6 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-white text-emerald-500 shadow-sm">
              <CheckCircle className="h-7 w-7" />
            </div>
            <div className="space-y-2">
              <h3 className="text-xl font-semibold text-emerald-700">分析完成</h3>
              <p className="text-sm text-emerald-700/80">
                我们已经为您准备好可操作的市场洞察，点击即可查看完整报告
              </p>
            </div>
            <Button onClick={handleViewReport} className="px-8" size="lg">
              查看洞察报告
            </Button>
          </CardContent>
        </Card>
      )}

      {/* 取消分析按钮移到底部，分析完成后隐藏 */}
      {analysis.isRunning && (
        <div className="text-center">
          <Button
            variant="outline"
            onClick={onCancel}
            className="mx-auto flex items-center gap-2"
          >
            <X className="h-4 w-4" />
            取消分析
          </Button>
        </div>
      )}
    </div>
  )
}
