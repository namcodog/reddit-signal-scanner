import React, { useState } from 'react';
import { 
  MagnifyingGlassIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  BuildingOfficeIcon,
  ChartBarIcon,
  FunnelIcon
} from '@heroicons/react/24/outline';

import { CompetitorAnalysisProps } from '@/types/contracts/report.contract';

const CompetitorAnalysis: React.FC<CompetitorAnalysisProps> = ({
  competitors = [],
  onCompetitorSelect
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'mention_count' | 'sentiment_score' | 'market_share'>('mention_count');
  const [filterPosition, setFilterPosition] = useState<string>('all');

  // 筛选和排序竞品
  const processedCompetitors = React.useMemo(() => {
    let filtered = competitors;

    // 搜索筛选
    if (searchTerm) {
      filtered = filtered.filter(competitor => 
        competitor.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        competitor.description?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // 市场地位筛选
    if (filterPosition !== 'all') {
      filtered = filtered.filter(competitor => competitor.market_position === filterPosition);
    }

    // 排序
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'mention_count':
          return b.mention_count - a.mention_count;
        case 'sentiment_score':
          return b.sentiment_score - a.sentiment_score;
        case 'market_share':
          return (b.market_share_estimate || 0) - (a.market_share_estimate || 0);
        default:
          return 0;
      }
    });

    return filtered;
  }, [competitors, searchTerm, sortBy, filterPosition]);

  const getPositionColor = (position?: string) => {
    switch (position) {
      case 'leader': return 'text-green-600 bg-green-50 border-green-200';
      case 'challenger': return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'follower': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'niche': return 'text-purple-600 bg-purple-50 border-purple-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getPositionLabel = (position?: string) => {
    switch (position) {
      case 'leader': return '领导者';
      case 'challenger': return '挑战者';
      case 'follower': return '跟随者';
      case 'niche': return '细分市场';
      default: return '未知';
    }
  };

  const getSentimentColor = (score: number) => {
    if (score > 0.3) return 'text-green-600';
    if (score > -0.1) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">竞品分析</h2>
          <div className="text-sm text-gray-500">
            共发现 {competitors.length} 个竞品
          </div>
        </div>

        {/* 搜索和筛选控件 */}
        <div className="flex flex-wrap items-center gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex-1 min-w-64">
            <div className="relative">
              <MagnifyingGlassIcon className="h-4 w-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="搜索竞品名称或描述..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          <div className="flex items-center">
            <FunnelIcon className="h-4 w-4 text-gray-500 mr-2" />
            <span className="text-sm text-gray-700 mr-2">市场地位:</span>
            <select
              value={filterPosition}
              onChange={(e) => setFilterPosition(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1"
            >
              <option value="all">全部</option>
              <option value="leader">领导者</option>
              <option value="challenger">挑战者</option>
              <option value="follower">跟随者</option>
              <option value="niche">细分市场</option>
            </select>
          </div>

          <div className="flex items-center">
            <span className="text-sm text-gray-700 mr-2">排序:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'mention_count' | 'sentiment_score' | 'market_share')}
              className="text-sm border border-gray-300 rounded px-2 py-1"
            >
              <option value="mention_count">提及次数</option>
              <option value="sentiment_score">情感分数</option>
              <option value="market_share">市场份额</option>
            </select>
          </div>
        </div>

        {/* 竞品列表 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {processedCompetitors.map((competitor, index) => (
            <div 
              key={index} 
              className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => onCompetitorSelect?.(competitor)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center mb-2">
                    <BuildingOfficeIcon className="h-5 w-5 text-gray-400 mr-2" />
                    <h3 className="text-lg font-semibold text-gray-900">{competitor.name}</h3>
                  </div>
                  
                  {competitor.description && (
                    <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                      {competitor.description}
                    </p>
                  )}
                </div>

                {competitor.market_position && (
                  <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getPositionColor(competitor.market_position)}`}>
                    {getPositionLabel(competitor.market_position)}
                  </span>
                )}
              </div>

              {/* 关键指标 */}
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div className="text-center">
                  <div className="text-lg font-bold text-blue-600">{competitor.mention_count}</div>
                  <div className="text-xs text-gray-500">提及次数</div>
                </div>
                <div className="text-center">
                  <div className={`text-lg font-bold ${getSentimentColor(competitor.sentiment_score)}`}>
                    {(competitor.sentiment_score * 100).toFixed(1)}%
                  </div>
                  <div className="text-xs text-gray-500">情感分数</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold text-purple-600">
                    {competitor.market_share_estimate ? `${(competitor.market_share_estimate * 100).toFixed(1)}%` : 'N/A'}
                  </div>
                  <div className="text-xs text-gray-500">市场份额</div>
                </div>
              </div>

              {/* 优势和劣势 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <h4 className="font-medium text-green-600 mb-2">优势</h4>
                  <ul className="space-y-1">
                    {competitor.strengths.slice(0, 3).map((strength: string, idx: number) => (
                      <li key={idx} className="text-sm text-gray-600 flex items-center">
                        <ArrowTrendingUpIcon className="h-3 w-3 text-green-500 mr-2 flex-shrink-0" />
                        {strength}
                      </li>
                    ))}
                    {competitor.strengths.length === 0 && (
                      <li className="text-sm text-gray-400">暂无优势信息</li>
                    )}
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium text-red-600 mb-2">劣势</h4>
                  <ul className="space-y-1">
                    {competitor.weaknesses.slice(0, 3).map((weakness: string, idx: number) => (
                      <li key={idx} className="text-sm text-gray-600 flex items-center">
                        <ArrowTrendingDownIcon className="h-3 w-3 text-red-500 mr-2 flex-shrink-0" />
                        {weakness}
                      </li>
                    ))}
                    {competitor.weaknesses.length === 0 && (
                      <li className="text-sm text-gray-400">暂无劣势信息</li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
          ))}
        </div>

        {processedCompetitors.length === 0 && (
          <div className="text-center py-8">
            <ChartBarIcon className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <p className="text-gray-500">暂无竞品数据或不符合筛选条件</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default CompetitorAnalysis;
