import React, { useState } from 'react';
import { 
  ExclamationTriangleIcon,
  EyeIcon,
  FunnelIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ChatBubbleLeftIcon
} from '@heroicons/react/24/outline';

import { PainPointsListProps } from '@/types/contracts/report.contract';

const PainPointsList: React.FC<PainPointsListProps> = ({
  painPoints = [],
  onInsightClick
}) => {
  const [sortBy, setSortBy] = useState<'frequency' | 'sentiment' | 'severity'>('frequency');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [filterSeverity, setFilterSeverity] = useState<string>('all');

  // 排序和筛选痛点
  const processedPainPoints = React.useMemo(() => {
    let filtered = painPoints;

    // 按严重程度筛选
    if (filterSeverity !== 'all') {
      filtered = filtered.filter(point => point.severity === filterSeverity);
    }

    // 排序
    filtered.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'frequency':
          comparison = a.frequency - b.frequency;
          break;
        case 'sentiment':
          comparison = a.sentiment_score - b.sentiment_score;
          break;
        case 'severity':
          const severityOrder = { 'low': 1, 'medium': 2, 'high': 3 };
          const aSeverity = severityOrder[a.severity as keyof typeof severityOrder] || 0;
          const bSeverity = severityOrder[b.severity as keyof typeof severityOrder] || 0;
          comparison = aSeverity - bSeverity;
          break;
      }

      return sortOrder === 'desc' ? -comparison : comparison;
    });

    return filtered;
  }, [painPoints, sortBy, sortOrder, filterSeverity]);

  const getSeverityColor = (severity?: string) => {
    switch (severity) {
      case 'high': return 'text-red-600 bg-red-50 border-red-200';
      case 'medium': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'low': return 'text-green-600 bg-green-50 border-green-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getSeverityLabel = (severity?: string) => {
    switch (severity) {
      case 'high': return '高';
      case 'medium': return '中';
      case 'low': return '低';
      default: return '未知';
    }
  };

  const getSentimentColor = (score: number) => {
    if (score < -0.3) return 'text-red-600';
    if (score < 0.1) return 'text-yellow-600';
    return 'text-green-600';
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">痛点分析</h2>
          <div className="text-sm text-gray-500">
            共发现 {painPoints.length} 个痛点
          </div>
        </div>

        {/* 筛选和排序控件 */}
        <div className="flex flex-wrap items-center gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center">
            <FunnelIcon className="h-4 w-4 text-gray-500 mr-2" />
            <span className="text-sm text-gray-700 mr-2">筛选:</span>
            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1"
            >
              <option value="all">全部严重程度</option>
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </div>

          <div className="flex items-center">
            <span className="text-sm text-gray-700 mr-2">排序:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'frequency' | 'sentiment' | 'severity')}
              className="text-sm border border-gray-300 rounded px-2 py-1 mr-2"
            >
              <option value="frequency">频次</option>
              <option value="sentiment">情感分数</option>
              <option value="severity">严重程度</option>
            </select>
            <button
              onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
              className="p-1 text-gray-500 hover:text-gray-700"
            >
              {sortOrder === 'desc' ? <ArrowDownIcon className="h-4 w-4" /> : <ArrowUpIcon className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* 痛点列表 */}
        <div className="space-y-4">
          {processedPainPoints.map((painPoint, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    {painPoint.description}
                  </h3>
                  
                  <div className="flex items-center space-x-4 text-sm">
                    <div className="flex items-center">
                      <ChatBubbleLeftIcon className="h-4 w-4 text-gray-400 mr-1" />
                      <span className="text-gray-600">频次: {painPoint.frequency}</span>
                    </div>
                    
                    <div className="flex items-center">
                      <span className="text-gray-600">情感: </span>
                      <span className={`ml-1 font-medium ${getSentimentColor(painPoint.sentiment_score)}`}>
                        {(painPoint.sentiment_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    
                    {painPoint.confidence && (
                      <div className="flex items-center">
                        <span className="text-gray-600">置信度: </span>
                        <span className="ml-1 font-medium text-blue-600">
                          {Math.round(painPoint.confidence * 100)}%
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center space-x-2 ml-4">
                  {painPoint.severity && (
                    <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getSeverityColor(painPoint.severity)}`}>
                      {getSeverityLabel(painPoint.severity)}
                    </span>
                  )}
                </div>
              </div>

              {/* 分类标签 */}
              {painPoint.categories.length > 0 && (
                <div className="mb-3">
                  <div className="flex flex-wrap gap-1">
                    {painPoint.categories.map((category, catIndex) => (
                      <span key={catIndex} className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {category}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 示例帖子 */}
              {painPoint.example_posts.length > 0 && (
                <div className="mb-3">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">示例帖子:</h4>
                  <div className="space-y-2">
                    {painPoint.example_posts.slice(0, 2).map((post, postIndex) => (
                      <div key={postIndex} className="bg-gray-50 rounded p-3 text-sm">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-blue-600 font-medium">{post.community}</span>
                          {post.upvotes && (
                            <span className="text-gray-500">👍 {post.upvotes}</span>
                          )}
                        </div>
                        <p className="text-gray-700 line-clamp-2">{post.content_snippet}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 标签和操作 */}
              <div className="flex items-center justify-between">
                <div className="flex flex-wrap gap-1">
                  {painPoint.tags.map((tag: string, tagIndex: number) => (
                    <span key={tagIndex} className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      {tag}
                    </span>
                  ))}
                </div>
                
                <button
                  onClick={() => onInsightClick?.(painPoint)}
                  className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50"
                >
                  <EyeIcon className="h-4 w-4 mr-1" />
                  查看详情
                </button>
              </div>
            </div>
          ))}
        </div>

        {processedPainPoints.length === 0 && (
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="p-8 text-center text-gray-500">
              <ExclamationTriangleIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>暂无痛点数据或不符合筛选条件</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PainPointsList;
