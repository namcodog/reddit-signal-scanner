import React, { useMemo } from 'react';
import { Brain, Users, MessageSquare, TrendingUp, LogIn, Loader2, CheckCircle, Circle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

type StepStatus = 'pending' | 'in-progress' | 'completed';

interface AnalysisStepDisplay {
  id: string;
  title: string;
  description: string;
  status: StepStatus;
}

interface LiveStats {
  communities: number;
  posts: number;
  insights: number;
}

interface ConnectionInfo {
  isConnected: boolean;
  strategy: 'websocket' | 'sse' | 'polling' | null;
  error?: string | null;
  onRetry: () => void;
}

interface AnalysisProgressProps {
  productDescription: string;
  progressPercent: number;
  steps: AnalysisStepDisplay[];
  estimatedRemaining: string | null;
  timeElapsed: string;
  isComplete: boolean;
  onCancel: () => void;
  onViewReport: () => void;
  showReconnect: boolean;
  connection: ConnectionInfo;
  liveStats?: LiveStats | null;
  statsSnapshot?: LiveStats;
  onLogin?: () => void;
}

const statCards: Array<{
  id: keyof LiveStats;
  label: string;
  icon: React.ReactNode;
  accent: string;
  iconColor: string;
}> = [
  {
    id: 'communities',
    label: '发现的社区',
    icon: <Users className="size-5" />,
    accent: 'bg-secondary/15',
    iconColor: 'text-secondary',
  },
  {
    id: 'posts',
    label: '已分析帖子',
    icon: <MessageSquare className="size-5" />,
    accent: 'bg-primary/10',
    iconColor: 'text-primary',
  },
  {
    id: 'insights',
    label: '生成的洞察',
    icon: <TrendingUp className="size-5" />,
    accent: 'bg-emerald-100/70',
    iconColor: 'text-emerald-600',
  },
];

const statusCopy: Record<StepStatus, { label: string; container: string; badge: string; badgeText: string }> = {
  pending: {
    label: '待开始',
    container: 'border-border bg-card',
    badge: 'bg-muted text-muted-foreground',
    badgeText: '待处理',
  },
  'in-progress': {
    label: '进行中',
    container: 'border-secondary/50 bg-secondary/10',
    badge: 'bg-secondary text-white',
    badgeText: '处理中',
  },
  completed: {
    label: '已完成',
    container: 'border-emerald-200 bg-emerald-50',
    badge: 'bg-emerald-500/90 text-white',
    badgeText: '已完成',
  },
};

const AnalysisProgress: React.FC<AnalysisProgressProps> = ({
  productDescription,
  progressPercent,
  steps,
  estimatedRemaining,
  timeElapsed,
  isComplete,
  onCancel,
  onViewReport,
  showReconnect,
  connection,
  liveStats,
  statsSnapshot,
  onLogin,
}) => {
  const stats = useMemo<LiveStats>(
    () => ({
      communities: liveStats?.communities ?? statsSnapshot?.communities ?? 0,
      posts: liveStats?.posts ?? statsSnapshot?.posts ?? 0,
      insights: liveStats?.insights ?? statsSnapshot?.insights ?? 0,
    }),
    [liveStats, statsSnapshot]
  );

  const roundedProgress = Math.min(100, Math.max(0, Math.round(progressPercent)));
  const heroTitle = isComplete ? '分析完成！' : '正在分析您的产品';
  const heroSubtitle = isComplete
    ? '我们已经为您发现值得关注的商业洞察，请点击下方查看完整报告。'
    : '我们正在扫描 Reddit 社区，为您的产品找出最有价值的市场信号。';
  const remainingLabel = isComplete ? '已完成' : estimatedRemaining ?? '生成中';

  const totalSteps = steps.length;
  const activeIndex = steps.findIndex((step) => step.status === 'in-progress');
  const completedSteps = steps.filter((step) => step.status === 'completed').length;
  const displayStepNumber = isComplete
    ? totalSteps
    : activeIndex >= 0
      ? activeIndex + 1
      : Math.min(completedSteps + 1, totalSteps);

  const progressHeadline = isComplete
    ? `全部 ${totalSteps} 个步骤已完成`
    : `第 ${displayStepNumber} 步 · 共 ${totalSteps} 步`;

  const renderStepIndicator = (status: StepStatus) => {
    if (status === 'completed') {
      return (
        <div className="flex size-10 items-center justify-center rounded-full border border-emerald-300 bg-emerald-50 text-emerald-600">
          <CheckCircle className="size-5" />
        </div>
      );
    }

    if (status === 'in-progress') {
      return (
        <div className="flex size-10 items-center justify-center rounded-full border border-secondary/50 bg-secondary/15 text-secondary">
          <Loader2 className="size-5 animate-spin" />
        </div>
      );
    }

    return (
      <div className="flex size-10 items-center justify-center rounded-full border border-border/60 text-muted-foreground">
        <Circle className="size-4" />
      </div>
    );
  };

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-6">
        {onLogin ? (
          <div className="flex justify-end">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2 rounded-full border-border/60 bg-background px-4 shadow-sm hover:bg-muted"
              onClick={onLogin}
            >
              <LogIn className="size-4" />
              登录
            </Button>
          </div>
        ) : null}

        <header className="flex flex-col items-center gap-4 text-center">
          <div className="flex size-14 items-center justify-center rounded-3xl bg-secondary/20">
            <Brain className="size-6 text-secondary animate-pulse" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">{heroTitle}</h2>
            <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">{heroSubtitle}</p>
          </div>
        </header>
      </div>

      <Card className="border border-border/60 shadow-[0px_20px_45px_-25px_rgba(15,23,42,0.25)]">
        <CardHeader className="space-y-1">
          <CardTitle className="text-base font-semibold text-foreground">正在分析的产品</CardTitle>
          <CardDescription className="text-sm">以下产品描述将作为生成洞察的核心依据</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="rounded-lg border border-border/70 bg-card/70 p-5 text-sm leading-relaxed text-muted-foreground">
            {productDescription || '尚未提供产品描述'}
          </p>
        </CardContent>
      </Card>

      <Card className="border border-border/60 shadow-[0px_20px_45px_-25px_rgba(15,23,42,0.25)]">
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <CardTitle className="text-base font-semibold text-foreground">实时分析进度</CardTitle>
              <CardDescription className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs sm:text-sm text-muted-foreground">
                <span>{progressHeadline}</span>
                <span className="hidden sm:inline">·</span>
                <span>已运行 {timeElapsed}</span>
                <span className="hidden sm:inline">·</span>
                <span>预计完成 {remainingLabel}</span>
              </CardDescription>
            </div>
            <Badge className="rounded-full bg-secondary px-4 py-1.5 text-sm font-semibold text-white shadow-sm">
              {roundedProgress}%
            </Badge>
          </div>
          <Progress value={roundedProgress} className="h-3 bg-muted" indicatorClassName="bg-foreground" />
        </CardHeader>
        <CardContent className="space-y-3">
          {steps.map((step) => {
            const meta = statusCopy[step.status];

            return (
              <div
                key={step.id}
                className={`flex flex-col gap-3 rounded-2xl border px-4 py-4 transition-colors sm:flex-row sm:items-center sm:justify-between ${meta.container}`}
              >
                <div className="flex items-start gap-4">
                  {renderStepIndicator(step.status)}
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-foreground">{step.title}</p>
                    <p className="text-xs text-muted-foreground sm:text-sm">{step.description}</p>
                    <p className="text-xs text-muted-foreground/80">{meta.label}</p>
                  </div>
                </div>
                <Badge className={`rounded-full px-3 py-1 text-xs font-medium ${meta.badge}`}>
                  {meta.badgeText}
                </Badge>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {!isComplete && (
        <div className="grid gap-4 md:grid-cols-3">
          {statCards.map((card) => (
            <Card key={card.id} className="border border-border/60 shadow-[0px_20px_45px_-25px_rgba(15,23,42,0.25)]">
              <CardContent className="flex flex-col items-center gap-3 p-5 text-center">
                <div className={`flex size-12 items-center justify-center rounded-full ${card.accent} ${card.iconColor}`}>
                  {card.icon}
                </div>
                <div className="text-2xl font-semibold text-foreground">{stats[card.id]}</div>
                <p className="text-sm text-muted-foreground">{card.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-center gap-3">
        {!isComplete ? (
          <>
            <Button type="button" variant="outline" className="min-w-[160px]" onClick={onCancel}>
              取消分析
            </Button>
            {showReconnect ? (
              <Button type="button" variant="ghost" className="min-w-[140px]" onClick={connection.onRetry}>
                重新连接
              </Button>
            ) : null}
          </>
        ) : (
          <Button type="button" size="lg" className="min-w-[200px]" onClick={onViewReport}>
            查看报告
          </Button>
        )}
      </div>

      <div className="text-center text-xs text-muted-foreground sm:text-sm">
        <span>已用时间：{timeElapsed}</span>
        {!isComplete && estimatedRemaining ? <span className="mx-2">·</span> : null}
        {!isComplete && estimatedRemaining ? <span>预计完成时间：{estimatedRemaining}</span> : null}
      </div>

      {isComplete ? (
        <Card className="border border-emerald-200 bg-emerald-50 text-emerald-700 shadow-none">
          <CardContent className="flex flex-col items-center gap-3 p-6 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-white text-emerald-500 shadow-sm">
              <CheckCircle className="h-6 w-6" />
            </div>
            <h3 className="text-xl font-semibold">分析已完成，报告已生成</h3>
            <p className="text-sm text-emerald-700/90">
              我们已经整理好完整的商业洞察，点击上方按钮即可查看详细报告。
            </p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
};

export default AnalysisProgress;
