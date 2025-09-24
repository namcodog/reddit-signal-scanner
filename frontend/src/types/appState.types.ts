import type { TaskStatus, AnalysisStep } from '@/services/sse.service';
import type { ReportData, ReportFormat } from '@/types/contracts/report.contract';

type User = {
  id: string;
  email: string;
  name?: string;
};

type RegisterRequest = {
  email: string;
  password: string;
  name?: string;
};

export type AppStep = 'input' | 'analysis' | 'report';

export type AuthDialogTab = 'login' | 'signup';

export type AuthDialogReason =
  | 'analysis'
  | 'report'
  | 'export'
  | 'feedback'
  | 'navigation'
  | 'unknown';

export interface AnalysisLiveStats {
  communities: number;
  posts: number;
  insights: number;
}

export interface TaskConnectionSnapshot {
  isConnected: boolean;
  strategy: 'websocket' | 'sse' | 'polling' | null;
  attempts: number;
  lastError: string | null;
}

export interface AnalysisState {
  taskId: string | null;
  productDescription: string;
  status: TaskStatus | null;
  currentStep: AnalysisStep | null;
  overallProgress: number;
  stepProgress: number;
  estimatedRemainingSeconds: number | null;
  liveStats: AnalysisLiveStats;
  startedAt: string | null;
  completedAt: string | null;
  isStarting: boolean;
  isCancelling: boolean;
  lastError: string | null;
  connection: TaskConnectionSnapshot;
}

export interface ReportState {
  data: ReportData | null;
  isLoading: boolean;
  lastError: string | null;
  lastLoadedAt: string | null;
}

export interface AuthStateSnapshot {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
}

export interface UiState {
  globalError: string | null;
  authDialog: {
    open: boolean;
    reason: AuthDialogReason | null;
    defaultTab: AuthDialogTab;
  };
}

export interface AppState {
  currentStep: AppStep;
  auth: AuthStateSnapshot;
  analysis: AnalysisState;
  report: ReportState;
  ui: UiState;
}

export type StartAnalysisFailureReason = 'auth-required' | 'validation-error' | 'api-error';

export interface StartAnalysisResult {
  success: boolean;
  taskId?: string;
  reason?: StartAnalysisFailureReason;
  error?: string;
}

export interface CancelAnalysisResult {
  success: boolean;
  error?: string;
}

export interface LoadReportOptions {
  format?: ReportFormat;
  forceReload?: boolean;
}

export interface LoadReportResult {
  success: boolean;
  error?: string;
}

export interface HydrateTaskOptions {
  productDescriptionFallback?: string;
  step?: AppStep;
}

export type ResetScope = 'all' | 'analysis' | 'report' | 'ui';

export interface AppActions {
  auth: {
    login: (email: string, password: string) => Promise<void>;
    register: (payload: RegisterRequest) => Promise<void>;
    logout: () => Promise<void>;
    openDialog: (reason?: AuthDialogReason, defaultTab?: AuthDialogTab) => void;
    closeDialog: () => void;
  };
  navigation: {
    setStep: (step: AppStep) => void;
  };
  analysis: {
    setProductDescription: (description: string) => void;
    startAnalysis: (description: string) => Promise<StartAnalysisResult>;
    hydrateFromTask: (taskId: string, options?: HydrateTaskOptions) => Promise<void>;
    cancelAnalysis: () => Promise<CancelAnalysisResult>;
    retryConnection: () => void;
    disconnectConnection: () => void;
    acknowledgeError: () => void;
  };
  report: {
    loadReport: (taskId: string, options?: LoadReportOptions) => Promise<LoadReportResult>;
    clearReport: () => void;
  };
  ui: {
    setGlobalError: (message: string | null) => void;
  };
  reset: (scope?: ResetScope) => void;
}

export interface AppStateContextValue {
  state: AppState;
  actions: AppActions;
}
