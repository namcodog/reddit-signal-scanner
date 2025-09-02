/**
 * 智能错误处理系统 - 消灭代码质量技术债务
 * 基于 Linus 错误处理原则：Fail fast, fail clear
 *
 * 解决问题：
 * 1. 错误分类和用户友好消息
 * 2. 边缘情况完整处理
 * 3. 错误恢复策略
 * 4. 错误上报和监控
 */

// 错误类型枚举
export enum ErrorType {
  NETWORK = 'network',
  VALIDATION = 'validation',
  AUTHENTICATION = 'authentication',
  PERMISSION = 'permission',
  RATE_LIMIT = 'rate_limit',
  SERVER_ERROR = 'server_error',
  CLIENT_ERROR = 'client_error',
  UNKNOWN = 'unknown',
}

// 错误严重级别
export enum ErrorSeverity {
  LOW = 'low', // 可忽略的警告
  MEDIUM = 'medium', // 影响功能但不阻塞
  HIGH = 'high', // 阻塞用户操作
  CRITICAL = 'critical', // 系统级错误
}

// 错误信息接口
export interface ErrorInfo {
  type: ErrorType;
  severity: ErrorSeverity;
  message: string;
  userMessage: string;
  canRetry: boolean;
  retryDelay?: number;
  recoveryActions?: string[];
}

// 错误上下文信息
export interface ErrorContext {
  component?: string;
  action?: string;
  userId?: string;
  sessionId?: string;
  timestamp: number;
  userAgent: string;
  url: string;
}

/**
 * 智能错误分类器 - 根据错误内容自动分类
 */
export class ErrorClassifier {
  private static readonly ERROR_PATTERNS: Record<ErrorType, RegExp[]> = {
    [ErrorType.NETWORK]: [
      /network error/i,
      /fetch.*failed/i,
      /connection.*refused/i,
      /timeout/i,
      /dns.*error/i,
      /no.*internet/i,
    ],
    [ErrorType.VALIDATION]: [
      /validation.*failed/i,
      /invalid.*input/i,
      /required.*field/i,
      /格式.*错误/i,
      /输入.*无效/i,
    ],
    [ErrorType.AUTHENTICATION]: [
      /unauthorized/i,
      /401/,
      /authentication.*failed/i,
      /invalid.*credentials/i,
      /登录.*失败/i,
      /身份.*验证/i,
    ],
    [ErrorType.PERMISSION]: [
      /forbidden/i,
      /403/,
      /permission.*denied/i,
      /access.*denied/i,
      /权限.*不足/i,
    ],
    [ErrorType.RATE_LIMIT]: [
      /rate.*limit/i,
      /429/,
      /too.*many.*requests/i,
      /请求.*频繁/i,
      /限流/i,
    ],
    [ErrorType.SERVER_ERROR]: [
      /5\d{2}/,
      /internal.*server.*error/i,
      /service.*unavailable/i,
      /服务器.*错误/i,
      /系统.*维护/i,
    ],
    [ErrorType.CLIENT_ERROR]: [
      /4\d{2}/,
      /bad.*request/i,
      /not.*found/i,
      /客户端.*错误/i,
    ],
    [ErrorType.UNKNOWN]: [/unknown/i, /unexpected/i],
  };

  /**
   * 智能分类错误类型
   */
  static classify(error: Error | string): ErrorType {
    const message = typeof error === 'string' ? error : error.message;

    for (const [type, patterns] of Object.entries(this.ERROR_PATTERNS)) {
      for (const pattern of patterns) {
        if (pattern.test(message)) {
          return type as ErrorType;
        }
      }
    }

    return ErrorType.UNKNOWN;
  }

  /**
   * 获取错误严重级别
   */
  static getSeverity(errorType: ErrorType): ErrorSeverity {
    switch (errorType) {
      case ErrorType.AUTHENTICATION:
      case ErrorType.PERMISSION:
      case ErrorType.SERVER_ERROR:
        return ErrorSeverity.HIGH;
      case ErrorType.NETWORK:
      case ErrorType.RATE_LIMIT:
        return ErrorSeverity.MEDIUM;
      case ErrorType.VALIDATION:
      case ErrorType.CLIENT_ERROR:
        return ErrorSeverity.LOW;
      case ErrorType.UNKNOWN:
      default:
        return ErrorSeverity.MEDIUM;
    }
  }

  /**
   * 获取用户友好的错误消息
   */
  static getUserFriendlyMessage(
    errorType: ErrorType,
    _originalMessage?: string
  ): string {
    const messages: Record<ErrorType, string> = {
      [ErrorType.NETWORK]: '网络连接失败，请检查网络设置后重试',
      [ErrorType.VALIDATION]: '输入信息有误，请检查后重新提交',
      [ErrorType.AUTHENTICATION]: '登录已过期，请重新登录',
      [ErrorType.PERMISSION]: '您没有执行此操作的权限',
      [ErrorType.RATE_LIMIT]: '操作过于频繁，请稍后再试',
      [ErrorType.SERVER_ERROR]: '服务暂时不可用，请稍后重试',
      [ErrorType.CLIENT_ERROR]: '请求格式错误，请刷新页面重试',
      [ErrorType.UNKNOWN]: '操作失败，请稍后重试',
    };

    return messages[errorType] || messages[ErrorType.UNKNOWN];
  }

  /**
   * 判断错误是否可以重试
   */
  static canRetry(errorType: ErrorType): boolean {
    const retryableTypes = [
      ErrorType.NETWORK,
      ErrorType.RATE_LIMIT,
      ErrorType.SERVER_ERROR,
      ErrorType.UNKNOWN,
    ];

    return retryableTypes.includes(errorType);
  }

  /**
   * 获取重试延迟时间(毫秒)
   */
  static getRetryDelay(errorType: ErrorType, attemptCount: number): number {
    const baseDelays: Record<ErrorType, number> = {
      [ErrorType.NETWORK]: 1000,
      [ErrorType.RATE_LIMIT]: 5000,
      [ErrorType.SERVER_ERROR]: 2000,
      [ErrorType.UNKNOWN]: 1500,
      [ErrorType.VALIDATION]: 0,
      [ErrorType.AUTHENTICATION]: 0,
      [ErrorType.PERMISSION]: 0,
      [ErrorType.CLIENT_ERROR]: 0,
    };

    const baseDelay = baseDelays[errorType] || 1000;

    // 指数退避策略
    return Math.min(baseDelay * Math.pow(2, attemptCount - 1), 30000);
  }

  /**
   * 获取恢复建议
   */
  static getRecoveryActions(errorType: ErrorType): string[] {
    const actions: Record<ErrorType, string[]> = {
      [ErrorType.NETWORK]: ['检查网络连接', '刷新页面重试', '切换到移动网络'],
      [ErrorType.VALIDATION]: ['检查输入格式', '填写必填字段', '减少输入长度'],
      [ErrorType.AUTHENTICATION]: ['重新登录', '清除浏览器缓存', '联系管理员'],
      [ErrorType.PERMISSION]: [
        '联系管理员获取权限',
        '切换到有权限的账号',
        '返回上一页',
      ],
      [ErrorType.RATE_LIMIT]: ['等待片刻后重试', '减少操作频率', '稍后再试'],
      [ErrorType.SERVER_ERROR]: ['稍后重试', '刷新页面', '联系技术支持'],
      [ErrorType.CLIENT_ERROR]: ['刷新页面', '清除浏览器缓存', '检查URL地址'],
      [ErrorType.UNKNOWN]: ['刷新页面重试', '检查网络连接', '联系技术支持'],
    };

    return actions[errorType] || actions[ErrorType.UNKNOWN];
  }
}

/**
 * 全局错误处理器 - 统一处理所有错误
 */
export class GlobalErrorHandler {
  private static instance: GlobalErrorHandler;
  private errorLog: Array<ErrorInfo & ErrorContext> = [];
  private readonly MAX_LOG_SIZE = 100;

  static getInstance(): GlobalErrorHandler {
    if (!this.instance) {
      this.instance = new GlobalErrorHandler();
    }
    return this.instance;
  }

  /**
   * 处理错误 - 分类、记录、返回处理建议
   */
  handleError(
    error: Error | string,
    context: Partial<ErrorContext> = {}
  ): ErrorInfo {
    const errorType = ErrorClassifier.classify(error);
    const severity = ErrorClassifier.getSeverity(errorType);
    const message = typeof error === 'string' ? error : error.message;
    const userMessage = ErrorClassifier.getUserFriendlyMessage(
      errorType,
      message
    );
    const canRetry = ErrorClassifier.canRetry(errorType);
    const retryDelay = canRetry
      ? ErrorClassifier.getRetryDelay(errorType, 1)
      : undefined;
    const recoveryActions = ErrorClassifier.getRecoveryActions(errorType);

    const errorInfo: ErrorInfo = {
      type: errorType,
      severity,
      message,
      userMessage,
      canRetry,
      retryDelay,
      recoveryActions,
    };

    // 记录错误上下文
    const fullContext: ErrorContext = {
      timestamp: Date.now(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      ...context,
    };

    // 添加到错误日志
    this.addToErrorLog(errorInfo, fullContext);

    // 严重错误自动上报
    if (
      severity === ErrorSeverity.CRITICAL ||
      severity === ErrorSeverity.HIGH
    ) {
      this.reportError(errorInfo, fullContext);
    }

    return errorInfo;
  }

  /**
   * 添加到错误日志
   */
  private addToErrorLog(errorInfo: ErrorInfo, context: ErrorContext): void {
    this.errorLog.push({ ...errorInfo, ...context });

    // 保持日志大小限制
    if (this.errorLog.length > this.MAX_LOG_SIZE) {
      this.errorLog.shift();
    }
  }

  /**
   * 上报错误到监控服务
   */
  private async reportError(
    errorInfo: ErrorInfo,
    context: ErrorContext
  ): Promise<void> {
    try {
      // TODO: 实际项目中发送到错误监控服务
      console.group('🚨 Error Report');
      console.error('Error:', errorInfo);
      console.log('Context:', context);
      console.groupEnd();

      // 模拟上报API调用
      // await fetch('/api/errors', {
      //   method: 'POST',
      //   body: JSON.stringify({ error: errorInfo, context })
      // });
    } catch (reportError) {
      console.error('Failed to report error:', reportError);
    }
  }

  /**
   * 获取错误统计
   */
  getErrorStats(): Record<ErrorType, number> {
    const stats: Record<ErrorType, number> = {} as Record<ErrorType, number>;

    // 初始化统计
    Object.values(ErrorType).forEach(type => {
      stats[type] = 0;
    });

    // 计算统计
    this.errorLog.forEach(error => {
      stats[error.type]++;
    });

    return stats;
  }

  /**
   * 清除错误日志
   */
  clearErrorLog(): void {
    this.errorLog = [];
  }

  /**
   * 获取最近的错误
   */
  getRecentErrors(count: number = 10): Array<ErrorInfo & ErrorContext> {
    return this.errorLog.slice(-count);
  }
}

/**
 * 便捷的错误处理函数
 */
export function handleError(
  error: Error | string,
  context?: Partial<ErrorContext>
): ErrorInfo {
  return GlobalErrorHandler.getInstance().handleError(error, context);
}

/**
 * 异步操作错误处理装饰器
 */
export function withErrorHandling<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  context?: Partial<ErrorContext>
): T {
  return (async (...args: any[]) => {
    try {
      return await fn(...args);
    } catch (error) {
      const errorInfo = handleError(error as Error, {
        component: fn.name,
        action: 'async_operation',
        ...context,
      });
      throw new Error(errorInfo.userMessage);
    }
  }) as T;
}

export default GlobalErrorHandler;
