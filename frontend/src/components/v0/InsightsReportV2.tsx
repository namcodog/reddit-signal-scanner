"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import {
  Download,
  Share2,
  Users,
  AlertTriangle,
  Lightbulb,
  Target,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  BarChart3,
  Activity,
  ArrowLeft,
  Info,
  Star,
  Code2,
  DollarSign,
  TrendingUp,
  Swords,
} from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import ReportEvaluationDialog from "./ReportEvaluationDialog"
import type { V0AnalysisReport } from '@/services/v0-api-adapter';

interface InsightData {
  painPoints: Array<{
    title: string
    description: string
    severity: "high" | "medium" | "low"
    mentions: number
    examples: string[]
  }>
  competitors: Array<{
    name: string
    sentiment: "positive" | "negative" | "mixed"
    mentions: number
    strengths: string[]
    weaknesses: string[]
    marketShare: number
  }>
  opportunities: Array<{
    title: string
    description: string
    potential: "high" | "medium" | "low"
    difficulty: "easy" | "medium" | "hard"
    marketSize: string
    keyInsights: string[]
  }>
  marketMetrics: {
    totalMentions: number
    sentiment: {
      positive: number
      negative: number
      neutral: number
    }
    topCommunities: Array<{
      name: string
      members: number
      relevance: number
    }>
    trendingTopics: string[]
  }
}

interface InsightsReportProps {
  taskId: string
  productDescription: string
  onNewAnalysis: () => void
  reportData?: V0AnalysisReport | null
}
const DEFAULT_DATA: InsightData = {
  painPoints: [
    {
      title: "缺乏个性化推荐",
      description: "用户反映现有产品无法根据个人偏好提供精准推荐，导致用户体验不佳。",
      severity: "high",
      mentions: 342,
      examples: [
        "推荐的内容完全不符合我的兴趣，感觉算法很糟糕",
        "希望能有更智能的个性化功能，现在的推荐太泛泛了",
      ],
    },
    {
      title: "界面复杂难用",
      description: "多数用户认为现有产品界面过于复杂，学习成本高，影响使用体验。",
      severity: "medium",
      mentions: 198,
      examples: [
        "界面太复杂了，找个功能都要半天",
        "新手很难上手，需要更简洁的设计",
      ],
    },
  ],
  competitors: [
    {
      name: "竞品A",
      sentiment: "positive",
      mentions: 1247,
      strengths: ["用户界面友好", "功能丰富", "社区活跃"],
      weaknesses: ["价格偏高", "客服响应慢"],
      marketShare: 35,
    },
    {
      name: "竞品B",
      sentiment: "mixed",
      mentions: 892,
      strengths: ["价格实惠", "性能稳定"],
      weaknesses: ["功能有限", "更新频率低"],
      marketShare: 22,
    },
  ],
  opportunities: [
    {
      title: "AI驱动的个性化体验",
      description: "结合人工智能技术，提供更智能的个性化推荐和用户体验。",
      potential: "high",
      difficulty: "medium",
      marketSize: "10亿美元",
      keyInsights: ["AI技术成熟", "用户需求强烈", "竞争对手较少"],
    },
    {
      title: "移动端优化",
      description: "专注移动端体验优化，抓住移动互联网红利。",
      potential: "medium",
      difficulty: "easy",
      marketSize: "5亿美元",
      keyInsights: ["移动用户增长", "现有产品体验差", "技术门槛低"],
    },
  ],
  marketMetrics: {
    totalMentions: 2847,
    sentiment: {
      positive: 45,
      negative: 25,
      neutral: 30,
    },
    topCommunities: [
      { name: "r/entrepreneur", members: 1_200_000, relevance: 95 },
      { name: "r/startups", members: 800_000, relevance: 88 },
      { name: "r/SaaS", members: 450_000, relevance: 82 },
    ],
    trendingTopics: ["AI自动化", "用户体验", "移动优先", "数据隐私"],
  },
}

const severityBadgeClass: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-emerald-100 text-emerald-700",
}

const potentialBadgeClass: Record<string, string> = {
  high: "bg-emerald-100 text-emerald-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-slate-100 text-slate-700",
}

const difficultyBadgeClass: Record<string, string> = {
  easy: "bg-emerald-100 text-emerald-700",
  medium: "bg-yellow-100 text-yellow-700",
  hard: "bg-red-100 text-red-700",
}

const getSentimentIcon = (sentiment: string) => {
  switch (sentiment) {
    case "positive":
      return <ThumbsUp className="h-4 w-4 text-emerald-500" />
    case "negative":
      return <ThumbsDown className="h-4 w-4 text-red-500" />
    default:
      return <Activity className="h-4 w-4 text-yellow-500" />
  }
}

const renderDifficultyStars = (difficulty: string) => {
  const starCount = difficulty === "hard" ? 3 : difficulty === "medium" ? 2 : 1
  const starColor = difficulty === "hard" ? "text-red-500" : difficulty === "medium" ? "text-yellow-500" : "text-emerald-500"

  return (
    <div className="flex flex-col space-y-2">
      <div className="flex items-center gap-1">
        {Array.from({ length: 3 }, (_, index) => (
          <Star
            key={index}
            className={`h-4 w-4 ${index < starCount ? `${starColor} fill-current` : "text-slate-300"}`}
          />
        ))}
        <span className="ml-2 text-sm text-muted-foreground">
          {difficulty === "hard" ? "高难度" : difficulty === "medium" ? "中等难度" : "易实现"}
        </span>
      </div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><Code2 className="h-3 w-3" />技术</span>
        <span className="flex items-center gap-1"><DollarSign className="h-3 w-3" />资源</span>
        <span className="flex items-center gap-1"><TrendingUp className="h-3 w-3" />市场</span>
        <span className="flex items-center gap-1"><Swords className="h-3 w-3" />竞争</span>
      </div>
    </div>
  )
}
export default function InsightsReportV2({ taskId, productDescription, onNewAnalysis, reportData }: InsightsReportProps) {
  const [activeTab, setActiveTab] = useState("overview")
  const [showEvaluationDialog, setShowEvaluationDialog] = useState(false)

  // 将V0AnalysisReport转换为InsightData格式
  const data: InsightData = reportData ? {
    painPoints: reportData.pain_points,
    competitors: reportData.competitors.map(comp => ({
      ...comp,
      marketShare: comp.market_share // 字段名转换
    })),
    opportunities: reportData.opportunities.map(opp => ({
      ...opp,
      marketSize: opp.timeline || "未知", // 字段映射
      keyInsights: opp.key_factors || [] // 字段映射
    })),
    marketMetrics: {
      totalMentions: reportData.market_metrics.total_mentions,
      sentiment: {
        positive: 0.6, // 默认值，可以从reportData计算
        negative: 0.2,
        neutral: 0.2
      },
      topCommunities: reportData.market_metrics.top_communities.map(name => ({
        name,
        members: 10000, // 默认值
        relevance: 85 // 默认值
      })),
      trendingTopics: reportData.market_metrics.trending_keywords
    }
  } : DEFAULT_DATA
  const trendingTopics = data.marketMetrics.trendingTopics ?? []

  const handleStartNewAnalysis = () => {
    setShowEvaluationDialog(true)
  }

  const handleEvaluationComplete = () => {
    setShowEvaluationDialog(false)
    onNewAnalysis()
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={onNewAnalysis}
            className="h-auto w-fit px-0 text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="mr-2 h-4 w-4" /> 返回重新输入产品
          </Button>
          <div className="space-y-1">
            <h1 className="text-3xl font-semibold text-foreground">市场洞察报告</h1>
            <p className="text-sm text-muted-foreground">
              任务编号 #{taskId || "—"} · 已分析 {data.marketMetrics.totalMentions.toLocaleString()} 条社区提及
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm">
            <Share2 className="mr-2 h-4 w-4" /> 分享
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" /> 导出 PDF
          </Button>
          <Button size="sm" onClick={handleStartNewAnalysis}>
            <Lightbulb className="mr-2 h-4 w-4" /> 开始新分析
          </Button>
        </div>
      </div>

      <Card className="border border-secondary/20 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle>产品概览</CardTitle>
          <CardDescription>以下洞察基于您在上一流程提供的产品描述</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="rounded-lg bg-muted/50 p-4 text-sm leading-relaxed text-muted-foreground">
            {productDescription || "当前分析基于您输入的产品信息。"}
          </p>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-4">
        <Card className="shadow-sm">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary/10">
              <MessageSquare className="h-5 w-5 text-secondary" />
            </div>
            <div className="text-right">
              <p className="text-2xl font-semibold text-foreground">{data.marketMetrics.totalMentions.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">总提及</p>
            </div>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary/10">
              <Users className="h-5 w-5 text-secondary" />
            </div>
            <div className="text-right">
              <p className="text-2xl font-semibold text-foreground">{data.marketMetrics.topCommunities.length}</p>
              <p className="text-xs text-muted-foreground">核心社区</p>
            </div>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary/10">
              <AlertTriangle className="h-5 w-5 text-secondary" />
            </div>
            <div className="text-right">
              <p className="text-2xl font-semibold text-foreground">{data.painPoints.length}</p>
              <p className="text-xs text-muted-foreground">关键痛点</p>
            </div>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-secondary/10">
              <Lightbulb className="h-5 w-5 text-secondary" />
            </div>
            <div className="text-right">
              <p className="text-2xl font-semibold text-foreground">{data.opportunities.length}</p>
              <p className="text-xs text-muted-foreground">商业机会</p>
            </div>
          </CardContent>
        </Card>
      </div>
      <TooltipProvider>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">概览</TabsTrigger>
            <TabsTrigger value="pain-points">痛点分析</TabsTrigger>
            <TabsTrigger value="competitors">竞品分析</TabsTrigger>
            <TabsTrigger value="opportunities">商业机会</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <Card className="shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="h-5 w-5" /> 市场情感分布
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="h-4 w-4 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent>
                      数据来源于 Reddit 社区，反映用户对该领域的总体态度。正向代表支持与推荐，中性代表客观讨论，负向代表顾虑与改进需求。
                    </TooltipContent>
                  </Tooltip>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>正面</span>
                    <span className="font-medium text-emerald-600">{data.marketMetrics.sentiment.positive}%</span>
                  </div>
                  <Progress value={data.marketMetrics.sentiment.positive} />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>中性</span>
                    <span className="font-medium text-slate-600">{data.marketMetrics.sentiment.neutral}%</span>
                  </div>
                  <Progress value={data.marketMetrics.sentiment.neutral} />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>负面</span>
                    <span className="font-medium text-red-600">{data.marketMetrics.sentiment.negative}%</span>
                  </div>
                  <Progress value={data.marketMetrics.sentiment.negative} />
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="shadow-sm">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Users className="h-5 w-5" /> 热门社区
                  </CardTitle>
                  <CardDescription>与您产品最相关的讨论社区</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {data.marketMetrics.topCommunities.map((community: { name: string; members: number; relevance: number }) => (
                    <div
                      key={community.name}
                      className="flex items-center justify-between rounded-lg border border-border/70 bg-card/80 p-3"
                    >
                      <div>
                        <p className="font-medium text-foreground">{community.name}</p>
                        <p className="text-xs text-muted-foreground">{community.members.toLocaleString()} 名成员</p>
                      </div>
                      <Badge variant="secondary">相关度 {community.relevance}%</Badge>
                    </div>
                  ))}
                </CardContent>
              </Card>
              <Card className="shadow-sm">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <TrendingUp className="h-5 w-5" /> 讨论热词
                  </CardTitle>
                  <CardDescription>近期出现频次最高的主题标签</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  {trendingTopics.length > 0 ? (
                    trendingTopics.map((topic: string) => (
                      <span
                        key={topic}
                        className="rounded-full bg-secondary/10 px-3 py-1 text-xs font-medium text-secondary"
                      >
                        #{topic}
                      </span>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">暂无高频讨论主题</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
          <TabsContent value="pain-points" className="space-y-4">
            {data.painPoints.map((painPoint: InsightData['painPoints'][0]) => (
              <Card key={painPoint.title} className="shadow-sm">
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <AlertTriangle className="h-5 w-5 text-red-500" />
                      {painPoint.title}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      <Badge className={`${severityBadgeClass[painPoint.severity]} border-0`}>严重度</Badge>
                      <Badge variant="outline">{painPoint.mentions} 条提及</Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-sm leading-relaxed text-muted-foreground">{painPoint.description}</p>
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-foreground">用户原声：</h4>
                    <div className="space-y-2">
                      {painPoint.examples.map((example: string) => (
                        <blockquote
                          key={example}
                          className="border-l-4 border-secondary/40 bg-muted/40 px-3 py-2 text-sm italic text-muted-foreground"
                        >
                          “{example}”
                        </blockquote>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </TabsContent>

          <TabsContent value="competitors" className="space-y-4">
            {data.competitors.map((competitor: InsightData['competitors'][0]) => (
              <Card key={competitor.name} className="shadow-sm">
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Target className="h-5 w-5 text-secondary" />
                      {competitor.name}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      {getSentimentIcon(competitor.sentiment)}
                      <Badge variant="outline">{competitor.mentions} 条提及</Badge>
                      <Badge variant="secondary">市场份额 {competitor.marketShare}%</Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="grid gap-6 md:grid-cols-2">
                  <div className="space-y-2">
                    <h4 className="flex items-center gap-2 text-sm font-semibold text-emerald-600">
                      <ThumbsUp className="h-4 w-4" /> 优势
                    </h4>
                    <ul className="space-y-1 text-sm text-muted-foreground">
                      {competitor.strengths.map((item: string) => (
                        <li key={item}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="space-y-2">
                    <h4 className="flex items-center gap-2 text-sm font-semibold text-red-500">
                      <ThumbsDown className="h-4 w-4" /> 劣势
                    </h4>
                    <ul className="space-y-1 text-sm text-muted-foreground">
                      {competitor.weaknesses.map((item: string) => (
                        <li key={item}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>
            ))}
          </TabsContent>

          <TabsContent value="opportunities" className="space-y-4">
            {data.opportunities.map((opportunity: InsightData['opportunities'][0]) => (
              <Card key={opportunity.title} className="shadow-sm">
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Lightbulb className="h-5 w-5 text-secondary" />
                      {opportunity.title}
                    </CardTitle>
                    <div className="flex items-center gap-2">
                      <Badge className={`${potentialBadgeClass[opportunity.potential]} border-0`}>
                        {opportunity.potential === "high" ? "高潜力" : opportunity.potential === "medium" ? "中潜力" : "低潜力"}
                      </Badge>
                      <Badge className={`${difficultyBadgeClass[opportunity.difficulty]} border-0`}>
                        {opportunity.difficulty === "easy" ? "易实现" : opportunity.difficulty === "medium" ? "中等难度" : "高难度"}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="grid gap-6 md:grid-cols-2">
                  <div className="space-y-3">
                    <p className="text-sm leading-relaxed text-muted-foreground">{opportunity.description}</p>
                    <div className="flex items-center gap-2 text-sm font-medium text-secondary">
                      <DollarSign className="h-4 w-4" /> 市场规模：{opportunity.marketSize}
                    </div>
                    {renderDifficultyStars(opportunity.difficulty)}
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-foreground">关键洞察：</h4>
                    <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                      {opportunity.keyInsights.map((insight: string) => (
                        <li key={insight}>• {insight}</li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>
            ))}
          </TabsContent>
        </Tabs>
      </TooltipProvider>

      <ReportEvaluationDialog
        open={showEvaluationDialog}
        onOpenChange={setShowEvaluationDialog}
        onEvaluationComplete={handleEvaluationComplete}
      />
    </div>
  )
}
