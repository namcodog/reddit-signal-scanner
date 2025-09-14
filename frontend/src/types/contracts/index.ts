/**
 * 前端类型契约统一导出
 * 确保与后端contracts完全同步
 */

// 报告相关类型
export type {
  ReportData,
  InsightItem,
  ChartData,
  VisualizationConfig,
  ReportPageProps,
  ExecutiveSummaryProps,
  PainPointsListProps,
  CompetitorAnalysisProps,
  OpportunityMatrixProps
} from './report.contract';

export { ReportFormat } from './report.contract';

// 任务相关类型
export type {
  TaskProcessedData,
  TaskRetryInfo,
  TaskProgress,
  TaskStep,
  WaitingPageProps,
  ProgressTrackerProps
} from './task.contract';

export { TaskStatus } from './task.contract';

// 认证相关类型
export type {
  JWTPayload,
  UserContext,
  AuthState,
  LoginRequest,
  LoginResponse,
  ProtectedRouteProps,
  AuthContextProps
} from './auth.contract';

// API基础类型
export type {
  ApiResponse,
  ApiError,
  PaginatedResponse,
  BaseApiClient
} from '../api/base.api';