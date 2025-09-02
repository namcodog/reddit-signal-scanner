/**
 * SSE实时通信服务 - PRD-05核心要求
 * 实现Server-Sent Events连接，支持自动重连和错误处理
 * 
 * 基于PRD设计：
 * - SSE优先策略，降级到轮询
 * - 心跳检测防止连接断开
 * - 智能重连机制
 */

export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  message?: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export interface SSEConfig {
  maxRetries: number;
  retryDelay: number;
  heartbeatInterval: number;
  connectionTimeout: number;
}

export type SSEEventHandler = (status: TaskStatus) => void;
export type SSEErrorHandler = (error: Error) => void;
export type SSECloseHandler = (willRetry: boolean) => void;

/**
 * SSE实时通信管理器
 * 符合PRD-05的实时通信要求
 */
export class SSEManager {
  private eventSource: EventSource | null = null;
  private config: SSEConfig;
  private retryCount: number = 0;
  private isConnected: boolean = false;
  private heartbeatTimer: number | null = null;
  private lastTaskId: string | null = null; // 存储taskId避免URL解析
  
  private onStatusUpdate?: SSEEventHandler;
  private onError?: SSEErrorHandler;
  private onClose?: SSECloseHandler;

  constructor(config: Partial<SSEConfig> = {}) {
    this.config = {
      maxRetries: 3,
      retryDelay: 2000, // 2秒重连间隔
      heartbeatInterval: 30000, // 30秒心跳
      connectionTimeout: 10000, // 10秒连接超时
      ...config
    };
  }

  /**
   * 连接到任务状态SSE流
   */
  connect(
    taskId: string,
    onStatusUpdate: SSEEventHandler,
    onError: SSEErrorHandler,
    onClose: SSECloseHandler
  ): void {
    this.lastTaskId = taskId; // 存储taskId
    this.onStatusUpdate = onStatusUpdate;
    this.onError = onError;
    this.onClose = onClose;

    this.establishConnection(taskId);
  }

  /**
   * 建立SSE连接
   */
  private establishConnection(taskId: string): void {
    try {
      // 关闭现有连接
      this.disconnect();

      const sseUrl = `/api/v1/analyze/stream/${taskId}`;
      this.eventSource = new EventSource(sseUrl);

      // 设置连接超时
      const connectionTimeout = setTimeout(() => {
        if (!this.isConnected) {
          this.handleConnectionError(new Error('连接超时'));
        }
      }, this.config.connectionTimeout);

      this.eventSource.onopen = () => {
        clearTimeout(connectionTimeout);
        this.isConnected = true;
        this.retryCount = 0;
        this.startHeartbeat();
        
        console.log(`SSE连接已建立: ${taskId}`);
      };

      this.eventSource.onmessage = (event) => {
        try {
          const status: TaskStatus = JSON.parse(event.data);
          this.onStatusUpdate?.(status);

          // 任务完成时自动断开连接
          if (status.status === 'completed' || status.status === 'failed') {
            this.disconnect();
          }
        } catch (error) {
          console.error('SSE消息解析失败:', error);
          this.onError?.(new Error('数据格式错误'));
        }
      };

      this.eventSource.onerror = () => {
        clearTimeout(connectionTimeout);
        this.handleConnectionError(new Error('SSE连接错误'));
      };

      // 监听心跳事件
      this.eventSource.addEventListener('heartbeat', (event) => {
        const data = JSON.parse(event.data);
        console.log('SSE心跳收到:', data.timestamp);
      });

    } catch (error) {
      this.handleConnectionError(error as Error);
    }
  }

  /**
   * 处理连接错误
   */
  private handleConnectionError(error: Error): void {
    this.isConnected = false;
    this.stopHeartbeat();

    console.error('SSE连接错误:', error.message);

    // 判断是否需要重试
    const shouldRetry = this.retryCount < this.config.maxRetries;
    
    this.onError?.(error);
    this.onClose?.(shouldRetry);

    if (shouldRetry) {
      this.retryCount++;
      console.log(`SSE重连第${this.retryCount}次，${this.config.retryDelay}ms后重试`);
      
      setTimeout(() => {
        // 使用存储的taskId重新连接，不依赖URL解析
        if (this.lastTaskId) {
          this.establishConnection(this.lastTaskId);
        }
      }, this.config.retryDelay);
    } else {
      console.log('SSE重连次数已达上限，放弃连接');
    }
  }

  /**
   * 开始心跳检测
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatTimer = window.setInterval(() => {
      if (!this.isConnected || !this.eventSource) {
        this.stopHeartbeat();
        return;
      }

      // 检查连接状态
      if (this.eventSource.readyState !== EventSource.OPEN) {
        console.warn('SSE连接异常，准备重连');
        this.handleConnectionError(new Error('连接状态异常'));
      }
    }, this.config.heartbeatInterval);
  }

  /**
   * 停止心跳检测
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * 断开SSE连接
   */
  disconnect(): void {
    this.stopHeartbeat();
    
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
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
      readyState: this.eventSource?.readyState
    };
  }
}

/**
 * 轮询备用机制
 * 当SSE不可用时的降级方案
 */
export class PollingManager {
  private pollTimer: number | null = null;
  private config: { interval: number; maxAttempts: number };
  private attemptCount: number = 0;
  private currentDelay: number = 5000; // 当前重试延迟
  private readonly baseDelay: number = 5000; // 基础延迟
  private readonly maxDelay: number = 30000; // 最大延迟30秒

  constructor(config: { interval?: number; maxAttempts?: number } = {}) {
    this.config = {
      interval: 5000, // 5秒轮询间隔
      maxAttempts: 72, // 6分钟最大轮询次数
      ...config
    };
    this.baseDelay = config.interval || 5000;
    this.currentDelay = this.baseDelay;
  }

  /**
   * 开始轮询
   */
  startPolling(
    taskId: string, 
    onStatusUpdate: SSEEventHandler,
    onError: SSEErrorHandler,
    onComplete: () => void
  ): void {
    this.stopPolling();
    this.attemptCount = 0;

    const poll = async () => {
      try {
        this.attemptCount++;
        
        const response = await fetch(`/api/v1/tasks/${taskId}/status`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const status: TaskStatus = await response.json();
        onStatusUpdate(status);

        // 检查任务是否完成
        if (status.status === 'completed' || status.status === 'failed') {
          this.stopPolling();
          onComplete();
          return;
        }

        // 检查是否达到最大轮询次数
        if (this.attemptCount >= this.config.maxAttempts) {
          this.stopPolling();
          onError(new Error('轮询超时，任务可能需要更长时间完成'));
          return;
        }

        // 继续轮询 - 重置延迟
        this.currentDelay = this.baseDelay;
        this.pollTimer = window.setTimeout(poll, this.currentDelay);

      } catch (error) {
        console.error('轮询请求失败:', error);
        onError(error as Error);
        
        // 指数退避重试 - Linus修复
        if (this.attemptCount < this.config.maxAttempts) {
          this.currentDelay = Math.min(this.currentDelay * 2, this.maxDelay);
          console.log(`轮询失败，${this.currentDelay}ms后重试 (第${this.attemptCount}次)`);
          this.pollTimer = window.setTimeout(poll, this.currentDelay);
        } else {
          console.log('轮询达到最大次数，停止轮询');
          this.stopPolling();
        }
      }
    };

    console.log(`开始轮询任务状态: ${taskId}`);
    poll();
  }

  /**
   * 停止轮询
   */
  stopPolling(): void {
    if (this.pollTimer) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
    // 重置延迟
    this.currentDelay = this.baseDelay;
  }

  /**
   * 获取轮询状态
   */
  getPollingState(): { isPolling: boolean; attemptCount: number } {
    return {
      isPolling: this.pollTimer !== null,
      attemptCount: this.attemptCount
    };
  }
}

/**
 * 统一的实时通信服务
 * 结合SSE和轮询的混合策略
 */
export class RealTimeTaskService {
  private sseManager: SSEManager;
  private pollingManager: PollingManager;
  private currentStrategy: 'sse' | 'polling' | null = null;

  constructor() {
    this.sseManager = new SSEManager();
    this.pollingManager = new PollingManager();
  }

  /**
   * 开始监听任务状态 - SSE优先，降级到轮询
   */
  startMonitoring(
    taskId: string,
    onStatusUpdate: SSEEventHandler,
    onError: SSEErrorHandler,
    onComplete: () => void
  ): void {
    console.log(`开始监听任务状态: ${taskId}`);

    // 首先尝试SSE
    this.currentStrategy = 'sse';
    
    this.sseManager.connect(
      taskId,
      onStatusUpdate,
      (error) => {
        console.warn('SSE错误:', error.message);
        onError(error);
      },
      (willRetry) => {
        if (!willRetry) {
          console.log('SSE连接失败，切换到轮询模式');
          this.fallbackToPolling(taskId, onStatusUpdate, onError, onComplete);
        }
      }
    );
  }

  /**
   * 降级到轮询模式
   */
  private fallbackToPolling(
    taskId: string,
    onStatusUpdate: SSEEventHandler,
    onError: SSEErrorHandler,
    onComplete: () => void
  ): void {
    this.currentStrategy = 'polling';
    
    this.pollingManager.startPolling(
      taskId,
      onStatusUpdate,
      onError,
      onComplete
    );
  }

  /**
   * 停止所有监听
   */
  stopMonitoring(): void {
    this.sseManager.disconnect();
    this.pollingManager.stopPolling();
    this.currentStrategy = null;
  }

  /**
   * 获取当前通信策略和状态
   */
  getStatus(): {
    strategy: 'sse' | 'polling' | null;
    sse: ReturnType<SSEManager['getConnectionState']>;
    polling: ReturnType<PollingManager['getPollingState']>;
  } {
    return {
      strategy: this.currentStrategy,
      sse: this.sseManager.getConnectionState(),
      polling: this.pollingManager.getPollingState()
    };
  }
}

// 导出单例实例
export const realTimeTaskService = new RealTimeTaskService();