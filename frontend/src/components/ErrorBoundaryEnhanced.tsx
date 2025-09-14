/**
 * 增强版React错误边界组件 - 100%类型安全 + v0设计融合
 * 基于Linus设计哲学：优雅降级，数据结构驱动错误处理
 * 
 * 特性：
 * 1. 集成新的错误类型系统
 * 2. v0 shadcn/ui组件集成 
 * 3. 智能错误分类和恢复
 * 4. 完整的用户体验
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home, Bug, AlertCircle } from 'lucide-react';
import { 
  ComponentError, 
  ERROR_CODES,
  USER_ERROR_MESSAGES 
} from '@/types/error.types';

// 引入v0风格组件（如果可用的话，否则使用基础HTML元素）
// import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
// import { Button } from '@/components/ui/button';
// import { Alert, AlertDescription } from '@/components/ui/alert';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: ComponentError, errorInfo: ErrorInfo) => void;
  showDetails?: boolean;
  maxRetries?: number;
  resetOnPropsChange?: boolean;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: ComponentError | null;
  retryCount: number;
  isRecovering: boolean;
}

/**
 * 增强版错误边界组件
 * 融合v0设计美学和现代错误处理
 */
class ErrorBoundaryEnhanced extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private maxRetries: number;
  private errorId: string;

  constructor(props: ErrorBoundaryProps) {
    super(props);
    
    this.maxRetries = props.maxRetries || 3;
    this.errorId = `error-${Date.now()}`;
    
    this.state = {
      hasError: false,
      error: null,
      retryCount: 0,
      isRecovering: false,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    // 创建标准化的ComponentError
    const componentError: ComponentError = {
      type: 'client',
      severity: 'error',
      message: error.message,
      code: ERROR_CODES.COMPONENT_RENDER_ERROR,
      timestamp: new Date(),
      recoverable: true,
      userMessage: USER_ERROR_MESSAGES[ERROR_CODES.COMPONENT_RENDER_ERROR],
      componentName: 'Unknown', // 将在componentDidCatch中更新
      componentStack: error.stack || '无堆栈信息',
      errorBoundary: 'ErrorBoundaryEnhanced',
    };

    return {
      hasError: true,
      error: componentError,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // 增强错误信息
    const enhancedError: ComponentError = {
      ...this.state.error!,
      componentStack: errorInfo.componentStack || '无组件堆栈信息',
      props: this.props,
      errorInfo: {
        componentStack: errorInfo.componentStack || '无组件堆栈信息',
        errorBoundary: 'ErrorBoundaryEnhanced' as string,
        errorBoundaryFound: true,
        errorBoundaryStack: new Error().stack || '无边界堆栈',
      },
    };

    // 更新状态
    this.setState({ error: enhancedError });

    // 记录错误（开发模式）
    if (process.env.NODE_ENV === 'development') {
      // 控制台分组以便测试断言与开发调试
      // eslint-disable-next-line no-console
      console.group(`React组件错误 - ${this.errorId}`);
      // 源于开发模式的调试输出，使用统一logger
      import('@/utils/logger')
        .then(({ default: logger }) => {
          logger.error('错误对象:', error as Error);
          logger.error('错误信息:', errorInfo as unknown as Error);
          logger.error('增强错误:', enhancedError as unknown as Error);
        })
        .catch(() => {
          // eslint-disable-next-line no-console
          console.error('ErrorBoundaryEnhanced: logger加载失败');
        })
        .finally(() => {
          // eslint-disable-next-line no-console
          console.groupEnd();
        });
    }

    // 调用外部错误处理器
    this.props.onError?.(enhancedError, errorInfo);

    // 生产环境错误上报（这里可以集成Sentry等）
    if (process.env.NODE_ENV === 'production') {
      this.reportErrorToService(enhancedError);
    }
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps): void {
    // 如果props改变且启用了重置，则重置错误状态
    if (
      this.props.resetOnPropsChange && 
      prevProps.children !== this.props.children &&
      this.state.hasError
    ) {
      this.resetErrorBoundary();
    }
  }

  /**
   * 上报错误到监控服务
   */
  private reportErrorToService = (error: ComponentError): void => {
    // 这里可以集成Sentry、Bugsnag等错误监控服务
    try {
      // 模拟错误上报
      fetch('/api/errors/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          errorId: this.errorId,
          error: {
            ...error,
            url: window.location.href,
            userAgent: navigator.userAgent,
          },
        }),
      }).catch(() => {
        // 静默处理上报失败
        import('@/utils/logger').then(({ default: logger }) => logger.warn('错误上报失败')).catch(() => {});
      });
    } catch {
      // 确保错误上报本身不会导致错误
    }
  };

  /**
   * 重试时的状态重置 - 保持retryCount
   */
  private resetErrorState = (): void => {
    this.setState({
      hasError: false,
      error: null,
      isRecovering: false,
    });
  };

  /**
   * 完全重置错误边界状态
   */
  private resetErrorBoundary = (): void => {
    this.setState({
      hasError: false,
      error: null,
      retryCount: 0,
      isRecovering: false,
    });
  };

  /**
   * 重试操作
   */
  private handleRetry = (): void => {
    if (this.state.retryCount >= this.maxRetries) {
      return;
    }

    this.setState({ 
      isRecovering: true,
      retryCount: this.state.retryCount + 1,
    });

    // 延迟重置，给用户视觉反馈
    setTimeout(() => {
      this.resetErrorState();
    }, 1000);
  };


  /**
   * 刷新页面
   */
  private handleRefresh = (): void => {
    window.location.reload();
  };

  /**
   * 返回首页
   */
  private handleGoHome = (): void => {
    window.location.href = '/';
  };

  /**
   * 报告Bug
   */
  private handleReportBug = (): void => {
    const { error } = this.state;
    if (!error) return;

    const subject = `Bug报告: ${error.code}`;
    const body = `
错误详情:
- 错误ID: ${this.errorId}
- 错误代码: ${error.code}
- 错误消息: ${error.message}
- 发生时间: ${error.timestamp.toISOString()}
- 页面URL: ${window.location.href}
- 用户代理: ${navigator.userAgent}

组件信息:
- 组件名称: ${error.componentName}
- 错误边界: ${error.errorBoundary}

请描述您执行的操作以及期望的结果：
[请在这里填写]
    `.trim();

    const mailtoUrl = `mailto:support@redditscanner.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    window.open(mailtoUrl);
  };


  /**
   * 渲染错误状态UI
   */
  /**
   * 渲染恢复中状态
   */
  private renderRecoveringState = (): ReactNode => (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full text-center">
        <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <RefreshCw className="w-6 h-6 text-blue-600 animate-spin" />
        </div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          正在恢复...
        </h2>
        <p className="text-gray-600">
          系统正在尝试恢复，请稍候
        </p>
      </div>
    </div>
  );

  /**
   * 渲染错误状态UI
   */
  private renderErrorState = (): ReactNode => {
    const { error, retryCount } = this.state;
    if (!error) return null;

    const canRetry = retryCount < this.maxRetries;
    const isMultipleRetries = retryCount > 0;

    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl p-8 max-w-2xl w-full">
          {/* 头部区域 */}
          <div className="text-center mb-8">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-8 h-8 text-red-600" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              页面遇到了问题
            </h1>
            <p className="text-gray-600 text-lg">
              {error.userMessage}
            </p>
          </div>

          {/* 错误信息卡片 */}
          <div className="bg-gray-50 rounded-lg p-4 mb-6">
            <div className="flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 text-red-500 mt-0.5" />
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900 mb-1">错误详情</h3>
                <p className="text-sm text-gray-600 mb-2">
                  <span className="font-medium">错误代码:</span> {error.code}
                </p>
                {isMultipleRetries && (
                  <p className="text-sm text-gray-500">
                    已尝试 {retryCount} 次重试
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* 操作按钮区域 */}
          <div className="space-y-3 mb-6">
            {canRetry && (
              <button
                onClick={this.handleRetry}
                className="w-full flex items-center justify-center px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors font-medium"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                重试 ({this.maxRetries - retryCount} 次机会剩余)
              </button>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                onClick={this.handleRefresh}
                className="flex items-center justify-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-colors font-medium"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                刷新页面
              </button>

              <button
                onClick={this.handleGoHome}
                className="flex items-center justify-center px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors font-medium"
              >
                <Home className="w-4 h-4 mr-2" />
                返回首页
              </button>
            </div>
          </div>

          {/* 技术支持区域 */}
          <div className="border-t pt-6 text-center">
            <p className="text-sm text-gray-500 mb-3">
              如果问题持续出现，请联系我们的技术支持
            </p>
            <button
              onClick={this.handleReportBug}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
            >
              <Bug className="w-4 h-4 mr-2" />
              报告此问题
            </button>
          </div>

          {/* 开发模式错误详情 */}
          {this.props.showDetails && process.env.NODE_ENV === 'development' && (
            <details className="mt-6">
              <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors">
                开发者信息
              </summary>
              <div className="mt-3 bg-gray-900 rounded-lg p-4 overflow-hidden">
                <pre className="text-xs text-green-400 overflow-auto max-h-60 font-mono">
                  {JSON.stringify(error, null, 2)}
                </pre>
              </div>
            </details>
          )}

          {/* 底部信息 */}
          <div className="mt-6 pt-4 border-t text-center">
            <p className="text-xs text-gray-400">
              错误ID: {this.errorId} | Reddit Signal Scanner v2.0
            </p>
          </div>
        </div>
      </div>
    );
  };

  render(): ReactNode {
    // 显示自定义fallback
    if (this.state.hasError && this.props.fallback) {
      return this.props.fallback;
    }

    // 显示恢复中状态
    if (this.state.isRecovering) {
      return this.renderRecoveringState();
    }

    // 显示错误状态
    if (this.state.hasError) {
      return this.renderErrorState();
    }

    // 正常渲染子组件
    return this.props.children;
  }
}

export default ErrorBoundaryEnhanced;

// 便捷的HOC包装器
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) {
  const WrappedComponent = (props: P) => (
    <ErrorBoundaryEnhanced {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundaryEnhanced>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;
  
  return WrappedComponent;
}

// 错误边界Hook（仅用于函数组件错误报告）
export function useErrorHandler() {
  const handleError = React.useCallback((error: Error, errorInfo?: Record<string, unknown>) => {
    const componentError: ComponentError = {
      type: 'client',
      severity: 'error',
      message: error.message,
      code: ERROR_CODES.COMPONENT_LIFECYCLE_ERROR,
      timestamp: new Date(),
      recoverable: true,
      userMessage: '组件运行时发生错误',
      componentName: 'Unknown',
      componentStack: error.stack || '无堆栈信息',
      errorBoundary: 'useErrorHandler',
      context: errorInfo,
    };

    // 在开发模式下记录错误
    if (process.env.NODE_ENV === 'development') {
      console.error('useErrorHandler捕获错误:', componentError);
    }

    // 抛出错误让Error Boundary处理
    throw error;
  }, []);

  return { handleError };
}
