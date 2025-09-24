export type StatusColor = 'green' | 'yellow' | 'red';

export type AdminRole = 'operations' | 'support' | 'technical';

export interface AdminSessionData {
  user_id: string;
  tenant_id: string;
  email?: string | null;
  roles: AdminRole[];
  permissions: string[];
}

export interface AdminSessionResponse {
  code: number;
  data: AdminSessionData;
  trace_id?: string;
}

export interface CommunitySummary {
  community: string;
  c_score: number;
  status_color: StatusColor;
  hit_7d: number;
}

export interface CommunitiesListResponse {
  code: number;
  data: { items: CommunitySummary[]; total: number };
  trace_id?: string;
}

export type AdminTaskStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'dead_letter';

export interface AdminUserSummary {
  user_id: string;
  email: string;
  membership_level: string;
  created_at: string;
  total_tasks: number;
  active_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  last_activity_at?: string | null;
}

export interface AdminRecentTask {
  task_id: string;
  user_email: string;
  status: AdminTaskStatus;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
}

export interface AdminTaskStatusCounts {
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  dead_letter: number;
}

export interface AdminDashboardOverview {
  users: AdminUserSummary[];
  recent_tasks: AdminRecentTask[];
  status_counts: AdminTaskStatusCounts;
}

export interface AdminDashboardOverviewResponse {
  code: number;
  data: AdminDashboardOverview;
  trace_id?: string;
}

export interface AdminDurationStats {
  average: number;
  p50: number;
  p95: number;
}

export interface AdminQueueStats {
  pending: number;
  processing: number;
  completed_last_hour: number;
  failed_last_hour: number;
}

export interface AdminSystemMetrics {
  generated_at: string;
  queue: AdminQueueStats;
  durations: AdminDurationStats;
}

export interface AdminSystemMetricsResponse {
  code: number;
  data: AdminSystemMetrics;
  trace_id?: string;
}

export interface BehaviorReasonCount {
  reason: string;
  count: number;
}

export interface BehaviorSummary {
  total_events: number;
  by_type: Record<string, number>;
  top_reasons: BehaviorReasonCount[];
}

export interface BehaviorSummaryResponse {
  code: number;
  data: BehaviorSummary;
  trace_id?: string;
}

export interface UsageSeriesPoint {
  bucket: string;
  tasks_created: number;
  active_users: number;
}

export interface UsageStats {
  daily: UsageSeriesPoint[];
  weekly_tasks: number;
  weekly_active_users: number;
}

export interface UsageStatsResponse {
  code: number;
  data: UsageStats;
  trace_id?: string;
}

export interface ErrorCategorySummary {
  category: string;
  count: number;
}

export interface ErrorLogEntry {
  task_id: string;
  error_message?: string | null;
  failure_category?: string | null;
  happened_at: string;
}

export interface ErrorLogSummary {
  total_failed: number;
  categories: ErrorCategorySummary[];
  recent: ErrorLogEntry[];
}

export interface ErrorLogResponse {
  code: number;
  data: ErrorLogSummary;
  trace_id?: string;
}

export interface PerformanceSample {
  timestamp: string;
  avg_duration: number;
  p95_duration: number;
}

export interface PerformanceMetrics {
  samples: PerformanceSample[];
}

export interface PerformanceMetricsResponse {
  code: number;
  data: PerformanceMetrics;
  trace_id?: string;
}

export type ModerationAction = 'reject' | 'delete';

export interface AdminTaskModerationData {
  task_id: string;
  new_status: AdminTaskStatus;
  event_id?: string | null;
}

export interface AdminTaskModerationResponse {
  code: number;
  data: AdminTaskModerationData;
  trace_id?: string;
}

export interface AnalysisSummary {
  task_id: string;
  a_score: number;
  coverage: number;
  relevance: number;
  median_days: number;
}

export interface AnalysisListResponse {
  code: number;
  data: { items: AnalysisSummary[]; total: number };
  trace_id?: string;
}

export interface FeedbackSummaryResponse {
  code: number;
  data: { window: { start: string; end: string }; total: number; likes: number; dislikes: number; top_reasons: { reason: string; count: number }[] };
  trace_id?: string;
}

import { httpClient } from '../services/http.client';
import {
  type FeedbackEventRequest,
  FeedbackEventType,
  FeedbackSource,
  type MetricEvent,
} from '../types/feedback';

const API_BASE = '/api/v1';

export async function getAdminSession(): Promise<AdminSessionResponse> {
  return httpClient.get(`${API_BASE}/admin/session`);
}

export async function getCommunitiesSummary(params: { q?: string; status?: StatusColor; sort?: string; offset?: number; limit?: number } = {}): Promise<CommunitiesListResponse> {
  const query: Record<string, string> = {
    sort: params.sort ?? 'cscore_desc',
    offset: String(params.offset ?? 0),
    limit: String(params.limit ?? 20),
  };
  if (params.q) query.q = params.q;
  if (params.status) query.status = params.status;
  return httpClient.get(`${API_BASE}/admin/communities/summary`, { params: query });
}

export async function getAnalysisSummary(params: { q?: string; sort?: string; offset?: number; limit?: number } = {}): Promise<AnalysisListResponse> {
  const query: Record<string, string> = {
    sort: params.sort ?? 'ascore_desc',
    offset: String(params.offset ?? 0),
    limit: String(params.limit ?? 20),
  };
  if (params.q) query.q = params.q;
  return httpClient.get(`${API_BASE}/admin/analysis/summary`, { params: query });
}

export async function getAdminDashboardOverview(params: { user_limit?: number; task_limit?: number } = {}): Promise<AdminDashboardOverviewResponse> {
  const query: Record<string, string> = {
    user_limit: String(params.user_limit ?? 20),
    task_limit: String(params.task_limit ?? 20),
  };
  return httpClient.get(`${API_BASE}/admin/dashboard/overview`, { params: query });
}

export async function getAdminSystemMetrics(): Promise<AdminSystemMetricsResponse> {
  return httpClient.get(`${API_BASE}/admin/dashboard/metrics`);
}

export async function getBehaviorSummary(days = 30): Promise<BehaviorSummaryResponse> {
  return httpClient.get(`${API_BASE}/admin/stats/behavior`, { params: { days: String(days) } });
}

export async function getUsageStats(days = 7): Promise<UsageStatsResponse> {
  return httpClient.get(`${API_BASE}/admin/stats/usage`, { params: { days: String(days) } });
}

export async function getErrorSummary(limit = 20): Promise<ErrorLogResponse> {
  return httpClient.get(`${API_BASE}/admin/stats/errors`, { params: { limit: String(limit) } });
}

export async function getPerformanceMetrics(hours = 24): Promise<PerformanceMetricsResponse> {
  return httpClient.get(`${API_BASE}/admin/stats/performance`, { params: { hours: String(hours) } });
}

export async function moderateTask(taskId: string, payload: { action: ModerationAction; reason?: string }): Promise<AdminTaskModerationResponse> {
  return httpClient.post(`${API_BASE}/admin/dashboard/tasks/${taskId}/moderation`, payload);
}

export async function getFeedbackSummary(days = 30): Promise<FeedbackSummaryResponse> {
  return httpClient.get(`${API_BASE}/admin/feedback/summary`, { params: { days: String(days) } });
}

// ===== Admin 操作 API =====

export interface CommunityDecisionResponse { code: number; data: { event_id: string }; trace_id?: string }
export type CommunityAction = 'approve' | 'experiment' | 'pause' | 'blacklist';
export async function postCommunityDecision(payload: { community: string; action: CommunityAction; labels?: string[]; reason?: string }): Promise<CommunityDecisionResponse> {
  return httpClient.post(`${API_BASE}/admin/decisions/community`, payload);
}

export interface AnalysisFeedbackResponse { code: number; data: { event_id: string }; trace_id?: string }
export async function postAnalysisFeedback(payload: { task_id: string; satisfied: boolean; reasons: string[]; notes?: string }): Promise<AnalysisFeedbackResponse> {
  return httpClient.post(`${API_BASE}/admin/feedback/analysis`, payload);
}

// 导出（返回文本/JSON二选一，由调用方决定如何处理）
export async function exportFeedback(format: 'json' | 'csv' = 'json', range?: { start?: string; end?: string; limit?: number }): Promise<{ contentType: string; body: string }> {
  const params: Record<string, string> = { format };
  if (range?.start) params.start = range.start;
  if (range?.end) params.end = range.end;
  if (range?.limit) params.limit = String(range.limit);
  // 使用 fetch 以便拿到原始 body
  const url = `${API_BASE}/admin/feedback/export`;
  const qs = new URLSearchParams(params);
  const res = await fetch(`${url}?${qs.toString()}`, { credentials: 'same-origin' });
  const contentType = res.headers.get('content-type') || '';
  const body = await res.text();
  return { contentType, body };
}

// ===== 埋点上报（PRD-05 对齐） =====

export async function sendFeedbackEvent(evt: FeedbackEventRequest): Promise<void> {
  await httpClient.post(`${API_BASE}/feedback/events`, evt).catch(() => undefined);
}

export function trackAdminActionSuccess(taskOrCommunity: string, action: string): Promise<void> {
  const evt: MetricEvent = {
    source: FeedbackSource.Admin,
    event_type: FeedbackEventType.Metric,
    task_id: taskOrCommunity,
    metric_name: 'admin_action_success',
    metric_value: 1,
    context: { action },
  };
  return sendFeedbackEvent(evt);
}

export function trackAdminActionFail(taskOrCommunity: string, action: string, message: string): Promise<void> {
  const evt: MetricEvent = {
    source: FeedbackSource.Admin,
    event_type: FeedbackEventType.Metric,
    task_id: taskOrCommunity,
    metric_name: 'admin_action_failed',
    metric_value: 1,
    context: { action, message },
  };
  return sendFeedbackEvent(evt);
}

export function trackExportClicked(): Promise<void> {
  const evt: MetricEvent = {
    source: FeedbackSource.Admin,
    event_type: FeedbackEventType.Metric,
    task_id: 'admin',
    metric_name: 'export_clicked',
    metric_value: 1,
  };
  return sendFeedbackEvent(evt);
}
