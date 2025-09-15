/**
 * 等待页面 - 基于v0界面设计的SSE实时进度显示
 * 复用现有SSE架构，实现v0风格的精美UI界面
 * 
 * 设计理念：
 * - 数据结构驱动UI：扩展的TaskStatus完美映射到UI状态
 * - 消除特殊情况：统一的四步骤状态管理
 * - 实用主义：SSE优先+轮询降级的成熟架构
 */

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  CpuChipIcon, 
  ClockIcon, 
  CheckCircleIcon, 
  ArrowPathIcon, 
  UsersIcon, 
  ChatBubbleLeftRightIcon, 
  ArrowTrendingUpIcon, 
  XMarkIcon
} from '@heroicons/react/24/outline';

import { useTaskProgress } from '@/hooks/useTaskProgress';
import { 
  AnalysisStep, 
  ANALYSIS_STEPS, 
  getStepIndex, 
  calculateOverallProgress,
  formatRemainingTime
} from '@/services/sse.service';

/**
 * 等待页面组件 - v0风格实现
 * 完全类型安全：零Any、零type:ignore
 */
const WaitingPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  
  // 使用现有的SSE Hook（架构不变）
  const {
    status,
    error,
    isConnected,
    strategy,
    retry,
    disconnect,
    connectionAttempts: _connectionAttempts,
  } = useTaskProgress(taskId);

  // 页面状态管理（v0风格）
  const [timeElapsed, setTimeElapsed] = useState<number>(0);
  const [productDescription, setProductDescription] = useState<string>('');
  
  // 任务ID验证
  if (!taskId) {
    navigate('/');
    return null;
  }

  // 获取产品描述（从localStorage或API）
  useEffect(() => {
    const savedDescription = localStorage.getItem(`task_${taskId}_description`);
    if (savedDescription) {
      setProductDescription(savedDescription);
    }
  }, [taskId]);

  // 时间计数器
  useEffect(() => {
    const timer = setInterval(() => {
      setTimeElapsed(prev => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // 自动跳转到报告页面
  useEffect(() => {
    if (status?.status === 'completed') {
      const timer = setTimeout(() => {
        navigate(`/report/${taskId}`);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [status?.status, taskId, navigate]);

  // 处理取消分析
  const handleCancel = (): void => {
    disconnect();
    navigate('/');
  };

  // 处理重试连接
  const handleRetry = (): void => {
    retry();
  };

  // 获取当前进度数据
  const getProgressData = () => {
    if (!status) {
      return {
        currentStep: ANALYSIS_STEPS[0],
        currentStepIndex: 0,
        overallProgress: 0,
        stepProgress: 0,
        estimatedRemaining: 0,
        isComplete: false
      };
    }

    const currentStep = status.current_step || AnalysisStep.DATA_COLLECTION;
    // Context7最佳实践：使用clamp边界限制确保索引在有效范围内
    const currentStepIndex = Math.max(0, Math.min(
      getStepIndex(currentStep), 
      ANALYSIS_STEPS.length - 1
    ));
    const stepProgress = status.step_progress || 0;
    const overallProgress = status.progress || calculateOverallProgress(currentStep, stepProgress);
    const estimatedRemaining = status.estimated_remaining_seconds || 0;
    const isComplete = status.status === 'completed';

    return {
      currentStep: ANALYSIS_STEPS[currentStepIndex] || ANALYSIS_STEPS[0],
      currentStepIndex,
      overallProgress,
      stepProgress,
      estimatedRemaining,
      isComplete
    };
  };

  const progressData = getProgressData();

  // 获取步骤图标
  const getStepIcon = (_step: typeof ANALYSIS_STEPS[0], index: number): JSX.Element => {
    const isCompleted = index < progressData.currentStepIndex;
    const isCurrent = index === progressData.currentStepIndex;
    
    if (isCompleted) {
      return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
    } else if (isCurrent) {
      return <ArrowPathIcon className="w-5 h-5 text-blue-600 animate-spin" />;
    } else {
      return <div className="w-5 h-5 rounded-full border-2 border-gray-300" />;
    }
  };

  // 获取实时统计数据（带动画效果）
  const getLiveStats = () => {
    const stats = status?.stats;
    if (stats) {
      return {
        communities: stats.communities_found || 0,
        posts: stats.posts_analyzed || 0,
        insights: stats.insights_generated || 0
      };
    }

    // Mock动画数据（类似v0）
    return {
      communities: Math.min(Math.floor(timeElapsed / 10) * 3 + 12, 47),
      posts: Math.min(Math.floor(timeElapsed / 5) * 127 + 234, 2847),
      insights: Math.min(Math.floor(timeElapsed / 15) * 8 + 3, 23)
    };
  };

  const liveStats = getLiveStats();

  // 格式化时间显示
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div data-testid="waiting-page" className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 py-12 px-4">
      <div className="max-w-4xl mx-auto space-y-8">
        
        {/* Header - v0风格 */}
        <div className="text-center space-y-4">
          <div className="flex items-center justify-center space-x-2 mb-4">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
              <CpuChipIcon className="w-6 h-6 text-blue-600 animate-pulse" />
            </div>
          </div>
          <h2 className="text-3xl font-bold text-gray-900">
            {progressData.isComplete ? "分析完成！" : "正在分析您的产品"}
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            {progressData.isComplete 
              ? "我们已经发现了关于您的市场机会的宝贵洞察" 
              : "我们正在扫描 Reddit 社区，为您的产品寻找商业机会"}
          </p>
          <p data-testid="task-id" className="text-sm text-gray-500 mt-2">
            任务ID: {taskId}
          </p>
        </div>

        {/* 产品描述卡片 */}
        {productDescription && (
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">正在分析的产品</h3>
            <p className="text-gray-600 line-clamp-3">{productDescription}</p>
          </div>
        )}

        {/* 连接状态指示 */}
        <div className="flex items-center justify-center space-x-4 text-sm">
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className={isConnected ? 'text-green-600' : 'text-red-600'}>
              {isConnected
                ? `实时连接 (${strategy === 'sse' ? 'SSE' : '轮询'})`
                : '连接断开'}
            </span>
          </div>
          {error && (
            <div className="flex items-center space-x-2 text-red-600">
              <XMarkIcon className="w-4 h-4" />
              <span>连接错误</span>
              <button 
                onClick={handleRetry}
                className="text-blue-600 underline hover:no-underline"
              >
                重试
              </button>
            </div>
          )}
        </div>

        {/* 进度概览卡片 - v0精华设计 */}
        <div data-testid="progress-tracker" className="bg-white rounded-2xl shadow-lg border border-gray-200">
          <div className="p-6">
            {/* 进度头部 */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-semibold text-gray-900 flex items-center space-x-2">
                  <ClockIcon className="w-5 h-5 text-blue-600" />
                  <span>分析进度</span>
                </h3>
                <p className="text-gray-600 mt-1">
                  {progressData.isComplete
                    ? "分析已成功完成"
                    : `第 ${progressData.currentStepIndex + 1} 步，共 ${ANALYSIS_STEPS.length} 步 • 剩余 ${formatRemainingTime(progressData.estimatedRemaining)}`
                  }
                </p>
              </div>
              <div data-testid="progress-percentage" className={`px-3 py-1 rounded-full text-sm font-medium ${
                progressData.isComplete 
                  ? 'bg-green-100 text-green-700' 
                  : 'bg-blue-100 text-blue-700'
              }`}>
                {Math.round(progressData.overallProgress)}%
              </div>
            </div>

            {/* 整体进度条 */}
            <div className="mb-6">
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div 
                  className="bg-gradient-to-r from-blue-500 to-blue-600 h-3 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${Math.max(progressData.overallProgress, 5)}%` }}
                />
              </div>
            </div>

            {/* 步骤详情 */}
            <div className="space-y-4">
              {ANALYSIS_STEPS.map((step, index) => {
                const isCompleted = index < progressData.currentStepIndex;
                const isCurrent = index === progressData.currentStepIndex;

                return (
                  <div
                    key={step.step}
                    className={`flex items-center space-x-4 p-4 rounded-lg border transition-all ${
                      isCurrent
                        ? "border-blue-200 bg-blue-50"
                        : isCompleted
                          ? "border-green-200 bg-green-50"
                          : "border-gray-200 bg-white"
                    }`}
                  >
                    <div className="flex-shrink-0">{getStepIcon(ANALYSIS_STEPS[0], index)}</div>
                    <div className="flex-1 min-w-0">
                      <h4 data-testid={isCurrent ? "current-step-name" : undefined} className="font-medium text-gray-900">{step.title}</h4>
                      <p className="text-sm text-gray-600">{step.description}</p>
                    </div>
                    <div className="flex-shrink-0">
                      {isCurrent && (
                        <div data-testid="current-step" className="px-3 py-1 bg-blue-100 text-blue-700 text-sm rounded-full animate-pulse">
                          处理中...
                        </div>
                      )}
                      {isCompleted && (
                        <div className="px-3 py-1 bg-green-100 text-green-700 text-sm rounded-full">
                          完成
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* 实时统计 - v0精华功能 */}
        {isConnected && !progressData.isComplete && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-lg shadow-md border border-gray-200 p-4 text-center">
              <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-2">
                <UsersIcon className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-2xl font-bold text-gray-900">{liveStats.communities}</div>
              <p className="text-sm text-gray-600">发现的社区</p>
            </div>

            <div className="bg-white rounded-lg shadow-md border border-gray-200 p-4 text-center">
              <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-2">
                <ChatBubbleLeftRightIcon className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-2xl font-bold text-gray-900">{liveStats.posts}</div>
              <p className="text-sm text-gray-600">已分析帖子</p>
            </div>

            <div className="bg-white rounded-lg shadow-md border border-gray-200 p-4 text-center">
              <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-2">
                <ArrowTrendingUpIcon className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-2xl font-bold text-gray-900">{liveStats.insights}</div>
              <p className="text-sm text-gray-600">生成的洞察</p>
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex items-center justify-center space-x-4">
          {!progressData.isComplete ? (
            <>
              <button 
                onClick={handleCancel}
                className="px-6 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                取消分析
              </button>
              {!isConnected && (
                <button 
                  onClick={handleRetry}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  重新连接
                </button>
              )}
            </>
          ) : (
            <button 
              onClick={() => navigate(`/report/${taskId}`)}
              className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium text-lg"
            >
              查看报告
            </button>
          )}
        </div>

        {/* 时间显示 */}
        <div className="text-center text-sm text-gray-500">
          已用时间：{formatTime(timeElapsed)}
          {!progressData.isComplete && progressData.estimatedRemaining > 0 && 
            ` • 预计完成时间：${formatRemainingTime(progressData.estimatedRemaining)}`
          }
        </div>

        {/* 提示信息 */}
        {!progressData.isComplete && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
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
        )}

        {/* Footer */}
        <div className="text-center text-sm text-gray-500">
          <p>基于 v0 设计语言 & Linus "简单胜过聪明" 哲学构建</p>
        </div>
      </div>
    </div>
  );
};

export default WaitingPage;