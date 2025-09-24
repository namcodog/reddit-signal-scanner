import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import { userService } from '@/services/user.service';
import { UserHistoryItem, UserHistoryResponse } from '@/types/user.types';

const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [history, setHistory] = useState<UserHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [total, setTotal] = useState(0);

  const currentPage = parseInt(searchParams.get('page') || '1', 10);
  const limit = 20;

  const loadHistory = useCallback(async (page: number, reset = false) => {
    try {
      if (reset) {
        setLoading(true);
        setHistory([]);
      } else {
        setLoadingMore(true);
      }
      setError(null);

      const response: UserHistoryResponse = await userService.getHistory(page, limit);

      if (reset) {
        setHistory(response.items);
      } else {
        setHistory(prev => [...prev, ...response.items]);
      }

      setTotal(response.total);
      setHasMore(response.hasMore);

      // 更新URL参数
      if (page !== currentPage) {
        setSearchParams({ page: page.toString() });
      }
    } catch (err) {
      setError('加载历史记录失败');
      console.error('Failed to load history:', err);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [currentPage, setSearchParams]);

  useEffect(() => {
    loadHistory(1, true);
  }, []);

  const handleLoadMore = () => {
    const nextPage = Math.floor(history.length / limit) + 1;
    loadHistory(nextPage);
  };

  const handleDelete = async (analysisId: string) => {
    if (!confirm('确定要删除这条分析记录吗？此操作不可恢复。')) {
      return;
    }

    try {
      await userService.deleteAnalysis(analysisId);

      // 从列表中移除已删除的项目
      setHistory(prev => prev.filter(item => item.taskId !== analysisId));
      setTotal(prev => prev - 1);

      // 如果当前页没有数据了，重新加载
      if (history.length === 1 && currentPage > 1) {
        const newPage = currentPage - 1;
        setSearchParams({ page: newPage.toString() });
        loadHistory(newPage, true);
      }
    } catch (err) {
      alert('删除失败，请重试');
      console.error('Failed to delete analysis:', err);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800';
      case 'dead_letter':
        return 'bg-gray-200 text-gray-700';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed':
        return '已完成';
      case 'failed':
        return '失败';
      case 'processing':
        return '处理中';
      case 'pending':
        return '等待中';
      case 'dead_letter':
        return '死信';
      default:
        return '未知';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / (1000 * 60));

    if (diffInMinutes < 1) {
      return '刚刚';
    } else if (diffInMinutes < 60) {
      return `${diffInMinutes} 分钟前`;
    } else if (diffInMinutes < 1440) {
      return `${Math.floor(diffInMinutes / 60)} 小时前`;
    } else {
      return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-gray-600">加载中...</p>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* 页面标题 */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">分析历史</h1>
            <p className="text-gray-600 mt-2">
              共 {total} 条记录，显示 {history.length} 条
            </p>
          </div>
          <button
            onClick={() => navigate('/profile')}
            className="px-4 py-2 text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50"
          >
            返回个人中心
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-red-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span className="text-red-700">{error}</span>
            </div>
            <button
              onClick={() => loadHistory(1, true)}
              className="mt-2 text-sm text-red-600 hover:text-red-700 underline"
            >
              重新加载
            </button>
          </div>
        )}

        {history.length === 0 ? (
          <div className="text-center py-12">
            <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-xl font-medium text-gray-900 mb-2">暂无分析记录</h3>
            <p className="text-gray-600 mb-6">您还没有进行过任何分析，开始您的第一次分析吧！</p>
            <button
              onClick={() => navigate('/')}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              开始分析
            </button>
          </div>
        ) : (
          <>
            {/* 分析记录列表 */}
            <div className="space-y-4">
              {history.map((item) => (
                <div
                  key={item.taskId}
                  className="bg-white rounded-lg shadow-sm border hover:shadow-md transition-shadow"
                >
                  <div className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-3 mb-3">
                          <h3 className="text-lg font-medium text-gray-900 truncate">
                            {item.description || '未填写描述的任务'}
                          </h3>
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(item.status)}`}>
                            {item.statusLabel || getStatusText(item.status)}
                          </span>
                        </div>

                        <div className="flex items-center space-x-6 text-sm text-gray-500">
                          <div className="flex items-center space-x-1">
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                            </svg>
                            <span>创建时间: {formatDate(item.createdAt)}</span>
                          </div>

                          {item.completedAt && (
                            <div className="flex items-center space-x-1">
                              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                              <span>完成时间: {formatDate(item.completedAt)}</span>
                            </div>
                          )}

                          {item.status === 'failed' && (
                            <div className="flex items-center space-x-1 text-red-500">
                              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                              </svg>
                              <span>任务失败，请重试</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 ml-4">
                        {item.status === 'completed' && (
                          <button
                            onClick={() => navigate(`/report/${item.taskId}`)}
                            className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                          >
                            查看报告
                          </button>
                        )}

                        {item.status === 'processing' && (
                          <button
                            onClick={() => navigate(`/analysis/${item.taskId}`)}
                            className="px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
                          >
                            查看进度
                          </button>
                        )}

                        <button
                          onClick={() => handleDelete(item.taskId)}
                          className="px-3 py-1.5 text-red-600 border border-red-600 text-sm rounded hover:bg-red-50 transition-colors"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* 加载更多按钮 */}
            {hasMore && (
              <div className="text-center mt-8">
                <button
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="px-6 py-3 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loadingMore ? (
                    <div className="flex items-center space-x-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                      <span>加载中...</span>
                    </div>
                  ) : (
                    '加载更多'
                  )}
                </button>
              </div>
            )}

            {!hasMore && history.length > 0 && (
              <div className="text-center mt-8 py-4">
                <p className="text-gray-500">已显示全部记录</p>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
};

export default HistoryPage;
