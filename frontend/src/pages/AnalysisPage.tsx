import React, { useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import NavigationBreadcrumb, { type StepKey } from '@/components/v0/NavigationBreadcrumb';
import AnalysisProgress from '@/components/v0/AnalysisProgress';
import FallbackUI from '@/components/FallbackUI';
import { ANALYSIS_STEPS, AnalysisStep, formatRemainingTime, getStepIndex } from '@/services/sse.service';
import { useTaskProgress } from '@/hooks/useTaskProgress';

const AUTO_REDIRECT_DELAY = 2000;

const deriveProgressPercent = (status: ReturnType<typeof useTaskProgress>['status']): number => {
  if (!status) {
    return 0;
  }

  if (status.status === 'completed') {
    return 100;
  }

  if (status.status === 'pending') {
    return 10;
  }

  return typeof status.progress === 'number' ? status.progress : 0;
};

const buildSteps = (
  current: AnalysisStep,
  status: ReturnType<typeof useTaskProgress>['status']
) => {
  const activeIndex = Math.max(0, getStepIndex(current));
  const isCompleted = status?.status === 'completed';

  return ANALYSIS_STEPS.map((step, index) => {
    let stepStatus: 'pending' | 'in-progress' | 'completed' = 'pending';

    if (isCompleted || index < activeIndex) {
      stepStatus = 'completed';
    } else if (index === activeIndex) {
      stepStatus = status?.status === 'failed' ? 'pending' : 'in-progress';
    }

    return {
      id: step.step,
      title: step.title,
      description: step.description,
      status: stepStatus,
    };
  });
};

const AnalysisPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const {
    status,
    error,
    isConnected,
    strategy,
    retry,
    disconnect,
    connectionAttempts,
  } = useTaskProgress(taskId);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!taskId) {
      navigate('/');
    }
  }, [navigate, taskId]);

  if (!taskId) {
    return null;
  }

  const shouldFallback = connectionAttempts >= 3 && !isConnected && !status;

  if (shouldFallback) {
    return (
      <FallbackUI
        taskId={taskId}
        error={error ?? '无法建立连接'}
        onRetry={retry}
      />
    );
  }

  const progressPercent = deriveProgressPercent(status);
  const currentStep = status?.current_step ?? AnalysisStep.DATA_COLLECTION;
  const steps = useMemo(() => buildSteps(currentStep, status), [currentStep, status]);

  const estimatedRemainingSeconds =
    status?.estimated_remaining_seconds ?? undefined;
  const formattedRemaining = estimatedRemainingSeconds
    ? formatRemainingTime(estimatedRemainingSeconds)
    : null;

  const statsSnapshot = {
    communities: status?.stats?.communities_found ?? 0,
    posts: status?.stats?.posts_analyzed ?? 0,
    insights: status?.stats?.insights_generated ?? 0,
  };

  const liveStats = status?.stats
    ? {
        communities: statsSnapshot.communities,
        posts: statsSnapshot.posts,
        insights: statsSnapshot.insights,
      }
    : null;

  useEffect(() => {
    if (status?.status === 'processing') {
      if (timerRef.current === null) {
        timerRef.current = window.setInterval(() => {
          setElapsedSeconds((prev) => prev + 1);
        }, 1000);
      }
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      if (status?.stats?.processing_time_seconds) {
        setElapsedSeconds(status.stats.processing_time_seconds);
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [status?.status, status?.stats?.processing_time_seconds]);

  useEffect(() => {
    if (status?.status === 'completed') {
      const timer = window.setTimeout(() => {
        navigate(`/report/${taskId}`);
      }, AUTO_REDIRECT_DELAY);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [navigate, status?.status, taskId]);

  const formattedElapsed = useMemo(() => {
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = elapsedSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, [elapsedSeconds]);

  const handleCancel = () => {
    disconnect();
    navigate('/');
  };

  const handleBreadcrumbNavigate = (step: StepKey) => {
    if (step === 'input') {
      navigate('/');
    }
    if (step === 'report' && status?.status === 'completed') {
      navigate(`/report/${taskId}`);
    }
  };

  const connectionHint = !isConnected
    ? '实时连接已断开，正在尝试重新连接...'
    : strategy === 'sse'
      ? '实时连接：SSE'
      : '实时连接：轮询模式';

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-4xl space-y-6 px-4 sm:px-6">
        <NavigationBreadcrumb
          currentStep="analysis"
          canNavigateBack
          onNavigate={handleBreadcrumbNavigate}
        />

        {!isConnected && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {connectionHint}
            {error ? ` · ${error}` : null}
            <button
              type="button"
              onClick={retry}
              className="ml-3 inline-flex items-center text-amber-600 underline-offset-2 hover:underline"
            >
              重新连接
            </button>
          </div>
        )}

        <AnalysisProgress
          productDescription={''}
          progressPercent={progressPercent}
          steps={steps}
          estimatedRemaining={formattedRemaining}
          timeElapsed={formattedElapsed}
          isComplete={status?.status === 'completed'}
          onCancel={handleCancel}
          onViewReport={() => navigate(`/report/${taskId}`)}
          showReconnect={!isConnected || Boolean(error)}
          connection={{
            isConnected,
            strategy,
            error,
            onRetry: retry,
          }}
          liveStats={liveStats}
          statsSnapshot={statsSnapshot}
        />
      </div>
    </AppShell>
  );
};

export default AnalysisPage;
