// PRD-05/PRD-07 契约：前端反馈埋点类型定义（strict，无 any）

export enum FeedbackSource {
  User = 'user',
  Admin = 'admin',
  System = 'system',
}

export enum FeedbackEventType {
  AnalysisRating = 'analysis_rating',
  InsightFlag = 'insight_flag',
  Metric = 'metric',
  CommunityDecision = 'community_decision',
  ModerationAction = 'moderation_action',
}

export enum RatingValue {
  Like = 'like',
  Dislike = 'dislike',
}

export enum InsightFlag {
  Useful = 'useful',
  Inaccurate = 'inaccurate',
  Spam = 'spam',
  Other = 'other',
}

export interface BaseEventCommon {
  source: FeedbackSource;
  event_type: FeedbackEventType;
  task_id: string;
  analysis_id?: string;
  user_id?: string;
}

export interface AnalysisRatingEvent extends BaseEventCommon {
  event_type: FeedbackEventType.AnalysisRating;
  rating: RatingValue;
  reason?: string;
  comment?: string;
}

export interface InsightFlagEvent extends BaseEventCommon {
  event_type: FeedbackEventType.InsightFlag;
  insight_id: string;
  flag: InsightFlag;
  tags?: string[];
  comment?: string;
}

export interface MetricEvent extends BaseEventCommon {
  event_type: FeedbackEventType.Metric;
  metric_name: string;
  metric_value: number;
  metric_unit?: string;
  context?: Record<string, unknown>;
}

export interface ModerationEvent extends BaseEventCommon {
  event_type: FeedbackEventType.ModerationAction;
  reason?: string;
  context?: Record<string, unknown>;
}

export type FeedbackEventRequest =
  | AnalysisRatingEvent
  | InsightFlagEvent
  | MetricEvent
  | ModerationEvent;

export interface FeedbackEventSaved {
  event_id: string;
  stored: boolean;
  stored_backend: string;
  timestamp: string; // ISO8601
}

export interface FeedbackEventResponse {
  status: 'success' | 'error' | string;
  data: FeedbackEventSaved;
  message?: string;
  trace_id?: string;
}

export function isAnalysisRatingEvent(
  e: FeedbackEventRequest,
): e is AnalysisRatingEvent {
  return e.event_type === FeedbackEventType.AnalysisRating;
}

export function isInsightFlagEvent(e: FeedbackEventRequest): e is InsightFlagEvent {
  return e.event_type === FeedbackEventType.InsightFlag;
}

export function isMetricEvent(e: FeedbackEventRequest): e is MetricEvent {
  return e.event_type === FeedbackEventType.Metric;
}

export function isModerationEvent(e: FeedbackEventRequest): e is ModerationEvent {
  return e.event_type === FeedbackEventType.ModerationAction;
}
