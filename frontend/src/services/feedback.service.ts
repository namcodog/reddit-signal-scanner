import HttpClient from '@/utils/httpClient';
import logger from '@/utils/logger';
import {
  FeedbackEventType,
  FeedbackSource,
  type FeedbackEventRequest,
  type MetricEvent,
  type AnalysisRatingEvent,
  RatingValue,
} from '@/types/feedback';

export type MetricContextValue = string | number | boolean | null;
export type MetricContext = Record<string, MetricContextValue>;

async function sendEvent(event: FeedbackEventRequest): Promise<void> {
  try {
    await HttpClient.post('/api/v1/feedback/events', event);
  } catch (error) {
    logger.warn('Failed to send feedback event', error as Error);
  }
}

function buildMetricEvent(
  taskId: string,
  metricName: string,
  metricValue: number,
  context?: MetricContext,
): MetricEvent {
  const safeContext = context
    ? Object.fromEntries(
        Object.entries(context).map(([key, value]) => [key, value]),
      )
    : undefined;

  return {
    source: FeedbackSource.User,
    event_type: FeedbackEventType.Metric,
    task_id: taskId,
    metric_name: metricName,
    metric_value: metricValue,
    context: safeContext,
  };
}

export async function trackAnalysisSubmitted(
  taskId: string,
  descriptionLength: number,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'analysis_submitted', 1, {
      description_length: descriptionLength,
    }),
  );
}

export async function trackAnalysisSubmitFailed(reason: string): Promise<void> {
  await sendEvent(
    buildMetricEvent('pending', 'analysis_submit_failed', 1, {
      reason,
    }),
  );
}

export async function trackProgressConnected(
  taskId: string,
  strategy: string,
  connectionAttempts: number,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'progress_connection', 1, {
      strategy,
      connection_attempts: connectionAttempts,
    }),
  );
}

export async function trackProgressFallback(
  taskId: string,
  connectionAttempts: number,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'progress_fallback', 1, {
      connection_attempts: connectionAttempts,
    }),
  );
}

export async function trackProgressError(taskId: string, message: string): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'progress_error', 1, {
      message,
    }),
  );
}

export async function trackProgressCompleted(
  taskId: string,
  durationSeconds: number,
  finalStrategy: string | null,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'analysis_completed', 1, {
      duration_seconds: durationSeconds,
      strategy: finalStrategy,
    }),
  );
}

export async function trackReportViewed(
  taskId: string,
  format: string,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'report_viewed', 1, {
      format,
    }),
  );
}

export async function trackReportExported(
  taskId: string,
  format: string,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'report_export', 1, {
      format,
    }),
  );
}

export async function trackReportExportFailed(
  taskId: string,
  format: string,
  message: string,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'report_export_failed', 1, {
      format,
      message,
    }),
  );
}

export async function trackReportShared(taskId: string): Promise<void> {
  await sendEvent(buildMetricEvent(taskId, 'report_shared', 1));
}

export async function trackReportShareFailed(
  taskId: string,
  message: string,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'report_share_failed', 1, {
      message,
    }),
  );
}

export async function trackAnalysisRating(
  taskId: string,
  satisfied: boolean,
  comment?: string,
): Promise<void> {
  const event: AnalysisRatingEvent = {
    source: FeedbackSource.User,
    event_type: FeedbackEventType.AnalysisRating,
    task_id: taskId,
    rating: satisfied ? RatingValue.Like : RatingValue.Dislike,
    comment,
  };
  await sendEvent(event);
}

// 新增：用户交互埋点
export async function trackAnalysisInteraction(
  taskId: string,
  action: string,
  target?: string,
  context?: MetricContext,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'analysis_interaction', 1, {
      action,
      target: target || null,
      ...context,
    }),
  );
}

// 新增：性能指标埋点
export async function trackReportFirstPaint(
  taskId: string,
  paintTimeMs: number,
): Promise<void> {
  await sendEvent(
    buildMetricEvent(taskId, 'report_first_paint_ms', paintTimeMs),
  );
}
