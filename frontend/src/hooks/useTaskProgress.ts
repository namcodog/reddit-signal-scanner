/**
 * 任务进度监听Hook - 集成SSE实时通信
 * 基于PRD-05设计：SSE优先 + 轮询降级 + 状态恢复
 *
 * 用法：
 * const { status, error, isConnected, strategy } = useTaskProgress(taskId);
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { TaskStatus, realTimeTaskService } from '@/services/sse.service';

export interface TaskProgressState {
  status: TaskStatus | null;
  error: string | null;
  isConnected: boolean;
  strategy: 'sse' | 'polling' | null;
  connectionAttempts: number;
}

export interface TaskProgressActions {
  retry: () => void;
  disconnect: () => void;
}

export type UseTaskProgressReturn = TaskProgressState & TaskProgressActions;

/**
 * 任务进度监听Hook
 */
export function useTaskProgress(
  taskId: string | undefined
): UseTaskProgressReturn {
  const [state, setState] = useState<TaskProgressState>({
    status: null,
    error: null,
    isConnected: false,
    strategy: null,
    connectionAttempts: 0,
  });

  const isMonitoring = useRef(false);
  const retryCount = useRef(0);

  // 状态更新处理器
  const handleStatusUpdate = useCallback((status: TaskStatus) => {
    setState(prev => ({
      ...prev,
      status,
      error: status.error_message || null,
    }));
  }, []);

  // 错误处理器
  const handleError = useCallback((error: Error) => {
    setState(prev => ({
      ...prev,
      error: error.message,
      isConnected: false,
    }));
  }, []);

  // 完成处理器
  const handleComplete = useCallback(() => {
    setState(prev => ({
      ...prev,
      isConnected: false,
    }));
    isMonitoring.current = false;
  }, []);

  // 开始监听
  const startMonitoring = useCallback(() => {
    if (!taskId || isMonitoring.current) return;

    console.log(`开始监听任务: ${taskId}`);
    isMonitoring.current = true;
    retryCount.current++;

    setState(prev => ({
      ...prev,
      error: null,
      isConnected: true,
      connectionAttempts: retryCount.current,
    }));

    realTimeTaskService.startMonitoring(
      taskId,
      handleStatusUpdate,
      handleError,
      handleComplete
    );

    // 定期更新连接状态 - 修复内存泄漏
    const statusInterval = setInterval(() => {
      if (!isMonitoring.current) {
        return; // interval会在effect cleanup中统一清理
      }

      const serviceStatus = realTimeTaskService.getStatus();
      setState(prev => ({
        ...prev,
        strategy: serviceStatus.strategy,
        isConnected:
          serviceStatus.strategy === 'sse'
            ? serviceStatus.sse.connected
            : serviceStatus.polling.isPolling,
      }));
    }, 1000);

    // 确保清理函数
    return () => {
      clearInterval(statusInterval);
      realTimeTaskService.stopMonitoring();
      isMonitoring.current = false;
    };
  }, [taskId, handleStatusUpdate, handleError, handleComplete]);

  // 重试连接
  const retry = useCallback(() => {
    realTimeTaskService.stopMonitoring();
    isMonitoring.current = false;

    // 短暂延迟后重试
    setTimeout(() => {
      startMonitoring();
    }, 1000);
  }, [startMonitoring]);

  // 断开连接
  const disconnect = useCallback(() => {
    realTimeTaskService.stopMonitoring();
    isMonitoring.current = false;

    setState(prev => ({
      ...prev,
      isConnected: false,
      strategy: null,
    }));
  }, []);

  // 自动开始监听
  useEffect(() => {
    if (taskId && !isMonitoring.current) {
      const cleanup = startMonitoring();
      return cleanup;
    }
  }, [taskId, startMonitoring]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (isMonitoring.current) {
        realTimeTaskService.stopMonitoring();
        isMonitoring.current = false;
      }
    };
  }, []);

  // 页面可见性变化处理
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (
        document.visibilityState === 'visible' &&
        taskId &&
        !isMonitoring.current
      ) {
        // 页面重新可见时，如果任务还在进行，恢复监听
        if (
          state.status &&
          !['completed', 'failed'].includes(state.status.status)
        ) {
          console.log('页面重新可见，恢复任务监听');
          startMonitoring();
        }
      } else if (document.visibilityState === 'hidden') {
        // 页面隐藏时可以选择保持连接或断开
        // 这里选择保持连接，因为用户可能很快回来
        console.log('页面已隐藏，保持连接');
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () =>
      document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [taskId, state.status, startMonitoring]);

  // 浏览器刷新/关闭前清理
  useEffect(() => {
    const handleBeforeUnload = () => {
      realTimeTaskService.stopMonitoring();
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  return {
    ...state,
    retry,
    disconnect,
  };
}
