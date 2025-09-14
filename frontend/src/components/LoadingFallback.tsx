/**
 * 加载回退组件 - 用于Suspense fallback
 * 简单优雅的加载提示
 */

import React from 'react';

const LoadingFallback: React.FC = () => {
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">加载中...</p>
      </div>
    </div>
  );
};

export default LoadingFallback;