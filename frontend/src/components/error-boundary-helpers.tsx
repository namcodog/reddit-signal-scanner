import React from 'react';
import ErrorBoundaryEnhanced from '@/components/ErrorBoundaryEnhanced';
import type { ErrorBoundaryProps } from '@/components/ErrorBoundaryEnhanced';
import type { ComponentError } from '@/types/error.types';
import { ERROR_CODES } from '@/types/error.types';

export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<ErrorBoundaryProps, 'children'>
) {
  const WrappedComponent: React.FC<P> = (props) => (
    <ErrorBoundaryEnhanced {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundaryEnhanced>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;

  return WrappedComponent;
}

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

    if (process.env.NODE_ENV === 'development') {
      console.error('useErrorHandler捕获错误:', componentError);
    }

    throw error;
  }, []);

  return { handleError };
}
