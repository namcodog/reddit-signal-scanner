import React, { useMemo, useState, useEffect } from 'react';
import { Tooltip, TooltipTrigger, TooltipProvider, TooltipContent } from '@/components/ui/tooltip';
import { Users, AlertTriangle, Lightbulb, MessageSquare, ThumbsUp, ThumbsDown, BarChart3, Activity, Info, Star, DollarSign, TrendingUp, Swords } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import ReportEvaluationDialog from '@/components/v0/ReportEvaluationDialog';
import { trackReportFirstPaint, trackReportViewed } from '@/services/feedback.service';
import type {
  ReportData,
  PainPointInsight as ReportPainPointInsight,
  CompetitorInsight as ReportCompetitorInsight,
  OpportunityInsight as ReportOpportunityInsight,
  ExecutiveSummary
} from '@/types/contracts/report.contract';

interface InsightData {
  painPoints: Array<{
    title: string;
    description: string;
    severity: 'high' | 'medium' | 'low';
    mentions: number;
    examples: string[];
  }>;
  competitors: Array<{
    name: string;
    sentiment: 'positive' | 'negative' | 'mixed';
    mentions: number;
    strengths: string[];
    weaknesses: string[];
    marketShare: number;
    summary?: string;
  }>;
  opportunities: Array<{
    title: string;
    description: string;
    potential: 'high' | 'medium' | 'low';
    difficulty: 'easy' | 'medium' | 'hard';
    marketSize: string;
    keyInsights: string[];
    timeframe?: string;
  }>;
  marketMetrics: {
    totalMentions: number;
    sentiment: { positive: number; negative: number; neutral: number };
    topCommunities: Array<{ name: string; members?: number; relevance?: number }>;
    trendingTopics: string[];
  };
  executiveSummary: {
    headline: string | null;
    summaryPoints: string[];
    confidenceScore: number | null;
    totalCommunities: number;
    topOpportunity: string | null;
  };
}

interface InsightsReportProps {
  taskId: string;
  productDescription: string;
  onNewAnalysis: () => void;
  reportData?: ReportData | null;
}
const normalizeSentiment = (
  summary: Record<string, number> | undefined,
  fallbackScore: number
): { positive: number; neutral: number; negative: number } => {
  if (summary && Object.keys(summary).length > 0) {
    const positiveRaw = summary.positive ?? 0;
    const neutralRaw = summary.neutral ?? 0;
    const negativeRaw = summary.negative ?? 0;
    const total = positiveRaw + neutralRaw + negativeRaw;
    if (total > 0) {
      const positive = Math.round((positiveRaw / total) * 100);
      const negative = Math.round((negativeRaw / total) * 100);
      const neutral = Math.max(0, 100 - positive - negative);
      return { positive, negative, neutral };
    }
  }

  const positive = Math.round(((fallbackScore + 1) / 2) * 100);
  const negative = Math.max(0, 100 - positive);
  const neutral = Math.max(0, 100 - positive - negative);
  return {
    positive: Math.max(0, Math.min(100, positive)),
    negative: Math.max(0, Math.min(100, negative)),
    neutral: Math.max(0, Math.min(100, neutral))
  };
};

const deriveSeverity = (
  severity: ReportPainPointInsight['severity'] | undefined,
  sentimentScore: number,
  frequency: number
): 'high' | 'medium' | 'low' => {
  if (severity === 'high' || severity === 'medium' || severity === 'low') {
    return severity;
  }
  if (frequency >= 50 || sentimentScore <= -0.6) {
    return 'high';
  }
  if (frequency >= 20 || sentimentScore <= -0.3) {
    return 'medium';
  }
  return 'low';
};



const mapPainPointsFromReport = (
  items: ReportPainPointInsight[]
): InsightData['painPoints'] => {
  return items.slice(0, 6).map((item, index) => {
    const title =
      (item.tags && item.tags[0]) ||
      (item.categories && item.categories[0]) ||
      `痛点 #${index + 1}`;
    const severity = deriveSeverity(item.severity, item.sentiment_score, item.frequency);
    const examples = item.example_posts?.map(post =>
      post.content_snippet || post.permalink || post.post_id || '暂无内容'
    ).filter(Boolean) || ['暂无示例，等待更多数据'];

    return {
      title,
      description: item.description,
      severity,
      mentions: item.frequency,
      examples,
    };
  });
};

const mapCompetitorSentiment = (
  score: number
): 'positive' | 'negative' | 'mixed' => {
  if (score > 0.2) {
    return 'positive';
  }
  if (score < -0.2) {
    return 'negative';
  }
  return 'mixed';
};

const mapCompetitorsFromReport = (
  items: ReportCompetitorInsight[]
): InsightData['competitors'] => {
  const totalMentions = items.reduce(
    (acc, item) => acc + (item.mention_count ?? 0),
    0
  );
  return items.slice(0, 6).map((item) => {
    const sentiment = mapCompetitorSentiment(item.sentiment_score ?? 0);
    const share =
      item.share_of_voice !== undefined
        ? item.share_of_voice * 100
        : totalMentions > 0
        ? (item.mention_count / totalMentions) * 100
        : 0;
    return {
      name: item.name,
      sentiment,
      mentions: item.mention_count,
      strengths: item.strengths ?? [],
      weaknesses: item.weaknesses ?? [],
      marketShare: Math.round(Math.max(0, Math.min(100, share))),
      summary: item.summary ?? undefined,
    };
  });
};

const mapOpportunityPotential = (
  indicator: ReportOpportunityInsight['market_size_indicator'],
  potentialScore?: number
): 'high' | 'medium' | 'low' => {
  if (indicator === 'huge' || indicator === 'large') {
    return 'high';
  }
  if (indicator === 'medium') {
    return 'medium';
  }
  if (indicator === 'tiny' || indicator === 'small') {
    return 'low';
  }
  if (typeof potentialScore === 'number') {
    if (potentialScore >= 0.7) {
      return 'high';
    }
    if (potentialScore >= 0.4) {
      return 'medium';
    }
    return 'low';
  }
  return 'medium';
};

const mapOpportunityDifficulty = (score: number): 'easy' | 'medium' | 'hard' => {
  if (score >= 0.7) {
    return 'easy';
  }
  if (score >= 0.4) {
    return 'medium';
  }
  return 'hard';
};

const mapMarketSizeLabel = (
  indicator: ReportOpportunityInsight['market_size_indicator']
): string => {
  switch (indicator) {
    case 'huge':
      return '万亿级市场';
    case 'large':
      return '大型市场';
    case 'medium':
      return '中型市场';
    case 'small':
      return '小型市场';
    case 'tiny':
      return '利基市场';
    default:
      return '规模待评估';
  }
};

const mapOpportunitiesFromReport = (
  items: ReportOpportunityInsight[]
): InsightData['opportunities'] => {
  return items.slice(0, 6).map((item) => {
    const potential = mapOpportunityPotential(
      item.market_size_indicator,
      item.potential_score
    );
    const difficulty = mapOpportunityDifficulty(item.feasibility_score ?? 0);
    const keyInsights =
      (item.related_keywords && item.related_keywords.length > 0
        ? item.related_keywords
        : item.target_communities) ?? [];
    return {
      title: item.title,
      description: item.description,
      potential,
      difficulty,
      marketSize: mapMarketSizeLabel(item.market_size_indicator),
      keyInsights: keyInsights.slice(0, 6),
      timeframe: item.timeframe ?? undefined,
    };
  });
};

const mapMarketMetricsFromReport = (report: ReportData): InsightData['marketMetrics'] => {
  const sentiment = normalizeSentiment(
    report.sentiment_summary,
    report.market_metrics?.sentiment_score ?? 0
  );
  const trendingTopics =
    (report.market_metrics?.trending_keywords?.length ?? 0) > 0
      ? report.market_metrics.trending_keywords
      : report.trending_topics ?? [];
  const topCommunities =
    report.market_metrics?.top_communities?.map((name, index) => ({
      name,
      members: undefined,
      relevance:
        report.market_metrics?.engagement_rate !== undefined
          ? Math.round(
              Math.max(
                0,
                Math.min(100, report.market_metrics.engagement_rate * 100 - index * 5)
              )
            )
          : undefined,
    })) ?? [];
  return {
    totalMentions:
      report.market_metrics?.total_mentions ??
      report.total_posts + report.total_comments,
    sentiment,
    topCommunities,
    trendingTopics,
  };
};

const mapExecutiveSummaryFromReport = (
  summary: ExecutiveSummary | undefined
): InsightData['executiveSummary'] => ({
  headline: summary?.headline ?? null,
  summaryPoints: summary?.summary_points ?? [],
  confidenceScore:
    summary?.confidence_score !== undefined && summary?.confidence_score !== null
      ? summary.confidence_score
      : null,
  totalCommunities: summary?.total_communities ?? 0,
  topOpportunity: summary?.top_opportunity ?? null,
});

const buildInsightData = (report: ReportData | null | undefined): InsightData | null => {
  if (!report) {
    return null;
  }

  return {
    painPoints: mapPainPointsFromReport(report.pain_points ?? []),
    competitors: mapCompetitorsFromReport(report.competitors ?? []),
    opportunities: mapOpportunitiesFromReport(report.opportunities ?? []),
    marketMetrics: mapMarketMetricsFromReport(report),
    executiveSummary: mapExecutiveSummaryFromReport(report.executive_summary),
  };
};

const InsightsReport: React.FC<InsightsReportProps> = ({ taskId, productDescription, onNewAnalysis, reportData }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [showEvaluationDialog, setShowEvaluationDialog] = useState(false);
  const [firstPaintTracked, setFirstPaintTracked] = useState(false);

  const data = useMemo(() => buildInsightData(reportData ?? null), [reportData]);

  // 性能埋点：首屏渲染完成
  useEffect(() => {
    if (data && !firstPaintTracked) {
      const paintTime = performance.now();
      trackReportFirstPaint(taskId, Math.round(paintTime));
      trackReportViewed(taskId, 'full');
      setFirstPaintTracked(true);
    }
  }, [data, taskId, firstPaintTracked]);



  // 骨架屏组件
  const ReportSkeleton = () => (
    <div className="space-y-8">
      {/* Header Skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-8 w-48 bg-muted animate-pulse rounded"></div>
          <div className="h-4 w-64 bg-muted animate-pulse rounded"></div>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-9 w-20 bg-muted animate-pulse rounded"></div>
          <div className="h-9 w-24 bg-muted animate-pulse rounded"></div>
        </div>
      </div>

      {/* Overview Cards Skeleton */}
      <div className="grid gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <div className="h-5 w-5 bg-muted animate-pulse rounded"></div>
                <div>
                  <div className="h-6 w-16 bg-muted animate-pulse rounded mb-1"></div>
                  <div className="h-4 w-20 bg-muted animate-pulse rounded"></div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs Skeleton */}
      <div className="space-y-4">
        <div className="flex space-x-1 bg-muted p-1 rounded-lg w-fit">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-8 w-20 bg-background animate-pulse rounded"></div>
          ))}
        </div>

        {/* Content Cards Skeleton */}
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-5 w-5 bg-muted animate-pulse rounded"></div>
                    <div className="h-6 w-32 bg-muted animate-pulse rounded"></div>
                  </div>
                  <div className="flex gap-2">
                    <div className="h-6 w-16 bg-muted animate-pulse rounded"></div>
                    <div className="h-6 w-20 bg-muted animate-pulse rounded"></div>
                  </div>
                </div>
                <div className="h-4 w-full bg-muted animate-pulse rounded"></div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="h-4 w-3/4 bg-muted animate-pulse rounded"></div>
                  <div className="h-4 w-1/2 bg-muted animate-pulse rounded"></div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );

  // 空状态组件
  const EmptyState = () => (
    <div className="space-y-8">
      <Card>
        <CardContent className="p-8 text-center">
          <div className="mx-auto w-16 h-16 bg-muted rounded-full flex items-center justify-center mb-4">
            <BarChart3 className="h-8 w-8 text-muted-foreground" />
          </div>
          <CardTitle className="text-lg font-semibold mb-2">暂无洞察数据</CardTitle>
          <CardDescription className="text-sm text-muted-foreground mb-4">
            当前任务尚未生成洞察详情，请稍后重试或重新触发分析。
          </CardDescription>
          <Button variant="outline" onClick={onNewAnalysis}>
            重新分析
          </Button>
        </CardContent>
      </Card>
    </div>
  );

  // 根据数据状态渲染不同内容
  if (!reportData) {
    return <ReportSkeleton />;
  }

  if (!data) {
    return <EmptyState />;
  }

  return (
    <div className="space-y-8">
      <Card>
        <CardContent className="flex flex-col gap-3 p-6">
          <div>
            <CardTitle className="text-lg font-semibold">分析编号</CardTitle>
            <CardDescription className="text-sm text-muted-foreground">{taskId}</CardDescription>
          </div>
          {productDescription && (
            <div>
              <CardTitle className="text-lg font-semibold">产品描述</CardTitle>
              <CardDescription className="text-sm text-muted-foreground leading-relaxed">
                {productDescription}
              </CardDescription>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="p-4 text-center">
            <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-secondary/20">
              <MessageSquare className="h-4 w-4 text-secondary" />
            </div>
            <div className="text-2xl font-bold text-foreground">{data.marketMetrics.totalMentions.toLocaleString()}</div>
            <p className="text-sm text-muted-foreground">总讨论量</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-secondary/20">
              <BarChart3 className="h-4 w-4 text-secondary" />
            </div>
            <div className="text-2xl font-bold text-foreground">{data.marketMetrics.sentiment.positive}%</div>
            <p className="text-sm text-muted-foreground">正面情感</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-secondary/20">
              <Users className="h-4 w-4 text-secondary" />
            </div>
            <div className="text-2xl font-bold text-foreground">{data.marketMetrics.topCommunities.length}</div>
            <p className="text-sm text-muted-foreground">重点社区</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-secondary/20">
              <Lightbulb className="h-4 w-4 text-secondary" />
            </div>
            <div className="text-2xl font-bold text-foreground">{data.opportunities.length}</div>
            <p className="text-sm text-muted-foreground">商业机会</p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 gap-2 p-1 md:grid-cols-4">
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="pain-points">用户痛点</TabsTrigger>
          <TabsTrigger value="competitors">竞品分析</TabsTrigger>
          <TabsTrigger value="opportunities">商业机会</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Info className="h-5 w-5 text-secondary" />
                <span>执行摘要</span>
              </CardTitle>
              {data.executiveSummary.headline && (
                <CardDescription>{data.executiveSummary.headline}</CardDescription>
              )}
            </CardHeader>
            <CardContent className="space-y-3">
              {data.executiveSummary.summaryPoints.length > 0 ? (
                <ul className="list-disc list-inside space-y-2 text-sm text-muted-foreground">
                  {data.executiveSummary.summaryPoints.map((point, index) => (
                    <li key={index}>{point}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">摘要要点待补充。</p>
              )}
              <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                <span>覆盖社区：{data.executiveSummary.totalCommunities}</span>
                {data.executiveSummary.topOpportunity && (
                  <span>
                    顶级机会：
                    <span className="font-medium text-foreground ml-1">
                      {data.executiveSummary.topOpportunity}
                    </span>
                  </span>
                )}
                {typeof data.executiveSummary.confidenceScore === 'number' && (
                  <span>
                    总体置信度：
                    <span className="font-medium text-foreground ml-1">
                      {Math.round(data.executiveSummary.confidenceScore * 100)}%
                    </span>
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-secondary" />
                <span>市场情感</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-4 w-4 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-sm">
                      基于最近采集的 Reddit 讨论，展示各情绪类别所占比例。
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm"><span>正面</span><span>{data.marketMetrics.sentiment.positive}%</span></div>
                <Progress value={data.marketMetrics.sentiment.positive} className="h-2" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm"><span>负面</span><span>{data.marketMetrics.sentiment.negative}%</span></div>
                <Progress value={data.marketMetrics.sentiment.negative} className="h-2" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm"><span>中性</span><span>{data.marketMetrics.sentiment.neutral}%</span></div>
                <Progress value={data.marketMetrics.sentiment.neutral} className="h-2" />
              </div>
              {data.marketMetrics.trendingTopics.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-foreground">热门话题</h4>
                  <div className="flex flex-wrap gap-2">
                    {data.marketMetrics.trendingTopics.map((topic, idx) => (
                      <Badge key={idx} variant="secondary">{topic}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-secondary" />
                <span>热门社区</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {data.marketMetrics.topCommunities.map((community, index) => (
                  <div key={index} className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <h4 className="font-medium text-foreground">{community.name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {typeof community.members === 'number'
                          ? `${community.members.toLocaleString()} 成员`
                          : '成员数据待同步'}
                      </p>
                    </div>
                    <Badge variant="secondary">
                      {community.relevance !== undefined ? `${community.relevance}% 相关` : '相关度待同步'}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pain-points" className="space-y-6">
          {data.painPoints.map((painPoint, index) => (
            <Card key={index} className="transition-transform duration-200 hover:-translate-y-1 hover:shadow-[var(--shadow-soft)]">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    <span>{painPoint.title}</span>
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge className={getSeverityColor(painPoint.severity)}>
                      {painPoint.severity === 'high' ? '高' : painPoint.severity === 'medium' ? '中' : '低'}
                    </Badge>
                    <Badge variant="outline">{painPoint.mentions} 条帖子提及</Badge>
                  </div>
                </div>
                <CardDescription>{painPoint.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <h4 className="font-medium text-foreground">用户示例：</h4>
                  {painPoint.examples.map((example, i) => (
                    <blockquote key={i} className="border-l-4 border-secondary/40 pl-4 text-sm italic text-muted-foreground">
                      “{example}”
                    </blockquote>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="competitors" className="space-y-6">
          {data.competitors.map((competitor, index) => (
            <Card key={index} className="transition-transform duration-200 hover:-translate-y-1 hover:shadow-[var(--shadow-soft)]">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Swords className="h-5 w-5 text-secondary" />
                    <span>{competitor.name}</span>
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{competitor.marketShare}% 声量</Badge>
                    <Badge variant="outline">{competitor.mentions} 条提及</Badge>
                    {getSentimentIcon(competitor.sentiment)}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-2">
                <div>
                  <h4 className="font-medium mb-2">优势</h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                    {competitor.strengths.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium mb-2">劣势</h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                    {competitor.weaknesses.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
                {competitor.summary && (
                  <div className="md:col-span-2 rounded-lg bg-muted/40 p-4 text-sm text-muted-foreground">
                    {competitor.summary}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="opportunities" className="space-y-6">
          {data.opportunities.map((opportunity, index) => (
            <Card key={index} className="transition-transform duration-200 hover:-translate-y-1 hover:shadow-[var(--shadow-soft)]">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-secondary" />
                    <span>{opportunity.title}</span>
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge className={getPotentialColor(opportunity.potential)}>{opportunity.potential}</Badge>
                    <Badge className={getDifficultyColor(opportunity.difficulty)}>{getDifficultyText(opportunity.difficulty)}</Badge>
                  </div>
                </div>
                <CardDescription>{opportunity.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>市场规模</span>
                  <span className="flex items-center gap-1 font-medium text-foreground">
                    <DollarSign className="h-4 w-4 text-muted-foreground" />
                    {opportunity.marketSize}
                  </span>
                </div>
                <div className="space-y-2">
                  <h4 className="font-medium">关键洞察</h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                    {opportunity.keyInsights.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div className="flex items-center justify-between text-sm text-muted-foreground">
                  <span>综合实现难度</span>
                  {renderDifficultyStars(opportunity.difficulty)}
                </div>
                {opportunity.timeframe && (
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>预计落地窗口</span>
                    <span className="font-medium text-foreground">{opportunity.timeframe}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </TabsContent>
      </Tabs>

      <div className="flex justify-end">
        <Button variant="outline" onClick={() => setShowEvaluationDialog(true)}>
          <Star className="h-4 w-4 mr-2" /> 评价这份报告
        </Button>
      </div>

      <ReportEvaluationDialog
        open={showEvaluationDialog}
        onOpenChange={setShowEvaluationDialog}
        onEvaluationComplete={onNewAnalysis}
      />
    </div>
  );
};

const getSeverityColor = (severity: string) => {
  switch (severity) {
    case 'high':
      return 'bg-red-100 text-red-700';
    case 'medium':
      return 'bg-yellow-100 text-yellow-700';
    default:
      return 'bg-green-100 text-green-700';
  }
};

const getPotentialColor = (potential: string) => {
  switch (potential) {
    case 'high':
      return 'bg-emerald-100 text-emerald-700';
    case 'medium':
      return 'bg-yellow-100 text-yellow-700';
    default:
      return 'bg-gray-100 text-gray-700';
  }
};

const getDifficultyText = (difficulty: string) => {
  switch (difficulty) {
    case 'easy':
      return '实施难度：简单';
    case 'hard':
      return '实施难度：困难';
    default:
      return '实施难度：中等';
  }
};

const getDifficultyColor = (difficulty: string) => {
  switch (difficulty) {
    case 'easy':
      return 'bg-emerald-100 text-emerald-700';
    case 'hard':
      return 'bg-red-100 text-red-700';
    default:
      return 'bg-yellow-100 text-yellow-700';
  }
};

const renderDifficultyStars = (difficulty: string) => {
  const count = difficulty === 'easy' ? 1 : difficulty === 'hard' ? 3 : 2;
  return (
    <div className="flex items-center gap-1 text-yellow-500">
      {Array.from({ length: count }).map((_, index) => (
        <Star key={index} className="h-4 w-4 fill-current" />
      ))}
    </div>
  );
};

const getSentimentIcon = (sentiment: string) => {
  switch (sentiment) {
    case 'positive':
      return <ThumbsUp className="h-4 w-4 text-emerald-500" />;
    case 'negative':
      return <ThumbsDown className="h-4 w-4 text-red-500" />;
    default:
      return <Activity className="h-4 w-4 text-yellow-500" />;
  }
};

export default InsightsReport;
