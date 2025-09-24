/**
 * WebSocket实时通信服务 - Phase3核心组件
 * 实现WebSocket连接，支持自动重连、心跳检测和SSE降级
 */

import logger from '@/utils/logger';
import { TaskStatus, AnalysisStep, SSEEventHandler, SSEErrorHandler, SSECloseHandler } from './sse.service';
import { configService } from './config.service';

// WebSocket消息类型
export interface WebSocketMessage {
  type: 'connected' | 'progress' | 'completed' | 'error' | 'close' | 'heartbeat';
  task_id: string;
  status?: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  message?: string;
  created_at?: string;
  updated_at?: string;
  started_at?: string;
  completed_at?: string;
  retry_count?: number;
  error_message?: string;
  step?: AnalysisStep;
  step_progress?: number;
  estimated_remaining_seconds?: number;
}

export interface WebSocketConfig {
  maxRetries: number;
  retryBaseDelay: number;
  maxRetryDelay: number;
  heartbeatTimeout: number;
  connectionTimeout: number;
}

/**
 * WebSocket连接管理器
 * 支持指数退避重连策略
 */
export class WebSocketManager {
  private socket: WebSocket | null = null;
  private config: WebSocketConfig;
  private retryCount: number = 0;
  private isConnected: boolean = false;
  private heartbeatTimer: number | null = null;
  private connectionTimer: number | null = null;
  private lastTaskId: string | null = null;

  private onStatusUpdate?: SSEEventHandler;
  private onError?: SSEErrorHandler;
  private onClose?: SSECloseHandler;

  constructor(config: Partial<WebSocketConfig> = {}) {
    this.config = {
      maxRetries: 5,
      retryBaseDelay: 1000, // 1秒基础延迟
      maxRetryDelay: 30000, // 30秒最大延迟
      heartbeatTimeout: 35000, // 35秒心跳超时
      connectionTimeout: 10000, // 10秒连接超时
      ...config,
    };
  }

  /**
   * 连接到WebSocket任务流
   */
  connect(
    taskId: string,
    onStatusUpdate: SSEEventHandler,
    onError: SSEErrorHandler,
    onClose: SSECloseHandler
  ): void {
    this.lastTaskId = taskId;
    this.onStatusUpdate = onStatusUpdate;
    this.onError = onError;
    this.onClose = onClose;

    this.establishConnection(taskId);
  }

  /**
   * 建立WebSocket连接
   */
  private establishConnection(taskId: string): void {
    try {
      // 关闭现有连接
      this.disconnect();

      const baseUrl = configService.getConfig().apiBaseUrl;
      const url = new URL(baseUrl);
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      url.pathname = `/ws/tasks/${taskId}`;

      const wsUrl = url.toString();

      this.socket = new WebSocket(wsUrl);

      // 设置连接超时
      this.connectionTimer = window.setTimeout(() => {
        if (!this.isConnected) {
          this.handleConnectionError(new Error('WebSocket连接超时'));
        }
      }, this.config.connectionTimeout);

      this.socket.onopen = () => {
        this.clearConnectionTimer();
        this.isConnected = true;
        this.retryCount = 0;
        this.startHeartbeatMonitor();

        logger.info(`WebSocket连接已建立: ${taskId}`);
      };

      this.socket.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          logger.error('WebSocket消息解析失败:', error as Error);
          this.onError?.(new Error('数据格式错误'));
        }
      };

      this.socket.onerror = (error) => {
        this.clearConnectionTimer();
        logger.error('WebSocket错误:', error);
        this.handleConnectionError(new Error('WebSocket连接错误'));
      };

      this.socket.onclose = (event) => {
        this.clearConnectionTimer();
        this.isConnected = false;
        this.stopHeartbeatMonitor();

        if (event.wasClean) {
          logger.info('WebSocket连接正常关闭');
        } else {
          logger.warn(`WebSocket连接异常关闭: ${event.code} ${event.reason}`);
          this.handleConnectionError(new Error(`连接关闭: ${event.reason || '未知原因'}`));
        }
      };

    } catch (error) {
      this.handleConnectionError(error as Error);
    }
  }

  /**
   * 处理WebSocket消息
   */
  private handleMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'connected':
        logger.debug('WebSocket连接确认');
        break;

      case 'heartbeat':
        logger.debug('WebSocket心跳收到');
        this.resetHeartbeatMonitor();
        break;

      case 'progress':
      case 'completed':
      case 'error': {
        // 转换为TaskStatus格式
        const status: TaskStatus = {
          task_id: message.task_id,
          status: message.status || 'pending',
          progress: message.progress,
          message: message.message,
          error_message: message.error_message,
          estimated_remaining_seconds: message.estimated_remaining_seconds,
          current_step: message.step,
          step_progress: message.step_progress,
          created_at: message.updated_at,
        };

        this.onStatusUpdate?.(status);

        // 任务完成时自动断开
        if (message.type === 'completed' || message.type === 'error') {
          this.disconnect();
        }
        break;
      }

      case 'close':
        this.disconnect();
        break;

      default:
        logger.warn('未知WebSocket消息类型:', message.type);
    }
  }

  /**
   * 处理连接错误
   */
  private handleConnectionError(error: Error): void {
    this.isConnected = false;
    this.stopHeartbeatMonitor();

    logger.error('WebSocket连接错误:', error);

    // 判断是否需要重试
    const shouldRetry = this.retryCount < this.config.maxRetries;

    this.onError?.(error);
    this.onClose?.(shouldRetry);

    if (shouldRetry) {
      this.retryCount++;

      // 指数退避计算延迟
      const delay = Math.min(
        this.config.retryBaseDelay * Math.pow(2, this.retryCount - 1),
        this.config.maxRetryDelay
      );

      logger.info(
        `WebSocket重连第${this.retryCount}次，${delay}ms后重试`
      );

      setTimeout(() => {
        if (this.lastTaskId) {
          this.establishConnection(this.lastTaskId);
        }
      }, delay);
    } else {
      logger.warn('WebSocket重连次数已达上限，放弃连接');
    }
  }

  /**
   * 开始心跳监控
   */
  private startHeartbeatMonitor(): void {
    this.stopHeartbeatMonitor();
    this.resetHeartbeatMonitor();
  }

  /**
   * 重置心跳计时器
   */
  private resetHeartbeatMonitor(): void {
    this.stopHeartbeatMonitor();

    this.heartbeatTimer = window.setTimeout(() => {
      logger.warn('WebSocket心跳超时，准备重连');
      this.handleConnectionError(new Error('心跳超时'));
    }, this.config.heartbeatTimeout);
  }

  /**
   * 停止心跳监控
   */
  private stopHeartbeatMonitor(): void {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * 清除连接计时器
   */
  private clearConnectionTimer(): void {
    if (this.connectionTimer) {
      clearTimeout(this.connectionTimer);
      this.connectionTimer = null;
    }
  }

  /**
   * 断开WebSocket连接
   */
  disconnect(): void {
    this.stopHeartbeatMonitor();
    this.clearConnectionTimer();

    if (this.socket) {
      this.socket.close(1000, '主动断开');
      this.socket = null;
    }

    this.isConnected = false;
    this.retryCount = 0;
  }

  /**
   * 获取连接状态
   */
  getConnectionState(): {
    connected: boolean;
    retryCount: number;
    readyState?: number;
  } {
    return {
      connected: this.isConnected,
      retryCount: this.retryCount,
      readyState: this.socket?.readyState,
    };
  }
}

/**
 * 混合实时通信服务
 * WebSocket优先，SSE降级
 */
export class HybridRealTimeService {
  private wsManager: WebSocketManager;
  private currentStrategy: 'websocket' | 'sse' | null = null;
  private fallbackCallback?: () => void;

  constructor() {
    this.wsManager = new WebSocketManager();
  }

  /**
   * 开始监听任务状态 - WebSocket优先
   */
  startMonitoring(
    taskId: string,
    onStatusUpdate: SSEEventHandler,
    onError: SSEErrorHandler,
    _onComplete: () => void,
    onFallbackToSSE?: () => void
  ): void {
    logger.info(`开始WebSocket监听任务状态: ${taskId}`);

    this.currentStrategy = 'websocket';
    this.fallbackCallback = onFallbackToSSE;

    this.wsManager.connect(
      taskId,
      onStatusUpdate,
      error => {
        logger.warn('WebSocket错误:', error.message);
        onError(error);
      },
      willRetry => {
        if (!willRetry) {
          logger.warn('WebSocket连接失败，准备切换到SSE');
          this.fallbackToSSE();
        }
      }
    );
  }

  /**
   * 降级到SSE模式
   */
  private fallbackToSSE(): void {
    this.currentStrategy = 'sse';

    if (this.fallbackCallback) {
      this.fallbackCallback();
    } else {
      logger.warn('未提供SSE降级回调函数');
    }
  }

  /**
   * 停止所有监听
   */
  stopMonitoring(): void {
    this.wsManager.disconnect();
    this.currentStrategy = null;
  }

  /**
   * 获取当前通信策略和状态
   */
  getStatus(): {
    strategy: 'websocket' | 'sse' | null;
    websocket: ReturnType<WebSocketManager['getConnectionState']>;
  } {
    return {
      strategy: this.currentStrategy,
      websocket: this.wsManager.getConnectionState(),
    };
  }
}

// 导出单例实例
export const hybridRealTimeService = new HybridRealTimeService();
