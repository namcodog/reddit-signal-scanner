"use client"

import { Tooltip, TooltipTrigger, TooltipProvider, TooltipContent } from "@/components/ui/tooltip"
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

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import ReportEvaluationDialog from "./report-evaluation-dialog"

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
  analysisId: string
  productDescription: string
  onNewAnalysis: () => void
  mockData?: InsightData // Made mockData optional
}

export default function InsightsReport({
  analysisId,
  productDescription,
  onNewAnalysis,
  mockData,
}: InsightsReportProps) {
  const [activeTab, setActiveTab] = useState("overview")
  const [showEvaluationDialog, setShowEvaluationDialog] = useState(false)

  const defaultData: InsightData = {
    painPoints: [
      {
        title: "缺乏个性化推荐",
        description: "用户反映现有产品无法根据个人偏好提供精准推荐，导致用户体验不佳。",
        severity: "high",
        mentions: 342,
        examples: [
          "推荐的内容完全不符合我的兴趣，感觉算法很糟糕",
          "希望能有更智能的个性化功能，现在的推荐太泛泛了",
          "用了这么久还是推荐一些我不感兴趣的东西",
        ],
      },
      {
        title: "界面操作复杂",
        description: "新用户学习成本高，界面设计不够直观，影响用户留存率。",
        severity: "medium",
        mentions: 198,
        examples: [
          "界面太复杂了，找个功能要点好多次",
          "新手教程不够清楚，很多功能不知道怎么用",
          "希望界面能更简洁一些，现在看起来很乱",
        ],
      },
      {
        title: "价格透明度不足",
        description: "用户对定价策略不满，希望有更清晰的价格说明和更多选择。",
        severity: "medium",
        mentions: 156,
        examples: [
          "价格不够透明，总有一些隐藏费用",
          "希望能有更多的套餐选择，现在的价格对我来说太贵了",
          "定价策略不清楚，不知道什么时候会涨价",
        ],
      },
    ],
    competitors: [
      {
        name: "Product Hunt平台",
        sentiment: "positive",
        mentions: 1247,
        strengths: ["社区活跃度高", "产品发现机制完善", "用户参与度强"],
        weaknesses: ["商业化程度不够", "对中文产品支持有限", "缺乏深度分析功能"],
        marketShare: 35,
      },
      {
        name: "BetaList平台",
        sentiment: "mixed",
        mentions: 892,
        strengths: ["早期产品聚焦", "邮件订阅系统完善", "界面简洁"],
        weaknesses: ["用户基数较小", "缺乏社交功能", "更新频率不够"],
        marketShare: 18,
      },
      {
        name: "Indie Hackers社区",
        sentiment: "positive",
        mentions: 756,
        strengths: ["创业者社区氛围好", "经验分享丰富", "商业化指导强"],
        weaknesses: ["技术门槛较高", "非技术用户参与度低", "内容质量参差不齐"],
        marketShare: 22,
      },
    ],
    opportunities: [
      {
        title: "AI驱动的个性化推荐",
        description: "基于用户行为和偏好数据，开发智能推荐算法，提供个性化的产品发现体验。",
        potential: "high",
        difficulty: "medium",
        marketSize: "$2.3B",
        keyInsights: [
          "67%的用户表示愿意为个性化推荐付费",
          "AI推荐可以提升用户留存率35%",
          "个性化功能是用户最期待的新特性",
          "竞品在这方面投入不足，存在市场空白",
        ],
      },
      {
        title: "中文市场本土化",
        description: "针对中文用户习惯和需求，开发本土化的产品发现和社区功能。",
        potential: "high",
        difficulty: "easy",
        marketSize: "$890M",
        keyInsights: [
          "中文市场缺乏优质的产品发现平台",
          "本土化需求强烈，用户愿意尝试新产品",
          "可以与国内创业孵化器合作获得流量",
          "移动端优先的设计更符合中文用户习惯",
        ],
      },
      {
        title: "企业级SaaS工具集成",
        description: "为B2B用户提供企业级功能，包括团队协作、数据分析和API接入。",
        potential: "medium",
        difficulty: "hard",
        marketSize: "$1.2B",
        keyInsights: [
          "B2B用户付费意愿更强，客单价更高",
          "企业用户需要更深度的数据分析功能",
          "API集成可以创造额外的收入来源",
          "需要投入较多的技术和销售资源",
        ],
      },
    ],
    marketMetrics: {
      totalMentions: 15847,
      sentiment: {
        positive: 58,
        negative: 23,
        neutral: 19,
      },
      topCommunities: [
        {
          name: "r/startups",
          members: 1200000,
          relevance: 89,
        },
        {
          name: "r/entrepreneur",
          members: 980000,
          relevance: 76,
        },
        {
          name: "r/SaaS",
          members: 450000,
          relevance: 82,
        },
        {
          name: "r/ProductManagement",
          members: 320000,
          relevance: 71,
        },
        {
          name: "r/webdev",
          members: 890000,
          relevance: 64,
        },
      ],
      trendingTopics: ["AI产品推荐", "用户体验优化", "个性化算法", "产品发现", "创业工具"],
    },
  }

  const reportData = mockData || defaultData

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "high":
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
      case "medium":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
      case "low":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200"
    }
  }

  const getPotentialColor = (potential: string) => {
    switch (potential) {
      case "high":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
      case "medium":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
      case "low":
        return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200"
    }
  }

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case "positive":
        return <ThumbsUp className="w-4 h-4 text-green-500" />
      case "negative":
        return <ThumbsDown className="w-4 h-4 text-red-500" />
      case "mixed":
        return <Activity className="w-4 h-4 text-yellow-500" />
      default:
        return <Activity className="w-4 h-4 text-gray-500" />
    }
  }

  const handleNewAnalysisClick = () => {
    setShowEvaluationDialog(true)
  }

  const handleEvaluationComplete = () => {
    onNewAnalysis()
  }

  const getDifficultyText = (difficulty: string) => {
    switch (difficulty) {
      case "easy":
        return "综合实现难度为简单"
      case "medium":
        return "综合实现难度为中等"
      case "hard":
        return "综合实现难度为困难"
      default:
        return "综合实现难度为中等"
    }
  }

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case "easy":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
      case "medium":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
      case "hard":
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
      default:
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
    }
  }

  const renderDifficultyStars = (difficulty: string) => {
    const getStarCount = () => {
      switch (difficulty) {
        case "easy":
          return 1
        case "medium":
          return 2
        case "hard":
          return 3
        default:
          return 1
      }
    }

    const getStarColor = () => {
      switch (difficulty) {
        case "easy":
          return "text-green-500"
        case "medium":
          return "text-yellow-500"
        case "hard":
          return "text-red-500"
        default:
          return "text-gray-500"
      }
    }

    const starCount = getStarCount()
    const starColor = getStarColor()

    return (
      <div className="flex flex-col space-y-2">
        <div className="flex items-center space-x-1">
          {Array.from({ length: 3 }, (_, index) => (
            <Star
              key={index}
              className={`w-4 h-4 ${index < starCount ? `${starColor} fill-current` : "text-gray-300"}`}
            />
          ))}
          <span className="text-sm text-muted-foreground ml-2">
            {difficulty === "easy" ? "简单" : difficulty === "medium" ? "中等" : "困难"}
          </span>
        </div>
        <div className="flex items-center space-x-3 text-xs text-muted-foreground">
          <div className="flex items-center space-x-1" title="技术实现难度">
            <Code2 className="w-3 h-3" />
            <span>技术</span>
          </div>
          <div className="flex items-center space-x-1" title="资源投入难度">
            <DollarSign className="w-3 h-3" />
            <span>资源</span>
          </div>
          <div className="flex items-center space-x-1" title="市场进入难度">
            <TrendingUp className="w-3 h-3" />
            <span>市场</span>
          </div>
          <div className="flex items-center space-x-1" title="竞争激烈程度">
            <Swords className="w-3 h-3" />
            <span>竞争</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <h2 className="text-3xl font-bold text-foreground">市场洞察报告</h2>
          <p className="text-muted-foreground">
            分析已完成 • 已分析 {reportData.marketMetrics.totalMentions.toLocaleString()} 条提及
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm">
            <Share2 className="w-4 h-4 mr-2" />
            分享
          </Button>
          <Button variant="outline" size="sm">
            <Download className="w-4 h-4 mr-2" />
            导出PDF
          </Button>
          <Button size="sm" onClick={handleNewAnalysisClick}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            开始新分析
          </Button>
        </div>
      </div>

      {/* Product Summary */}
      <Card className="border-secondary/20">
        <CardHeader>
          <CardTitle>已分析产品</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">{productDescription}</p>
        </CardContent>
      </Card>

      {/* Key Metrics Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-8 h-8 bg-secondary/10 rounded-lg flex items-center justify-center mx-auto mb-2">
              <MessageSquare className="w-4 h-4 text-secondary" />
            </div>
            <div className="text-2xl font-bold text-foreground">
              {reportData.marketMetrics.totalMentions.toLocaleString()}
            </div>
            <p className="text-sm text-muted-foreground">总提及数</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-2">
              <ThumbsUp className="w-4 h-4 text-green-600" />
            </div>
            <div className="text-2xl font-bold text-foreground">{reportData.marketMetrics.sentiment.positive}%</div>
            <p className="text-sm text-muted-foreground">正面情感</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-8 h-8 bg-secondary/10 rounded-lg flex items-center justify-center mx-auto mb-2">
              <Users className="w-4 h-4 text-secondary" />
            </div>
            <div className="text-2xl font-bold text-foreground">{reportData.marketMetrics.topCommunities.length}</div>
            <p className="text-sm text-muted-foreground">社区数量</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 text-center">
            <div className="w-8 h-8 bg-secondary/10 rounded-lg flex items-center justify-center mx-auto mb-2">
              <Lightbulb className="w-4 h-4 text-secondary" />
            </div>
            <div className="text-2xl font-bold text-foreground">{reportData.opportunities.length}</div>
            <p className="text-sm text-muted-foreground">商业机会</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="pain-points">用户痛点</TabsTrigger>
          <TabsTrigger value="competitors">竞品分析</TabsTrigger>
          <TabsTrigger value="opportunities">商业机会</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Sentiment Analysis */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <BarChart3 className="w-5 h-5 text-secondary" />
                <span>市场情感</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="w-4 h-4 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p>
                        市场情感反映了Reddit用户对相关产品和服务的整体态度。正面情感表示用户满意度和推荐意愿，负面情感揭示用户不满和改进需求，中性情感代表客观讨论。这些数据帮助您了解市场对您产品领域的真实反应。
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>正面</span>
                  <span>{reportData.marketMetrics.sentiment.positive}%</span>
                </div>
                <Progress value={reportData.marketMetrics.sentiment.positive} className="h-2" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>负面</span>
                  <span>{reportData.marketMetrics.sentiment.negative}%</span>
                </div>
                <Progress value={reportData.marketMetrics.sentiment.negative} className="h-2" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>中性</span>
                  <span>{reportData.marketMetrics.sentiment.neutral}%</span>
                </div>
                <Progress value={reportData.marketMetrics.sentiment.neutral} className="h-2" />
              </div>
            </CardContent>
          </Card>

          {/* Top Communities */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <Users className="w-5 h-5 text-secondary" />
                <span>热门社区</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {reportData.marketMetrics.topCommunities.map((community, index) => (
                  <div key={index} className="flex items-center justify-between p-3 border border-border rounded-lg">
                    <div>
                      <h4 className="font-medium text-foreground">{community.name}</h4>
                      <p className="text-sm text-muted-foreground">{community.members.toLocaleString()} 成员</p>
                    </div>
                    <Badge variant="secondary">{community.relevance}% 相关</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pain-points" className="space-y-6">
          {reportData.painPoints.map((painPoint, index) => (
            <Card key={index}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center space-x-2">
                    <AlertTriangle className="w-5 h-5 text-red-500" />
                    <span>{painPoint.title}</span>
                  </CardTitle>
                  <div className="flex items-center space-x-2">
                    <Badge className={getSeverityColor(painPoint.severity)}>
                      {painPoint.severity === "high" ? "高" : painPoint.severity === "medium" ? "中" : "低"}
                    </Badge>
                    <Badge variant="outline">{painPoint.mentions} 条帖子提及</Badge>
                  </div>
                </div>
                <CardDescription>{painPoint.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <h4 className="font-medium text-foreground">用户示例：</h4>
                  {painPoint.examples.map((example, exampleIndex) => (
                    <blockquote
                      key={exampleIndex}
                      className="border-l-4 border-secondary/50 pl-4 italic text-muted-foreground"
                    >
                      "{example}"
                    </blockquote>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="competitors" className="space-y-6">
          {reportData.competitors.map((competitor, index) => (
            <Card key={index}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center space-x-2">
                    <Target className="w-5 h-5 text-secondary" />
                    <span>{competitor.name}</span>
                  </CardTitle>
                  <div className="flex items-center space-x-2">
                    {getSentimentIcon(competitor.sentiment)}
                    <Badge variant="outline">{competitor.mentions} 条帖子提及</Badge>
                    <Badge variant="secondary">{competitor.marketShare}% 市场份额</Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-medium text-green-600 mb-2">优势</h4>
                    <ul className="space-y-1">
                      {competitor.strengths.map((strength, strengthIndex) => (
                        <li key={strengthIndex} className="text-sm text-muted-foreground flex items-center space-x-2">
                          <ThumbsUp className="w-3 h-3 text-green-500" />
                          <span>{strength}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4 className="font-medium text-red-600 mb-2">劣势</h4>
                    <ul className="space-y-1">
                      {competitor.weaknesses.map((weakness, weaknessIndex) => (
                        <li key={weaknessIndex} className="text-sm text-muted-foreground flex items-center space-x-2">
                          <ThumbsDown className="w-3 h-3 text-red-500" />
                          <span>{weakness}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="opportunities" className="space-y-6">
          {reportData.opportunities.map((opportunity, index) => (
            <Card key={index}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center space-x-2">
                    <Lightbulb className="w-5 h-5 text-secondary" />
                    <span>{opportunity.title}</span>
                  </CardTitle>
                </div>
                <CardDescription>{opportunity.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <h4 className="font-medium text-foreground">关键洞察：</h4>
                  <ul className="space-y-2">
                    {opportunity.keyInsights.map((insight, insightIndex) => (
                      <li key={insightIndex} className="text-sm text-muted-foreground flex items-start space-x-2">
                        <div className="w-1.5 h-1.5 bg-secondary rounded-full mt-2 flex-shrink-0" />
                        <span>{insight}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>

      {/* Evaluation Dialog */}
      <ReportEvaluationDialog
        open={showEvaluationDialog}
        onOpenChange={setShowEvaluationDialog}
        onEvaluationComplete={handleEvaluationComplete}
      />
    </div>
  )
}
