/**
 * 分析等待页面 - SSE实时进度显示
 * Linus: "用户不关心技术实现，只关心能否完成任务"
 * 基于 URL驱动状态，支持页面刷新恢复
 * 
 * PRD-05核心功能：
 * - SSE实时通信，降级到轮询
 * - 状态自动恢复
 * - 智能错误处理
 */

import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTaskProgress } from '@/hooks/useTaskProgress';
import FallbackUI from '@/components/FallbackUI';

/**
 * 分析等待页面 - 基于PRD-05 SSE实时通信
 * Linus: "先让它工作，再让它变好"
 */
const AnalysisPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  
  // 使用SSE Hook进行实时通信
  const { status, error, isConnected, strategy, retry, disconnect, connectionAttempts } = useTaskProgress(taskId);

  // 任务ID验证
  if (!taskId) {
    navigate('/');
    return null;
  }

  // 降级条件：多次连接失败且无有效状态
  const shouldFallback = connectionAttempts >= 3 && !isConnected && !status;
  
  if (shouldFallback) {
    return (
      <FallbackUI 
        taskId={taskId} 
        error={error || '无法建立连接'} 
        onRetry={retry}
      />
    );
  }

  // 状态映射到显示内容
  const getDisplayInfo = () => {
    if (!status) {
      return {
        step: '正在连接服务器...',
        progress: 0
      };
    }

    const statusMap = {
      pending: { step: '任务排队中...', progress: 10 },
      processing: { step: status.message || '分析进行中...', progress: status.progress || 50 },
      completed: { step: '分析完成！', progress: 100 },
      failed: { step: '分析失败', progress: 0 }
    };

    return statusMap[status.status] || { step: '未知状态', progress: 0 };
  };

  const { step, progress } = getDisplayInfo();

  // 自动跳转到报告页面
  React.useEffect(() => {
    if (status?.status === 'completed') {
      const timer = setTimeout(() => {
        navigate(`/report/${taskId}`);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [status?.status, taskId, navigate]);

  const handleCancel = () => {
    disconnect(); // 断开SSE连接
    navigate('/');
  };

  const handleRetry = () => {
    retry(); // 重试连接
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Reddit 信号分析进行中
          </h1>
          <p className="text-gray-600 mb-2">
            任务ID: <code className="bg-gray-100 px-2 py-1 rounded text-sm">{taskId}</code>
          </p>
          
          {/* 连接状态指示 */}
          <div className="flex items-center justify-center space-x-2 text-sm">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className={isConnected ? 'text-green-600' : 'text-red-600'}>
              {isConnected 
                ? `实时连接 (${strategy === 'sse' ? 'SSE' : '轮询'})` 
                : '连接断开'
              }
            </span>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8">
          {/* 进度显示 */}
          <div className="mb-8">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">分析进度</h2>
              <span className="text-sm text-gray-500">{Math.round(progress)}%</span>
            </div>
            
            <div className="w-full bg-gray-200 rounded-full h-4 mb-4">
              <div 
                className="bg-blue-600 h-4 rounded-full transition-all duration-1000 ease-out flex items-center justify-end pr-2"
                style={{ width: `${Math.max(progress, 5)}%` }}
              >
                {progress > 10 && (
                  <div className="text-white text-xs font-medium">
                    {Math.round(progress)}%
                  </div>
                )}
              </div>
            </div>
            
            <div className="text-center">
              <p className="text-gray-700 mb-2">{step}</p>
              {status?.created_at && (
                <p className="text-sm text-gray-500">
                  开始时间: {new Date(status.created_at).toLocaleString()}
                </p>
              )}
            </div>
          </div>

          {/* 分析说明 */}
          <div className="border-t pt-6 mb-6">
            <h3 className="font-semibold mb-3">分析内容包括:</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-gray-600">
              <div className="flex items-center">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                Reddit热门帖子抓取
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                用户评论情感分析
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                关键词提取和聚类
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                商业机会识别
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                竞争对手分析
              </div>
              <div className="flex items-center">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                市场需求评估
              </div>
            </div>
          </div>

          {/* 错误显示 */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-start">
                <div className="text-red-500 mr-3">⚠️</div>
                <div>
                  <p className="text-red-800 font-medium mb-1">连接错误</p>
                  <p className="text-red-700 text-sm mb-3">{error}</p>
                  <button
                    onClick={handleRetry}
                    className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 text-sm"
                  >
                    重新连接
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 失败状态显示 */}
          {status?.status === 'failed' && (
            <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-start">
                <div className="text-yellow-500 mr-3">🚧</div>
                <div>
                  <p className="text-yellow-800 font-medium mb-1">分析失败</p>
                  <p className="text-yellow-700 text-sm mb-3">
                    {status.error_message || '分析过程中遇到错误，请稍后重试'}
                  </p>
                  <button
                    onClick={() => navigate('/')}
                    className="px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 focus:outline-none focus:ring-2 focus:ring-yellow-500 text-sm"
                  >
                    重新开始
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 动作按钮 */}
          <div className="text-center space-x-4">
            <button
              onClick={handleCancel}
              className="px-6 py-2 text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500"
            >
              取消分析
            </button>
            
            {!isConnected && (
              <button
                onClick={handleRetry}
                className="px-6 py-2 text-blue-600 bg-blue-100 rounded-md hover:bg-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                重新连接
              </button>
            )}
          </div>
        </div>

        {/* 提示信息 */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start">
            <div className="text-blue-500 mr-3">💡</div>
            <div className="text-blue-800 text-sm">
              <p className="font-medium mb-1">分析期间可以做什么？</p>
              <p>这个过程需要几分钟时间。您可以：</p>
              <ul className="mt-2 space-y-1 text-xs">
                <li>• 准备产品资料和市场定位</li>
                <li>• 思考目标用户群体特征</li>
                <li>• 页面会自动跳转到报告页面</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-8 text-center text-sm text-gray-500">
          <p>基于 Linus "简单胜过聪明" 设计哲学构建</p>
        </div>
      </div>
    </div>
  );
};

export default AnalysisPage;