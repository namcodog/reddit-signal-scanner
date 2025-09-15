/**
 * API调用基础类型定义
 * 统一前后端接口规范
 */

// 基础API响应结构
export interface ApiResponse<T = unknown> {
  success: boolean;
  message: string;
  timestamp: string;
  data: T;
}

// API错误响应
export interface ApiError {
  success: false;
  message: string;
  timestamp: string;
  error_code?: string;
  details?: Record<string, unknown>;
}

// 分页响应
export interface PaginatedResponse<T> {
  success: boolean;
  message: string;
  timestamp: string;
  data: {
    items: T[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  };
}

// HTTP方法枚举
export enum HttpMethod {
  GET = 'GET',
  POST = 'POST',
  PUT = 'PUT',
  DELETE = 'DELETE',
  PATCH = 'PATCH'
}

// 请求配置
export interface RequestConfig {
  method: HttpMethod;
  url: string;
  headers?: Record<string, string>;
  params?: Record<string, unknown>;
  data?: unknown;
  timeout?: number;
  withAuth?: boolean;
}

// API客户端接口
export interface BaseApiClient {
  get<T>(url: string, config?: Partial<RequestConfig>): Promise<ApiResponse<T>>;
  post<T, D = unknown>(url: string, data?: D, config?: Partial<RequestConfig>): Promise<ApiResponse<T>>;
  put<T, D = unknown>(url: string, data?: D, config?: Partial<RequestConfig>): Promise<ApiResponse<T>>;
  delete<T>(url: string, config?: Partial<RequestConfig>): Promise<ApiResponse<T>>;
  patch<T, D = unknown>(url: string, data?: D, config?: Partial<RequestConfig>): Promise<ApiResponse<T>>;
}

// 错误处理类型
export interface ErrorHandler {
  handle(error: ApiError | Error): void;
  shouldRetry(error: ApiError | Error): boolean;
  getRetryDelay(attempt: number): number;
}

// 拦截器类型
export interface RequestInterceptor {
  onRequest?(config: RequestConfig): RequestConfig | Promise<RequestConfig>;
  onRequestError?(error: Error): Error | Promise<Error>;
}

export interface ResponseInterceptor {
  onResponse?<T>(response: ApiResponse<T>): ApiResponse<T> | Promise<ApiResponse<T>>;
  onResponseError?(error: ApiError): ApiError | Promise<ApiError>;
}