/**
 * 任务相关类型契约
 * 与backend/app/schemas/contracts/task_contract.py对应
 */

export enum TaskStatus {
  PENDING = "pending",
  RUNNING = "running",
  SUCCESS = "success",
  FAILED = "failed",
  RETRYING = "retrying"
}

export interface TaskRetryInfo {
  attempt_count: number;
  max_retries: number;
  last_error?: string;
  next_retry_at?: string; // ISO string
  exponential_backoff: boolean;
}

export interface TaskProcessedData {
  status: TaskStatus;
  progress_percentage: number; // 0-100
  retry_info?: TaskRetryInfo;
  result_data?: Record<string, unknown>;
  processing_time_seconds?: number;
}

// 前端扩展：任务监控相关类型
export interface TaskProgress {
  taskId: string;
  status: TaskStatus;
  progress: number;
  currentStep: string;
  estimatedTimeRemaining?: number;
  steps: TaskStep[];
}

export interface TaskStep {
  id: string;
  name: string;
  description: string;
  status: 'waiting' | 'active' | 'completed' | 'failed';
  duration?: number;
  error?: string;
}

// 等待页面组件Props
export interface WaitingPageProps {
  taskId: string;
  onComplete?: (result: TaskProcessedData) => void;
  onError?: (error: string) => void;
}

export interface ProgressTrackerProps {
  progress: TaskProgress;
  compact?: boolean;
  showSteps?: boolean;
}