/**
 * 错误处理类型系统 - 100%类型安全
 * 基于Linus设计哲学：数据结构优先，清晰的错误分类体系
 * 
 * 设计原则：
 * 1. 单一数据源：所有错误通过AppError联合类型
 * 2. 类型驱动：错误处理逻辑完全由类型决定  
 * 3. 组合优于继承：使用联合类型而非类继承
 * 4. 向后兼容：与现有Error类兼容
 */

// 错误类型分类（基于HTTP语义扩展）
export type ErrorType = 
  | 'network'           // 网络连接错误
  | 'validation'        // 表单验证错误  
  | 'authentication'    // 认证授权错误
  | 'permission'        // 权限错误
  | 'server'           // 服务器错误
  | 'client'           // 客户端错误
  | 'business'         // 业务逻辑错误
  | 'unknown';         // 未知错误

// 错误严重级别（影响UI展示方式）
export type ErrorSeverity = 
  | 'info'        // 信息提示，蓝色
  | 'warning'     // 警告提示，橙色  
  | 'error'       // 错误提示，红色
  | 'critical';   // 严重错误，模态框

// 基础错误接口（所有错误类型的公共字段）
export interface BaseError {
  readonly type: ErrorType;
  readonly severity: ErrorSeverity;
  readonly message: string;           // 技术错误信息
  readonly code: string;              // 错误代码
  readonly timestamp: Date;           // 发生时间
  readonly recoverable: boolean;      // 是否可恢复
  readonly userMessage: string;       // 用户友好消息
  readonly context?: Record<string, unknown>; // 错误上下文
}

// API错误接口（HTTP请求相关错误）
export interface APIError extends BaseError {
  readonly type: 'server' | 'network' | 'authentication' | 'permission' | 'business';
  readonly statusCode?: number;       // HTTP状态码
  readonly endpoint?: string;         // 请求端点
  readonly method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'; // HTTP方法
  readonly requestId?: string;        // 请求跟踪ID
  readonly details?: Record<string, unknown>; // 服务器返回的详细信息
  readonly retryable: boolean;        // 是否可重试
  readonly retryAfter?: number;       // 重试等待时间(秒)
}

// 表单验证错误
export interface ValidationError extends BaseError {
  readonly type: 'validation';
  readonly field: string;             // 字段名
  readonly value: unknown;            // 字段值
  readonly constraint: string;        // 验证约束
  readonly validationRule: string;    // 验证规则名称
}

// 网络连接错误  
export interface NetworkError extends BaseError {
  readonly type: 'network';
  readonly cause: 'timeout' | 'offline' | 'dns' | 'cors' | 'connection' | 'unknown';
  readonly retryable: true;           // 网络错误通常可重试
  readonly url?: string;              // 失败的URL
}

// React组件错误（Error Boundary捕获）
export interface ComponentError extends BaseError {
  readonly type: 'client';
  readonly componentName: string;     // 出错组件名称
  readonly componentStack: string;    // 组件调用栈
  readonly errorBoundary: string;     // 错误边界名称
  readonly props?: Record<string, unknown>; // 组件props
  readonly errorInfo?: ReactErrorInfo; // React错误信息
}

// 业务逻辑错误
export interface BusinessError extends BaseError {
  readonly type: 'business';
  readonly businessCode: string;      // 业务错误码
  readonly businessContext: Record<string, unknown>; // 业务上下文
  readonly resolution?: string;       // 解决建议
}

// 联合错误类型（所有可能的错误）
export type AppError = 
  | APIError 
  | ValidationError 
  | NetworkError 
  | ComponentError 
  | BusinessError;

// 错误处理结果（描述如何处理错误）
export interface ErrorHandlingResult {
  readonly handled: boolean;          // 是否已处理
  readonly shouldRetry: boolean;      // 是否应该重试
  readonly userNotification: {        // 用户通知配置
    readonly show: boolean;
    readonly message: string;
    readonly type: 'toast' | 'inline' | 'modal' | 'banner';
    readonly duration?: number;       // 显示时长(ms)，0表示不自动关闭
    readonly persistent?: boolean;    // 是否持久显示
  };
  readonly recovery?: {               // 错误恢复选项
    readonly available: boolean;
    readonly action: () => void | Promise<void>;
    readonly label: string;
    readonly icon?: React.ComponentType<{ className?: string }>;
  };
  readonly logging?: {                // 日志记录配置
    readonly level: 'debug' | 'info' | 'warn' | 'error';
    readonly report: boolean;         // 是否上报到服务器
    readonly includeStack: boolean;   // 是否包含堆栈信息
  };
}

// 错误报告配置（全局设置）
export interface ErrorReportingConfig {
  readonly enableConsoleLogging: boolean;   // 控制台日志
  readonly enableRemoteLogging: boolean;    // 远程日志上报
  readonly enableUserFeedback: boolean;     // 用户反馈收集
  readonly excludeErrorTypes: ErrorType[];  // 排除的错误类型
  readonly maxErrorsPerSession: number;     // 会话最大错误数
  readonly debugMode: boolean;              // 调试模式
}

// 错误统计信息
export interface ErrorStatistics {
  readonly totalErrors: number;
  readonly errorsByType: Record<ErrorType, number>;
  readonly errorsBySeverity: Record<ErrorSeverity, number>;
  readonly mostRecentErrors: AppError[];
  readonly mostFrequentErrors: Array<{
    code: string;
    count: number;
    lastOccurrence: Date;
  }>;
}

// 错误创建工厂函数类型
export type ErrorFactory<T extends AppError = AppError> = (
  message: string,
  options?: Partial<Omit<T, 'message' | 'timestamp' | 'type'>>
) => T;

// 错误处理器函数类型
export type ErrorHandler<T extends AppError = AppError> = (
  error: T
) => ErrorHandlingResult;

// 错误过滤器函数类型（用于日志和通知过滤）
export type ErrorFilter = (error: AppError) => boolean;

// 错误变换器函数类型（用于错误格式转换）
export type ErrorTransformer<TInput, TOutput extends AppError> = (
  input: TInput
) => TOutput;

// 预定义的错误代码常量
export const ERROR_CODES = {
  // 网络错误
  NETWORK_TIMEOUT: 'NETWORK_TIMEOUT',
  NETWORK_OFFLINE: 'NETWORK_OFFLINE',
  NETWORK_DNS_ERROR: 'NETWORK_DNS_ERROR',
  NETWORK_CONNECTION_ERROR: 'NETWORK_CONNECTION_ERROR',
  
  // HTTP错误
  HTTP_UNAUTHORIZED: 'HTTP_401',
  HTTP_FORBIDDEN: 'HTTP_403',
  HTTP_NOT_FOUND: 'HTTP_404',
  HTTP_RATE_LIMITED: 'HTTP_429',
  HTTP_INTERNAL_ERROR: 'HTTP_500',
  HTTP_BAD_GATEWAY: 'HTTP_502',
  HTTP_SERVICE_UNAVAILABLE: 'HTTP_503',
  HTTP_GATEWAY_TIMEOUT: 'HTTP_504',
  
  // 验证错误
  VALIDATION_REQUIRED: 'VALIDATION_REQUIRED',
  VALIDATION_FORMAT: 'VALIDATION_FORMAT',
  VALIDATION_LENGTH: 'VALIDATION_LENGTH',
  VALIDATION_RANGE: 'VALIDATION_RANGE',
  
  // 业务错误
  BUSINESS_RULE_VIOLATION: 'BUSINESS_RULE_VIOLATION',
  BUSINESS_STATE_INVALID: 'BUSINESS_STATE_INVALID',
  BUSINESS_PERMISSION_DENIED: 'BUSINESS_PERMISSION_DENIED',
  
  // 客户端错误
  COMPONENT_RENDER_ERROR: 'COMPONENT_RENDER_ERROR',
  COMPONENT_LIFECYCLE_ERROR: 'COMPONENT_LIFECYCLE_ERROR',
  CLIENT_STORAGE_ERROR: 'CLIENT_STORAGE_ERROR',
  
  // 未知错误
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
} as const;

// 错误代码类型
export type ErrorCode = typeof ERROR_CODES[keyof typeof ERROR_CODES];

// 预定义的用户友好错误消息
export const USER_ERROR_MESSAGES = {
  [ERROR_CODES.NETWORK_TIMEOUT]: '请求超时，请检查网络连接后重试',
  [ERROR_CODES.NETWORK_OFFLINE]: '网络连接已断开，请检查网络设置',
  [ERROR_CODES.HTTP_UNAUTHORIZED]: '登录已过期，请重新登录',
  [ERROR_CODES.HTTP_FORBIDDEN]: '权限不足，无法执行此操作',
  [ERROR_CODES.HTTP_NOT_FOUND]: '请求的资源不存在',
  [ERROR_CODES.HTTP_RATE_LIMITED]: '操作过于频繁，请稍后再试',
  [ERROR_CODES.HTTP_INTERNAL_ERROR]: '服务器内部错误，请稍后重试',
  [ERROR_CODES.VALIDATION_REQUIRED]: '此字段为必填项',
  [ERROR_CODES.VALIDATION_FORMAT]: '输入格式不正确',
  [ERROR_CODES.COMPONENT_RENDER_ERROR]: '页面渲染出现问题，正在尝试修复',
  [ERROR_CODES.UNKNOWN_ERROR]: '发生了未知错误，请联系技术支持',
} as const;

// 类型守卫函数
export const isAPIError = (error: AppError): error is APIError => 
  ['server', 'network', 'authentication', 'permission', 'business'].includes(error.type);

export const isValidationError = (error: AppError): error is ValidationError => 
  error.type === 'validation';

export const isNetworkError = (error: AppError): error is NetworkError => 
  error.type === 'network';

export const isComponentError = (error: AppError): error is ComponentError => 
  error.type === 'client';

export const isBusinessError = (error: AppError): error is BusinessError => 
  error.type === 'business';

// 错误严重性判断
export const isCriticalError = (error: AppError): boolean => 
  error.severity === 'critical';

export const isRecoverableError = (error: AppError): boolean => 
  error.recoverable;

// 兼容性：与现有Error类的互操作
export interface ErrorCompatibility {
  /**
   * 将标准Error转换为AppError
   */
  fromError(error: Error, type?: ErrorType): AppError;
  
  /**
   * 将AppError转换为标准Error（向后兼容）
   */
  toError(appError: AppError): Error;
  
  /**
   * 检查是否为AppError实例
   */
  isAppError(error: unknown): error is AppError;
}

// React ErrorInfo备用定义（避免React依赖）

// 如果需要React.ErrorInfo但未安装React类型，提供备用定义
export interface ReactErrorInfo {
  componentStack: string;
  errorBoundary?: string | null;
  errorBoundaryFound: boolean;
  errorBoundaryStack?: string | null;
}

// 默认配置
export const DEFAULT_ERROR_CONFIG: ErrorReportingConfig = {
  enableConsoleLogging: process.env.NODE_ENV === 'development',
  enableRemoteLogging: process.env.NODE_ENV === 'production',
  enableUserFeedback: true,
  excludeErrorTypes: [],
  maxErrorsPerSession: 100,
  debugMode: process.env.NODE_ENV === 'development',
} as const;