import React, {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import InputValidator from '@/utils/validation';
import { showToast } from '@/utils/toast';
import configService from '@/services/config.service';
import apiClient from '@/services/api.client';
import reportService from '@/services/report.service';
import logger from '@/utils/logger';
import {
  trackAnalysisSubmitted,
  trackAnalysisSubmitFailed,
  trackReportViewed,
} from '@/services/feedback.service';
import { useSecureAuth } from '@/hooks/useSecureAuth';
import { useTaskProgress } from '@/hooks/useTaskProgress';
import {
  type AnalysisState,
  type AppActions,
  type AppState,
  type AppStateContextValue,
  type AuthDialogReason,
  type AuthDialogTab,
  type CancelAnalysisResult,
  type HydrateTaskOptions,
  type LoadReportOptions,
  type LoadReportResult,
  type ResetScope,
  type StartAnalysisResult,
} from '@/types/appState.types';
import { ReportFormat } from '@/types/contracts/report.contract';
import type { TaskStatus } from '@/services/sse.service';

interface AnalyzeResponseEnvelope {
  status: string;
  message: string;
  timestamp: string;
  data?: {
    task_id: string;
  };
}

interface StatusResponseEnvelope {
  status: string;
  message: string;
  timestamp: string;
  data?: TaskStatus;
}

const TASK_DESCRIPTION_PREFIX = 'task_';
const TASK_DESCRIPTION_SUFFIX = '_description';

const createInitialAnalysisState = (): AnalysisState => ({
  taskId: null,
  productDescription: '',
  status: null,
  currentStep: null,
  overallProgress: 0,
  stepProgress: 0,
  estimatedRemainingSeconds: null,
  liveStats: {
    communities: 0,
    posts: 0,
    insights: 0,
  },
  startedAt: null,
  completedAt: null,
  isStarting: false,
  isCancelling: false,
  lastError: null,
  connection: {
    isConnected: false,
    strategy: null,
    attempts: 0,
    lastError: null,
  },
});

const createInitialReportState = (): AppState['report'] => ({
  data: null,
  isLoading: false,
  lastError: null,
  lastLoadedAt: null,
});

const createInitialUiState = (): AppState['ui'] => ({
  globalError: null,
  authDialog: {
    open: false,
    reason: null,
    defaultTab: 'login' as AuthDialogTab,
  },
});

const isConnectionEqual = (
  a: AnalysisState['connection'],
  b: AnalysisState['connection'],
): boolean =>
  a.isConnected === b.isConnected &&
  a.strategy === b.strategy &&
  a.attempts === b.attempts &&
  a.lastError === b.lastError;

const areLiveStatsEqual = (
  a: AnalysisState['liveStats'],
  b: AnalysisState['liveStats'],
): boolean =>
  a.communities === b.communities &&
  a.posts === b.posts &&
  a.insights === b.insights;

const hasMeaningfulStatusChange = (
  previous: TaskStatus | null,
  nextStatus: TaskStatus,
): boolean => {
  if (!previous) {
    return true;
  }

  return (
    previous.status !== nextStatus.status ||
    previous.progress !== nextStatus.progress ||
    previous.current_step !== nextStatus.current_step ||
    previous.step_progress !== nextStatus.step_progress ||
    previous.estimated_remaining_seconds !== nextStatus.estimated_remaining_seconds ||
    previous.error_message !== nextStatus.error_message
  );
};

const mergeTaskStatus = (
  prev: AnalysisState,
  status: TaskStatus,
): { state: AnalysisState; changed: boolean } => {
  let changed = false;
  let nextState = prev;

  if (hasMeaningfulStatusChange(prev.status, status)) {
    nextState = {
      ...nextState,
      status,
    };
    changed = true;
  }

  const nextStep = status.current_step ?? null;
  if (nextStep && nextStep !== prev.currentStep) {
    nextState = {
      ...nextState,
      currentStep: nextStep,
    };
    changed = true;
  }

  if (typeof status.progress === 'number' && status.progress !== prev.overallProgress) {
    nextState = {
      ...nextState,
      overallProgress: status.progress,
    };
    changed = true;
  }

  if (typeof status.step_progress === 'number' && status.step_progress !== prev.stepProgress) {
    nextState = {
      ...nextState,
      stepProgress: status.step_progress,
    };
    changed = true;
  }

  if (
    typeof status.estimated_remaining_seconds === 'number' &&
    status.estimated_remaining_seconds !== prev.estimatedRemainingSeconds
  ) {
    nextState = {
      ...nextState,
      estimatedRemainingSeconds: status.estimated_remaining_seconds,
    };
    changed = true;
  }

  if (status.started_at && status.started_at !== prev.startedAt) {
    nextState = {
      ...nextState,
      startedAt: status.started_at,
    };
    changed = true;
  }

  if (status.completed_at && status.completed_at !== prev.completedAt) {
    nextState = {
      ...nextState,
      completedAt: status.completed_at,
    };
    changed = true;
  }

  if (status.error_message && status.error_message !== prev.lastError) {
    nextState = {
      ...nextState,
      lastError: status.error_message,
    };
    changed = true;
  }

  if (status.stats) {
    const mappedStats = {
      communities: status.stats.communities_found ?? prev.liveStats.communities,
      posts: status.stats.posts_analyzed ?? prev.liveStats.posts,
      insights: status.stats.insights_generated ?? prev.liveStats.insights,
    };

    if (!areLiveStatsEqual(prev.liveStats, mappedStats)) {
      nextState = {
        ...nextState,
        liveStats: mappedStats,
      };
      changed = true;
    }
  }

  if (prev.isStarting) {
    nextState = {
      ...nextState,
      isStarting: false,
    };
    changed = true;
  }

  return {
    state: nextState,
    changed,
  };
};

const getDescriptionStorageKey = (taskId: string): string =>
  `${TASK_DESCRIPTION_PREFIX}${taskId}${TASK_DESCRIPTION_SUFFIX}`;

type AppStateProviderComponent = React.FC<{ children: React.ReactNode }> & {
  Context: React.Context<AppStateContextValue | undefined>;
};

const AppStateContext = createContext<AppStateContextValue | undefined>(undefined);

const AppStateProvider: AppStateProviderComponent = ({ children }) => {
  const {
    isAuthenticated,
    isLoading: authLoading,
    user,
    login: secureLogin,
    register: secureRegister,
    logout: secureLogout,
  } = useSecureAuth();

  const [state, setState] = useState<AppState>(() => ({
    currentStep: 'input',
    auth: {
      isAuthenticated,
      isLoading: authLoading,
      user,
    },
    analysis: createInitialAnalysisState(),
    report: createInitialReportState(),
    ui: createInitialUiState(),
  }));

  useEffect(() => {
    setState(prev => {
      if (
        prev.auth.isAuthenticated === isAuthenticated &&
        prev.auth.isLoading === authLoading &&
        prev.auth.user === user
      ) {
        return prev;
      }

      return {
        ...prev,
        auth: {
          isAuthenticated,
          isLoading: authLoading,
          user,
        },
      };
    });
  }, [authLoading, isAuthenticated, user]);

  const {
    status: taskStatus,
    error: progressError,
    isConnected,
    strategy,
    connectionAttempts,
    retry,
    disconnect,
  } = useTaskProgress(state.analysis.taskId ?? undefined);

  useEffect(() => {
    setState(prev => {
      const nextConnection = {
        isConnected,
        strategy: strategy ?? null,
        attempts: connectionAttempts,
        lastError: progressError,
      } as AnalysisState['connection'];

      let updatedAnalysis = prev.analysis;
      let hasChanges = false;

      if (!isConnectionEqual(prev.analysis.connection, nextConnection)) {
        updatedAnalysis = {
          ...updatedAnalysis,
          connection: nextConnection,
        };
        hasChanges = true;
      }

      if (taskStatus) {
        const { state: mergedState, changed } = mergeTaskStatus(updatedAnalysis, taskStatus);
        if (changed) {
          updatedAnalysis = mergedState;
          hasChanges = true;
        }
      }

      if (!taskStatus && prev.analysis.status !== null) {
        updatedAnalysis = {
          ...updatedAnalysis,
          status: null,
        };
        hasChanges = true;
      }

      if (!hasChanges) {
        return prev;
      }

      return {
        ...prev,
        analysis: updatedAnalysis,
      };
    });
  }, [connectionAttempts, isConnected, progressError, strategy, taskStatus]);

  const persistDescription = useCallback((taskId: string, description: string) => {
    try {
      localStorage.setItem(getDescriptionStorageKey(taskId), description);
    } catch {
      // 忽略缓存失败
    }
  }, []);

  const readDescription = useCallback((taskId: string): string | null => {
    try {
      return localStorage.getItem(getDescriptionStorageKey(taskId));
    } catch {
      return null;
    }
  }, []);

  const openAuthDialog = useCallback(
    (reason: AuthDialogReason = 'unknown', defaultTab: AuthDialogTab = 'login') => {
      setState(prev => ({
        ...prev,
        ui: {
          ...prev.ui,
          authDialog: {
            open: true,
            reason,
            defaultTab,
          },
        },
      }));
    },
    [],
  );

  const closeAuthDialog = useCallback(() => {
    setState(prev => {
      if (!prev.ui.authDialog.open) {
        return prev;
      }
      return {
        ...prev,
        ui: {
          ...prev.ui,
          authDialog: {
            open: false,
            reason: null,
            defaultTab: prev.ui.authDialog.defaultTab,
          },
        },
      };
    });
  }, []);

  const setGlobalError = useCallback((message: string | null) => {
    setState(prev => ({
      ...prev,
      ui: {
        ...prev.ui,
        globalError: message,
      },
    }));
  }, []);

  const setProductDescription = useCallback((description: string) => {
    setState(prev => {
      if (prev.analysis.productDescription === description) {
        return prev;
      }
      return {
        ...prev,
        analysis: {
          ...prev.analysis,
          productDescription: description,
        },
      };
    });
  }, []);

  const startAnalysis = useCallback(async (description: string): Promise<StartAnalysisResult> => {
    const trimmed = description.trim();

    const validation = InputValidator.validateProductDescription(trimmed);
    if (!validation.valid) {
      const errorMessage = validation.error ?? '输入验证失败';
      setState(prev => ({
        ...prev,
        analysis: {
          ...prev.analysis,
          lastError: errorMessage,
          isStarting: false,
        },
        ui: {
          ...prev.ui,
          globalError: errorMessage,
        },
      }));
      return {
        success: false,
        reason: 'validation-error',
        error: errorMessage,
      };
    }

    const sanitized = validation.sanitized ?? trimmed;

    setState(prev => ({
      ...prev,
      analysis: {
        ...prev.analysis,
        productDescription: sanitized,
        isStarting: true,
        lastError: null,
      },
      ui: {
        ...prev.ui,
        globalError: null,
      },
    }));

    try {
      const endpoint = configService.getAnalyzeEndpoint();
      const response = await apiClient.post<AnalyzeResponseEnvelope>(endpoint, {
        product_description: sanitized,
        timestamp: Date.now(),
      });

      if (response.status !== 'success' || !response.data?.task_id) {
        throw new Error(response.message || '服务器未返回任务ID');
      }

      const taskId = response.data.task_id;

      persistDescription(taskId, sanitized);
      void trackAnalysisSubmitted(taskId, sanitized.length);
      showToast('分析任务已提交', 'success');

      setState(prev => ({
        ...prev,
        currentStep: 'analysis',
        analysis: {
          ...createInitialAnalysisState(),
          taskId,
          productDescription: sanitized,
          startedAt: new Date().toISOString(),
        },
        report: createInitialReportState(),
      }));

      return {
        success: true,
        taskId,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : '提交失败，请稍后重试';

      setState(prev => ({
        ...prev,
        analysis: {
          ...prev.analysis,
          isStarting: false,
          lastError: message,
        },
        ui: {
          ...prev.ui,
          globalError: message,
        },
      }));

      void trackAnalysisSubmitFailed(message);
      showToast(message, 'error');

      return {
        success: false,
        reason: 'api-error',
        error: message,
      };
    }
  }, [isAuthenticated, openAuthDialog, persistDescription]);

  const hydrateFromTask = useCallback(
    async (taskId: string, options?: HydrateTaskOptions) => {
      let resolvedDescription = readDescription(taskId);
      if (!resolvedDescription && options?.productDescriptionFallback) {
        resolvedDescription = options.productDescriptionFallback;
      }

      setState(prev => ({
        ...prev,
        currentStep: options?.step ?? 'analysis',
        analysis: {
          ...createInitialAnalysisState(),
          taskId,
          productDescription: resolvedDescription ?? prev.analysis.productDescription,
        },
        report: options?.step === 'report' ? prev.report : createInitialReportState(),
      }));

      try {
        const statusEndpoint = configService.getStatusEndpoint(taskId);
        const statusResponse = await apiClient.get<StatusResponseEnvelope>(statusEndpoint);
        if (statusResponse.status === 'success') {
          const initialStatus = statusResponse.data;
          if (initialStatus) {
            setState(prev => ({
              ...prev,
              analysis: mergeTaskStatus(prev.analysis, initialStatus).state,
            }));
          }
        }
      } catch {
        // 忽略状态同步失败，实时通道会继续尝试
      }
    },
    [readDescription],
  );

  const cancelAnalysis = useCallback(async (): Promise<CancelAnalysisResult> => {
    const activeTaskId = state.analysis.taskId;
    if (!activeTaskId) {
      return { success: true };
    }

    setState(prev => ({
      ...prev,
      analysis: {
        ...prev.analysis,
        isCancelling: true,
        lastError: null,
      },
    }));

    try {
      await apiClient.delete(`/api/v1/discovery/analyze/${activeTaskId}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : '取消分析失败';
      setState(prev => ({
        ...prev,
        analysis: {
          ...prev.analysis,
          isCancelling: false,
          lastError: message,
        },
        ui: {
          ...prev.ui,
          globalError: message,
        },
      }));
      return { success: false, error: message };
    }

    disconnect();

    setState(prev => ({
      ...prev,
      currentStep: 'input',
      analysis: {
        ...createInitialAnalysisState(),
        productDescription: prev.analysis.productDescription,
      },
      report: createInitialReportState(),
    }));

    return { success: true };
  }, [disconnect, state.analysis.taskId]);

  const retryConnection = useCallback(() => {
    retry();
  }, [retry]);

  const disconnectConnection = useCallback(() => {
    disconnect();
  }, [disconnect]);

  const acknowledgeError = useCallback(() => {
    setState(prev => ({
      ...prev,
      analysis: {
        ...prev.analysis,
        lastError: null,
      },
      ui: {
        ...prev.ui,
        globalError: null,
      },
    }));
  }, []);

  const loadReport = useCallback(
    async (taskId: string, options?: LoadReportOptions): Promise<LoadReportResult> => {
      if (!options?.forceReload && state.report.data?.task_id === taskId) {
        return { success: true };
      }

      setState(prev => ({
        ...prev,
        report: {
          ...prev.report,
          isLoading: true,
          lastError: null,
        },
      }));

      try {
        const response = await reportService.getReport({
          task_id: taskId,
          format: options?.format ?? ReportFormat.FULL,
        });

        if (!response.data) {
          throw new Error('报告数据为空');
        }

        try {
          await reportService.trackView(taskId);
          void trackReportViewed(taskId, options?.format ?? ReportFormat.FULL);
        } catch (trackError) {
          logger.warn('Failed to track report view', trackError as Error);
        }

        setState(prev => ({
          ...prev,
          currentStep: 'report',
          report: {
            data: response.data,
            isLoading: false,
            lastError: null,
            lastLoadedAt: new Date().toISOString(),
          },
          analysis: {
            ...prev.analysis,
            taskId,
            completedAt: prev.analysis.completedAt ?? new Date().toISOString(),
          },
        }));

        return { success: true };
      } catch (error) {
        const message = error instanceof Error ? error.message : '获取报告失败';
        setState(prev => ({
          ...prev,
          report: {
            ...prev.report,
            isLoading: false,
            lastError: message,
          },
          ui: {
            ...prev.ui,
            globalError: message,
          },
        }));
        return { success: false, error: message };
      }
    },
    [],
  );

  const clearReport = useCallback(() => {
    setState(prev => ({
      ...prev,
      report: createInitialReportState(),
    }));
  }, []);

  const reset = useCallback((scope: ResetScope = 'all') => {
    setState(prev => {
      switch (scope) {
        case 'analysis':
          disconnect();
          return {
            ...prev,
            analysis: createInitialAnalysisState(),
          };
        case 'report':
          return {
            ...prev,
            report: createInitialReportState(),
          };
        case 'ui':
          return {
            ...prev,
            ui: createInitialUiState(),
          };
        case 'all':
        default:
          disconnect();
          return {
            currentStep: 'input',
            auth: prev.auth,
            analysis: createInitialAnalysisState(),
            report: createInitialReportState(),
            ui: createInitialUiState(),
          };
      }
    });
  }, [disconnect]);

  const actions: AppActions = useMemo(() => ({
    auth: {
      login: secureLogin,
      register: secureRegister,
      logout: secureLogout,
      openDialog: openAuthDialog,
      closeDialog: closeAuthDialog,
    },
    navigation: {
      setStep: step => {
        setState(prev => ({
          ...prev,
          currentStep: step,
        }));
      },
    },
    analysis: {
      setProductDescription,
      startAnalysis,
      hydrateFromTask,
      cancelAnalysis,
      retryConnection,
      disconnectConnection,
      acknowledgeError,
    },
    report: {
      loadReport,
      clearReport,
    },
    ui: {
      setGlobalError,
    },
    reset,
  }), [
    cancelAnalysis,
    closeAuthDialog,
    disconnectConnection,
    hydrateFromTask,
    openAuthDialog,
    reset,
    retryConnection,
    secureLogin,
    secureLogout,
    secureRegister,
    setGlobalError,
    setProductDescription,
    startAnalysis,
    loadReport,
    clearReport,
  ]);

  const value = useMemo<AppStateContextValue>(() => ({
    state,
    actions,
  }), [actions, state]);

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
};

AppStateProvider.Context = AppStateContext;

export { AppStateProvider, AppStateContext };
