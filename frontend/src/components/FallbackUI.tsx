/**
 * 降级UI组件 - PRD-05要求的优雅降级
 * 当SSE和轮询都失败时的最后防线
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';

interface FallbackUIProps {
  taskId: string;
  error: string;
  onRetry: () => void;
}

/**
 * 简单但可用的降级界面
 * Linus: "当所有技术都失败时，至少给用户一条路走"
 */
export const FallbackUI: React.FC<FallbackUIProps> = ({ taskId, error, onRetry }) => {
  const navigate = useNavigate();

  const handleCheckManually = () => {
    window.location.reload(); // 最简单的状态重置
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
        {/* 错误图标 */}
        <div className="text-6xl mb-6">⚠️</div>
        
        {/* 错误标题 */}
        <h2 className="text-2xl font-bold text-gray-900 mb-4">
          连接中断
        </h2>
        
        {/* 错误信息 */}
        <p className="text-gray-600 mb-6">
          实时连接失败：{error}
        </p>
        
        {/* 任务信息 */}
        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          <p className="text-sm text-gray-700 mb-2">
            你的任务正在后台继续处理：
          </p>
          <code className="text-xs bg-white px-2 py-1 rounded border">
            {taskId}
          </code>
        </div>
        
        {/* 操作按钮 */}
        <div className="space-y-3">
          <button
            onClick={onRetry}
            className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            重新连接
          </button>
          
          <button
            onClick={handleCheckManually}
            className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500"
          >
            手动检查状态
          </button>
          
          <button
            onClick={() => navigate('/')}
            className="w-full px-4 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
          >
            重新开始分析
          </button>
        </div>
        
        {/* 提示信息 */}
        <div className="mt-6 text-xs text-gray-500">
          <p>分析任务会继续在后台运行</p>
          <p>你可以稍后返回查看结果</p>
        </div>
      </div>
    </div>
  );
};

export default FallbackUI;