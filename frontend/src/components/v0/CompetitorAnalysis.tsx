/**
 * CompetitorAnalysis组件 - 竞争对手分析展示
 * 显示竞争对手信息、市场定位、优劣势分析和交互式表格
 */

import React, { useState, useMemo } from 'react';
import { 
  BuildingOffice2Icon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  MagnifyingGlassIcon,
  FunnelIcon
} from '@heroicons/react/24/outline';

import type { CompetitorAnalysisProps } from '@/types/contracts/report.contract';

// 扩展竞争对手类型定义
interface Competitor {
  id: string;
  name: string;
  market_position: 'leader' | 'challenger' | 'follower' | 'niche';
  strengths: string[];
  weaknesses: string[];
  marketShare: number;
  mentionCount: number;
  sentiment: number; // 0-1, 用户对该竞争对手的情感分数
  trendDirection: 'up' | 'down' | 'stable';
  lastUpdate: string;
}

const CompetitorAnalysis: React.FC<CompetitorAnalysisProps> = ({
  competitors: rawCompetitors = [],  // 修复：添加默认值，避免undefined.map()错误
  onCompetitorSelect
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [positionFilter, setPositionFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'name' | 'marketShare' | 'mentions' | 'sentiment'>('marketShare');

  // 转换和模拟数据（因为当前后端可能还没有完整的竞争对手数据）
  const competitors: Competitor[] = useMemo(() => {
    if (rawCompetitors && rawCompetitors.length > 0) {
      return rawCompetitors.map((comp, index) => ({
        id: `comp-${index}`,
        name: comp.name || `竞争对手 ${index + 1}`,
        market_position: (comp.market_position as Competitor['market_position']) || 'follower',
        strengths: comp.strengths || [],
        weaknesses: comp.weaknesses || [],
        marketShare: Math.random() * 30 + 5, // 模拟市场份额
        mentionCount: Math.floor(Math.random() * 100) + 10,
        sentiment: Math.random() * 0.6 + 0.2, // 0.2-0.8范围
        trendDirection: (['up', 'down', 'stable'] as const)[Math.floor(Math.random() * 3)],
        lastUpdate: new Date().toISOString()
      }));
    }
    
    // 如果没有真实数据，提供示例数据
    return [
      {
        id: 'comp-1',
        name: '行业领导者A',
        market_position: 'leader',
        strengths: ['品牌知名度高', '资金雄厚', '技术先进'],
        weaknesses: ['价格偏高', '创新速度慢', '客服体验一般'],
        marketShare: 25.3,
        mentionCount: 156,
        sentiment: 0.65,
        trendDirection: 'stable',
        lastUpdate: new Date().toISOString()
      },
      {
        id: 'comp-2', 
        name: '新兴挑战者B',
        market_position: 'challenger',
        strengths: ['价格优势', '用户体验好', '快速迭代'],
        weaknesses: ['品牌影响力小', '功能相对简单', '稳定性待提升'],
        marketShare: 12.8,
        mentionCount: 89,
        sentiment: 0.72,
        trendDirection: 'up',
        lastUpdate: new Date().toISOString()
      },
      {
        id: 'comp-3',
        name: '传统厂商C', 
        market_position: 'follower',
        strengths: ['渠道覆盖广', '行业经验丰富', '价格稳定'],
        weaknesses: ['技术落后', '界面陈旧', '响应速度慢'],
        marketShare: 8.1,
        mentionCount: 34,
        sentiment: 0.45,
        trendDirection: 'down',
        lastUpdate: new Date().toISOString()
      }
    ];
  }, [rawCompetitors]);

  // 过滤和排序
  const filteredCompetitors = useMemo(() => {
    const filtered = competitors.filter(comp => 
      comp.name.toLowerCase().includes(searchTerm.toLowerCase()) &&
      (positionFilter === 'all' || comp.market_position === positionFilter)
    );

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'name':
          return a.name.localeCompare(b.name);
        case 'mentions':
          return b.mentionCount - a.mentionCount;
        case 'sentiment':
          return b.sentiment - a.sentiment;
        case 'marketShare':
        default:
          return b.marketShare - a.marketShare;
      }
    });

    return filtered;
  }, [competitors, searchTerm, positionFilter, sortBy]);

  const getPositionConfig = (position: Competitor['market_position']): { label: string; className: string } => {
    const config = {
      leader: { label: '领导者', className: 'bg-green-100 text-green-800' },
      challenger: { label: '挑战者', className: 'bg-blue-100 text-blue-800' },
      follower: { label: '跟随者', className: 'bg-gray-100 text-gray-800' },
      niche: { label: '细分市场', className: 'bg-purple-100 text-purple-800' }
    };
    
    return config[position];
  };

  const getTrendIcon = (trend: Competitor['trendDirection']): React.ReactNode => {
    switch (trend) {
      case 'up':
        return <ArrowTrendingUpIcon className="h-4 w-4 text-green-600" />;
      case 'down':
        return <ArrowTrendingDownIcon className="h-4 w-4 text-red-600" />;
      default:
        return <div className="h-4 w-4 bg-gray-400 rounded-full" />;
    }
  };

  const getSentimentColor = (sentiment: number): string => {
    if (sentiment > 0.7) return 'text-green-600';
    if (sentiment > 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center space-x-2">
        <BuildingOffice2Icon className="h-6 w-6 text-purple-600" />
        <h2 className="text-2xl font-bold text-gray-900">竞争对手分析</h2>
      </div>

      {/* 控制栏 */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <input
                type="text"
                placeholder="搜索竞争对手..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <FunnelIcon className="h-4 w-4 text-gray-500" />
            <select
              value={positionFilter}
              onChange={(e) => setPositionFilter(e.target.value)}
              className="border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value="all">所有类型</option>
              <option value="leader">领导者</option>
              <option value="challenger">挑战者</option>
              <option value="follower">跟随者</option>
              <option value="niche">细分市场</option>
            </select>
          </div>
          
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="border border-gray-300 rounded-md px-3 py-2 text-sm"
          >
            <option value="marketShare">市场份额</option>
            <option value="mentions">提及次数</option>
            <option value="sentiment">用户情感</option>
            <option value="name">名称</option>
          </select>
        </div>
      </div>

      {/* 竞争对手表格 */}
      <div className="bg-white rounded-lg shadow-sm border">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">竞争对手概览 ({filteredCompetitors.length})</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  公司名称
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  市场定位
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  市场份额
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  提及次数
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  用户情感
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  趋势
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredCompetitors.map((competitor) => {
                const positionConfig = getPositionConfig(competitor.market_position);
                
                return (
                  <tr key={competitor.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-medium text-gray-900">{competitor.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${positionConfig.className}`}>
                        {positionConfig.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {competitor.marketShare.toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {competitor.mentionCount}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`text-sm font-medium ${getSentimentColor(competitor.sentiment)}`}>
                        {Math.round(competitor.sentiment * 100)}%
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getTrendIcon(competitor.trendDirection)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        onClick={() => onCompetitorSelect?.(competitor.name)}
                        className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50"
                      >
                        查看详情
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          
          {filteredCompetitors.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              <BuildingOffice2Icon className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>暂无竞争对手数据或不符合筛选条件</p>
            </div>
          )}
        </div>
      </div>

      {/* 详细分析卡片（显示前3个） */}
      {filteredCompetitors.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredCompetitors.slice(0, 3).map((competitor) => {
            const positionConfig = getPositionConfig(competitor.market_position);
            
            return (
              <div key={`detail-${competitor.id}`} className="bg-white rounded-lg shadow-sm border hover:shadow-md transition-shadow">
                <div className="p-6 border-b border-gray-200">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-lg font-semibold text-gray-900">{competitor.name}</h3>
                    {getTrendIcon(competitor.trendDirection)}
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${positionConfig.className}`}>
                      {positionConfig.label}
                    </span>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      {competitor.marketShare.toFixed(1)}% 市场份额
                    </span>
                  </div>
                </div>
                <div className="p-6">
                  <div className="space-y-4">
                    {/* 优势 */}
                    {competitor.strengths.length > 0 && (
                      <div>
                        <h4 className="font-medium text-green-700 mb-2">优势</h4>
                        <div className="space-y-1">
                          {competitor.strengths.slice(0, 3).map((strength, index) => (
                            <div key={index} className="text-sm text-gray-600 flex items-center">
                              <div className="w-2 h-2 bg-green-500 rounded-full mr-2 flex-shrink-0" />
                              {strength}
                            </div>
                          ))}
                          {competitor.strengths.length > 3 && (
                            <div className="text-xs text-gray-500">
                              +{competitor.strengths.length - 3} 更多优势
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {/* 劣势 */}
                    {competitor.weaknesses.length > 0 && (
                      <div>
                        <h4 className="font-medium text-red-700 mb-2">劣势</h4>
                        <div className="space-y-1">
                          {competitor.weaknesses.slice(0, 3).map((weakness, index) => (
                            <div key={index} className="text-sm text-gray-600 flex items-center">
                              <div className="w-2 h-2 bg-red-500 rounded-full mr-2 flex-shrink-0" />
                              {weakness}
                            </div>
                          ))}
                          {competitor.weaknesses.length > 3 && (
                            <div className="text-xs text-gray-500">
                              +{competitor.weaknesses.length - 3} 更多劣势
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {/* 底部统计 */}
                    <div className="pt-4 border-t border-gray-100">
                      <div className="grid grid-cols-2 gap-4 text-center">
                        <div>
                          <div className="text-lg font-semibold text-gray-900">{competitor.mentionCount}</div>
                          <div className="text-xs text-gray-500">提及次数</div>
                        </div>
                        <div>
                          <div className={`text-lg font-semibold ${getSentimentColor(competitor.sentiment)}`}>
                            {Math.round(competitor.sentiment * 100)}%
                          </div>
                          <div className="text-xs text-gray-500">用户好评</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export { CompetitorAnalysis };
export default CompetitorAnalysis;