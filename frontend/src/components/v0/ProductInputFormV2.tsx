"use client"

import type React from "react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Lightbulb, Clock, Target, Zap } from "lucide-react"

interface ProductInputFormProps {
  onStartAnalysis: (description: string) => void
}

export default function ProductInputFormV2({ onStartAnalysis }: ProductInputFormProps) {
  const [description, setDescription] = useState("")
  const [charCount, setCharCount] = useState(0)
  const [isValid, setIsValid] = useState(false)

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value
    const characters = text.length

    setDescription(text)
    setCharCount(characters)
    setIsValid(characters >= 10 && characters <= 500)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (isValid && description.trim()) {
      onStartAnalysis(description.trim())
    }
  }

  const examples = [
    {
      title: "SaaS 工具",
      description: "一个面向远程团队的项目管理工具，集成 Slack 并自动跟踪任务时间...",
    },
    {
      title: "移动应用",
      description: "一个健身应用，根据可用设备和时间限制创建个性化锻炼计划...",
    },
    {
      title: "电商平台",
      description: "一个专注于可持续时尚品牌的在线市场，重视透明度和道德制造...",
    },
  ]

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-10 px-4">
      {/* Header Section */}
      <div className="space-y-4 text-center">
        <div className="mb-4 flex items-center justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-secondary/10">
            <Lightbulb className="h-6 w-6 text-secondary" />
          </div>
        </div>
        <h2 className="text-3xl font-semibold text-foreground">描述您的产品想法</h2>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          详细告诉我们您的产品或服务。您描述得越具体，我们能提供的洞察就越好。
        </p>
      </div>

      {/* Main Input Form */}
      <Card className="border-2 border-dashed border-border bg-card/95 shadow-sm transition-all hover:border-secondary/50 hover:shadow-lg">
        <CardHeader>
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Target className="h-5 w-5 text-secondary" />
                <span>产品描述</span>
              </CardTitle>
              <CardDescription>包括您的目标受众、核心功能以及您要解决的问题</CardDescription>
            </div>
            <Badge variant={isValid ? "default" : "secondary"} className="w-fit px-3 py-1 text-sm">
              {charCount} 字
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="product-description" className="sr-only">
                产品描述
              </Label>
              <textarea
                id="product-description"
                value={description}
                onChange={handleDescriptionChange}
                className="min-h-40 w-full resize-none rounded-xl border border-border bg-input px-4 py-4 text-foreground shadow-inner placeholder:text-muted-foreground transition-shadow focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="示例：一个帮助忙碌专业人士进行餐食准备的移动应用，根据饮食偏好、烹饪时间限制和当地杂货店供应情况生成个性化的每周餐食计划。该应用包括自动生成购物清单、分步烹饪指导以及与热门配送服务集成等功能..."
              />
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>
                  {charCount < 10
                    ? `还需要至少 ${10 - charCount} 个字`
                    : charCount > 500
                      ? `超出 ${charCount - 500} 个字`
                      : "字数适合分析"}
                </span>
                <span>建议 10-500 字</span>
              </div>
            </div>

            <Button type="submit" className="w-full" size="lg" disabled={!isValid || !description.trim()}>
              <Zap className="w-4 h-4 mr-2" />
              开始 5 分钟分析
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Example Ideas */}
      <div className="space-y-4">
        <h3 className="text-center text-lg font-semibold text-foreground">需要灵感？试试这些示例：</h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {examples.map((example, index) => (
            <Card
              key={index}
              className="cursor-pointer border border-border/70 bg-card/90 shadow-sm transition-all hover:-translate-y-1 hover:border-secondary/50 hover:shadow-lg"
              onClick={() => {
                setDescription(example.description)
                handleDescriptionChange({
                  target: { value: example.description },
                } as React.ChangeEvent<HTMLTextAreaElement>)
              }}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-secondary">{example.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground line-clamp-3">{example.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Process Timeline */}
      <div className="rounded-2xl border border-border bg-card/90 p-6 shadow-sm">
        <h3 className="mb-4 text-center text-lg font-semibold text-foreground">接下来会发生什么？</h3>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <div className="space-y-2 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary/10">
              <Clock className="h-6 w-6 text-secondary" />
            </div>
            <h4 className="font-medium text-foreground">步骤 1：分析</h4>
            <p className="text-sm text-muted-foreground">我们扫描相关的 Reddit 社区，寻找关于您市场的讨论</p>
          </div>
          <div className="space-y-2 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary/10">
              <Target className="h-6 w-6 text-secondary" />
            </div>
            <h4 className="font-medium text-foreground">步骤 2：处理</h4>
            <p className="text-sm text-muted-foreground">AI 分析用户痛点、竞品提及和市场机会</p>
          </div>
          <div className="space-y-2 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-secondary/10">
              <Lightbulb className="h-6 w-6 text-secondary" />
            </div>
            <h4 className="font-medium text-foreground">步骤 3：洞察</h4>
            <p className="text-sm text-muted-foreground">获得包含可操作商业洞察的综合报告</p>
          </div>
        </div>
      </div>
    </div>
  )
}
