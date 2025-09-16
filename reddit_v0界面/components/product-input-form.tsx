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

export default function ProductInputForm({ onStartAnalysis }: ProductInputFormProps) {
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
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header Section */}
      <div className="text-center space-y-4">
        <div className="flex items-center justify-center space-x-2 mb-4">
          <div className="w-12 h-12 bg-secondary/10 rounded-xl flex items-center justify-center">
            <Lightbulb className="w-6 h-6 text-secondary" />
          </div>
        </div>
        <h2 className="text-3xl font-bold text-foreground">描述您的产品想法</h2>
        <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
          详细告诉我们您的产品或服务。您描述得越具体，我们能提供的洞察就越好。
        </p>
      </div>

      {/* Main Input Form */}
      <Card className="border-2 border-dashed border-border hover:border-secondary/50 transition-colors">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <Target className="w-5 h-5 text-secondary" />
                <span>产品描述</span>
              </CardTitle>
              <CardDescription>包括您的目标受众、核心功能以及您要解决的问题</CardDescription>
            </div>
            <Badge variant={isValid ? "default" : "secondary"} className="ml-4">
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
                className="w-full min-h-40 p-4 border border-border rounded-lg bg-input text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all"
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
        <h3 className="text-lg font-semibold text-foreground text-center">需要灵感？试试这些示例：</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {examples.map((example, index) => (
            <Card
              key={index}
              className="cursor-pointer hover:shadow-md transition-shadow border-border hover:border-secondary/50"
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
      <div className="bg-card rounded-lg p-6 border border-border">
        <h3 className="text-lg font-semibold text-foreground mb-4 text-center">接下来会发生什么？</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 bg-secondary/10 rounded-full flex items-center justify-center mx-auto">
              <Clock className="w-6 h-6 text-secondary" />
            </div>
            <h4 className="font-medium text-foreground">步骤 1：分析</h4>
            <p className="text-sm text-muted-foreground">我们扫描相关的 Reddit 社区，寻找关于您市场的讨论</p>
          </div>
          <div className="text-center space-y-2">
            <div className="w-12 h-12 bg-secondary/10 rounded-full flex items-center justify-center mx-auto">
              <Target className="w-6 h-6 text-secondary" />
            </div>
            <h4 className="font-medium text-foreground">步骤 2：处理</h4>
            <p className="text-sm text-muted-foreground">AI 分析用户痛点、竞品提及和市场机会</p>
          </div>
          <div className="text-center space-y-2">
            <div className="w-12 h-12 bg-secondary/10 rounded-full flex items-center justify-center mx-auto">
              <Lightbulb className="w-6 h-6 text-secondary" />
            </div>
            <h4 className="font-medium text-foreground">步骤 3：洞察</h4>
            <p className="text-sm text-muted-foreground">获得包含可操作商业洞察的综合报告</p>
          </div>
        </div>
      </div>
    </div>
  )
}
