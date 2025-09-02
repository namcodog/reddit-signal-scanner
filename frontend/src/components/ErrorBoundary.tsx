/**
 * React Error Boundary - 增强版
 * 基于 Linus 简洁原则：优雅降级，不破坏用户体验
 * 
 * 技术债务消除：集成智能错误处理系统
 */

import { Component, ErrorInfo, ReactNode } from 'react';
import { handleError } from '@/utils/errorHandler';

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
  userMessage?: string;
  canRetry?: boolean;
  recoveryActions?: string[];
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

/**
 * 增强版错误边界组件 - 智能错误分类和处理
 */
class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // 使用智能错误处理系统
    const errorReport = handleError(error, {
      component: 'ErrorBoundary',
      action: 'react_component_error',
      // 从错误堆栈提取更多上下文
      ...(errorInfo.componentStack && {
        sessionId: Date.now().toString()
      })
    });
    
    // 更新状态，包含用户友好信息
    this.setState({
      error,
      errorInfo,
      userMessage: errorReport.userMessage,
      canRetry: errorReport.canRetry,
      recoveryActions: errorReport.recoveryActions
    });

    console.error('React Error Boundary - Classified error:', errorReport);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  private handleGoHome = (): void => {
    window.location.href = '/';
  };

  private handleRetry = (): void => {
    // 清除错误状态，重新渲染
    this.setState({ 
      hasError: false, 
      error: undefined,
      errorInfo: undefined,
      userMessage: undefined,
      canRetry: undefined,
      recoveryActions: undefined
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      const { userMessage, canRetry, recoveryActions } = this.state;
      
      return (
        <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
          <div className="max-w-lg w-full bg-white rounded-xl shadow-lg p-8 text-center">
            {/* 错误图标 */}
            <div className="text-6xl mb-6">😵‍💫</div>
            
            {/* 错误标题 */}
            <h1 className="text-2xl font-bold text-gray-900 mb-4">
              糟糕！出现了错误
            </h1>
            
            {/* 用户友好的错误消息 */}
            <p className="text-gray-600 mb-8">
              {userMessage || '应用遇到了意外错误，请尝试以下操作'}
            </p>

            {/* 恢复建议 */}
            {recoveryActions && recoveryActions.length > 0 && (
              <div className="mb-8">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">建议操作：</h3>
                <ul className="text-sm text-gray-600 space-y-1">
                  {recoveryActions.map((action, index) => (
                    <li key={index} className="flex items-center">
                      <span className="text-blue-500 mr-2">•</span>
                      {action}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 操作按钮 */}
            <div className="space-y-3">
              {canRetry && (
                <button
                  onClick={this.handleRetry}
                  className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 font-medium transition-colors"
                >
                  重试
                </button>
              )}
              
              <button
                onClick={this.handleReload}
                className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 font-medium transition-colors"
              >
                刷新页面
              </button>
              
              <button
                onClick={this.handleGoHome}
                className="w-full px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 font-medium transition-colors"
              >
                返回首页
              </button>
            </div>

            {/* 开发环境错误详情 */}
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="mt-8 text-left">
                <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-700 transition-colors">
                  错误详情 (开发环境)
                </summary>
                <pre className="mt-3 text-xs text-red-600 bg-red-50 p-4 rounded-lg overflow-auto max-h-40 font-mono border border-red-200">
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack && (
                    <>
                      {'\n\nComponent Stack:'}
                      {this.state.errorInfo.componentStack}
                    </>
                  )}
                </pre>
              </details>
            )}

            {/* 底部提示 */}
            <div className="mt-8 text-xs text-gray-400">
              <p>如果问题持续存在，请联系技术支持</p>
              <p className="mt-1">Reddit Signal Scanner - 基于Linus设计哲学</p>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;