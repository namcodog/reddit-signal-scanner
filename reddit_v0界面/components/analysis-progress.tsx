"use client"

import type React from "react"
import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Search, Brain, Clock, CheckCircle, Loader2, Users, MessageSquare, TrendingUp, LogIn } from "lucide-react"
import { useAppState } from "@/hooks/use-app-state"

interface AnalysisStep {
  id: string
  title: string
  description: string
  icon: React.ReactNode
  duration: number // in seconds
  status: "pending" | "in-progress" | "completed"
}

interface AnalysisProgressProps {
  productDescription: string
  onComplete: (analysisId: string) => void
  onCancel: () => void
}

export default function AnalysisProgress({ productDescription, onComplete, onCancel }: AnalysisProgressProps) {
  const [state, actions] = useAppState()
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [progress, setProgress] = useState(0)
  const [timeElapsed, setTimeElapsed] = useState(0)
  const [estimatedTimeRemaining, setEstimatedTimeRemaining] = useState(15) // 15 seconds instead of 5 minutes
  const [isComplete, setIsComplete] = useState(false)
  const [showLoginDialog, setShowLoginDialog] = useState(false)

  const analysisSteps: AnalysisStep[] = [
    {
      id: "data-collection",
      title: "数据收集与处理",
      description: "全面收集和处理相关市场数据",
      icon: <Search className="w-5 h-5" />,
      duration: 8,
      status: "pending",
    },
    {
      id: "intelligent-analysis",
      title: "智能分析与洞察生成",
      description: "运用AI技术深度分析并生成商业洞察",
      icon: <Brain className="w-5 h-5" />,
      duration: 7,
      status: "pending",
    },
  ]

  const [steps, setSteps] = useState(analysisSteps)

  // Mock analysis progress simulation
  useEffect(() => {
    const interval = setInterval(() => {
      setTimeElapsed((prev) => prev + 1)

      // Calculate progress based on time elapsed
      const totalDuration = steps.reduce((sum, step) => sum + step.duration, 0)
      const newProgress = Math.min((timeElapsed / totalDuration) * 100, 100)
      setProgress(newProgress)

      // Update current step
      let cumulativeTime = 0
      let newCurrentStepIndex = 0

      for (let i = 0; i < steps.length; i++) {
        cumulativeTime += steps[i].duration
        if (timeElapsed < cumulativeTime) {
          newCurrentStepIndex = i
          break
        }
        newCurrentStepIndex = i + 1
      }

      setCurrentStepIndex(newCurrentStepIndex)

      // Update step statuses
      setSteps((prevSteps) =>
        prevSteps.map((step, index) => ({
          ...step,
          status: index < newCurrentStepIndex ? "completed" : index === newCurrentStepIndex ? "in-progress" : "pending",
        })),
      )

      // Calculate estimated time remaining
      const remaining = Math.max(totalDuration - timeElapsed, 0)
      setEstimatedTimeRemaining(remaining)

      // Check if analysis is complete
      if (timeElapsed >= totalDuration && !isComplete) {
        setIsComplete(true)
        setTimeout(() => {
          onComplete("mock-analysis-id-" + Date.now())
        }, 2000)
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [timeElapsed, steps, isComplete, onComplete])

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  const getStepIcon = (step: AnalysisStep, index: number) => {
    if (step.status === "completed") {
      return <CheckCircle className="w-5 h-5 text-green-500" />
    } else if (step.status === "in-progress") {
      return <Loader2 className="w-5 h-5 text-secondary animate-spin" />
    } else {
      return <div className="w-5 h-5 rounded-full border-2 border-muted-foreground/30" />
    }
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    const formData = new FormData(e.target as HTMLFormElement)
    const email = formData.get("email") as string
    const password = formData.get("password") as string
    actions.login(email, password)
    setShowLoginDialog(false)
  }

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault()
    const formData = new FormData(e.target as HTMLFormElement)
    const name = formData.get("name") as string
    const email = formData.get("email") as string
    const password = formData.get("password") as string
    actions.login(email, password, name)
    setShowLoginDialog(false)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex justify-end mb-4">
        {!state.isAuthenticated && (
          <Dialog open={showLoginDialog} onOpenChange={setShowLoginDialog}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" className="flex items-center space-x-2 bg-transparent">
                <LogIn className="w-4 h-4" />
                <span>登录</span>
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>登录账户</DialogTitle>
                <DialogDescription>登录以保存您的分析结果和访问更多功能</DialogDescription>
              </DialogHeader>
              <Tabs defaultValue="login" className="space-y-4">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="login">登录</TabsTrigger>
                  <TabsTrigger value="signup">注册</TabsTrigger>
                </TabsList>

                <TabsContent value="login">
                  <form onSubmit={handleLogin} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="email">邮箱</Label>
                      <Input id="email" name="email" type="email" placeholder="请输入您的邮箱" required />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="password">密码</Label>
                      <Input id="password" name="password" type="password" placeholder="请输入您的密码" required />
                    </div>
                    <Button type="submit" className="w-full">
                      登录
                    </Button>
                  </form>
                </TabsContent>

                <TabsContent value="signup">
                  <form onSubmit={handleSignup} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="name">姓名</Label>
                      <Input id="name" name="name" type="text" placeholder="请输入您的姓名" required />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="signup-email">邮箱</Label>
                      <Input id="signup-email" name="email" type="email" placeholder="请输入您的邮箱" required />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="signup-password">密码</Label>
                      <Input id="signup-password" name="password" type="password" placeholder="创建密码" required />
                    </div>
                    <Button type="submit" className="w-full">
                      创建账户
                    </Button>
                  </form>
                </TabsContent>
              </Tabs>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* Header */}
      <div className="text-center space-y-4">
        <div className="flex items-center justify-center space-x-2 mb-4">
          <div className="w-12 h-12 bg-secondary/10 rounded-xl flex items-center justify-center">
            <Brain className="w-6 h-6 text-secondary animate-pulse" />
          </div>
        </div>
        <h2 className="text-3xl font-bold text-foreground">{isComplete ? "分析完成！" : "正在分析您的产品"}</h2>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          {isComplete ? "我们已经发现了关于您市场机会的宝贵洞察" : "我们正在扫描 Reddit 社区，为您的产品寻找商业机会"}
        </p>
      </div>

      {/* Product Summary */}
      <Card className="border-secondary/20">
        <CardHeader>
          <CardTitle className="text-lg">正在分析的产品</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground line-clamp-3">{productDescription}</p>
        </CardContent>
      </Card>

      {/* Progress Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <Clock className="w-5 h-5 text-secondary" />
                <span>分析进度</span>
              </CardTitle>
              <CardDescription>
                {isComplete
                  ? "分析已成功完成"
                  : `第 ${currentStepIndex + 1} 步，共 ${steps.length} 步 • 剩余 ${formatTime(estimatedTimeRemaining)}`}
              </CardDescription>
            </div>
            <Badge variant={isComplete ? "default" : "secondary"} className="ml-4">
              {Math.round(progress)}%
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <Progress value={progress} className="h-3" />

          {/* Step Details */}
          <div className="space-y-4">
            {steps.map((step, index) => (
              <div
                key={step.id}
                className={`flex items-center space-x-4 p-4 rounded-lg border transition-all ${
                  step.status === "in-progress"
                    ? "border-secondary/50 bg-secondary/5"
                    : step.status === "completed"
                      ? "border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950"
                      : "border-border bg-card"
                }`}
              >
                <div className="flex-shrink-0">{getStepIcon(step, index)}</div>
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-foreground">{step.title}</h4>
                  <p className="text-sm text-muted-foreground">{step.description}</p>
                </div>
                <div className="flex-shrink-0">
                  {step.status === "in-progress" && (
                    <Badge variant="secondary" className="animate-pulse">
                      处理中...
                    </Badge>
                  )}
                  {step.status === "completed" && (
                    <Badge variant="default" className="bg-green-500">
                      完成
                    </Badge>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Live Stats */}
      {!isComplete && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-4 text-center">
              <div className="w-8 h-8 bg-secondary/10 rounded-lg flex items-center justify-center mx-auto mb-2">
                <Users className="w-4 h-4 text-secondary" />
              </div>
              <div className="text-2xl font-bold text-foreground">
                {Math.min(Math.floor(timeElapsed / 10) * 3 + 12, 47)}
              </div>
              <p className="text-sm text-muted-foreground">发现的社区</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 text-center">
              <div className="w-8 h-8 bg-secondary/10 rounded-lg flex items-center justify-center mx-auto mb-2">
                <MessageSquare className="w-4 h-4 text-secondary" />
              </div>
              <div className="text-2xl font-bold text-foreground">
                {Math.min(Math.floor(timeElapsed / 5) * 127 + 234, 2847)}
              </div>
              <p className="text-sm text-muted-foreground">已分析帖子</p>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-4 text-center">
              <div className="w-8 h-8 bg-secondary/10 rounded-lg flex items-center justify-center mx-auto mb-2">
                <TrendingUp className="w-4 h-4 text-secondary" />
              </div>
              <div className="text-2xl font-bold text-foreground">
                {Math.min(Math.floor(timeElapsed / 15) * 8 + 3, 23)}
              </div>
              <p className="text-sm text-muted-foreground">生成的洞察</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center justify-center space-x-4">
        {!isComplete ? (
          <Button variant="outline" onClick={onCancel}>
            取消分析
          </Button>
        ) : (
          <Button size="lg" onClick={() => onComplete("mock-analysis-id")}>
            查看报告
          </Button>
        )}
      </div>

      {/* Time Display */}
      <div className="text-center text-sm text-muted-foreground">
        已用时间：{formatTime(timeElapsed)}
        {!isComplete && ` • 预计完成时间：${formatTime(estimatedTimeRemaining)}`}
      </div>
    </div>
  )
}
