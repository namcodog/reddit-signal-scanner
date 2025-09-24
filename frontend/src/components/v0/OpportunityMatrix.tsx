import React, { useState } from 'react';
import { 
  LightBulbIcon,
  ClockIcon,
  CurrencyDollarIcon,
  FunnelIcon,
  ArrowsUpDownIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';

import { OpportunityMatrixProps } from '@/types/contracts/report.contract';

const OpportunityMatrix: React.FC<OpportunityMatrixProps> = ({
  opportunities = [],
  onOpportunityClick
}) => {
  const [filterPotential, setFilterPotential] = useState<string>('all');
  const [filterDifficulty, setFilterDifficulty] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'potential' | 'difficulty' | 'confidence'>('potential');

  // 筛选和排序机会
  const processedOpportunities = React.useMemo(() => {
    let filtered = opportunities;

    // 按潜力筛选
    if (filterPotential !== 'all') {
      filtered = filtered.filter(opp => opp.potential === filterPotential);
    }

    // 按难度筛选
    if (filterDifficulty !== 'all') {
      filtered = filtered.filter(opp => opp.difficulty === filterDifficulty);
    }

    // 排序
    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'potential':
          const potentialOrder: Record<string, number> = { 'low': 1, 'medium': 2, 'high': 3 };
          return potentialOrder[b.potential] - potentialOrder[a.potential];
        case 'difficulty':
          const difficultyOrder: Record<string, number> = { 'easy': 1, 'medium': 2, 'hard': 3 };
          return difficultyOrder[a.difficulty] - difficultyOrder[b.difficulty]; // 简单的优先
        case 'confidence':
          return (b.confidence || 0) - (a.confidence || 0);
        default:
          return 0;
      }
    });

    return filtered;
  }, [opportunities, filterPotential, filterDifficulty, sortBy]);

  const getPotentialColor = (potential: string) => {
    switch (potential) {
      case 'high': return 'text-green-600 bg-green-50 border-green-200';
      case 'medium': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'low': return 'text-gray-600 bg-gray-50 border-gray-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'easy': return 'text-green-600 bg-green-50 border-green-200';
      case 'medium': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'hard': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getPotentialLabel = (potential: string) => {
    switch (potential) {
      case 'high': return '高';
      case 'medium': return '中';
      case 'low': return '低';
      default: return '未知';
    }
  };

  const getDifficultyLabel = (difficulty: string) => {
    switch (difficulty) {
      case 'easy': return '容易';
      case 'medium': return '中等';
      case 'hard': return '困难';
      default: return '未知';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">商业机会矩阵</h2>
          <div className="text-sm text-gray-500">
            共发现 {opportunities.length} 个机会
          </div>
        </div>

        {/* 筛选和排序控件 */}
        <div className="flex flex-wrap items-center gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center">
            <FunnelIcon className="h-4 w-4 text-gray-500 mr-2" />
            <span className="text-sm text-gray-700 mr-2">潜力:</span>
            <select
              value={filterPotential}
              onChange={(e) => setFilterPotential(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1"
            >
              <option value="all">全部</option>
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </div>

          <div className="flex items-center">
            <span className="text-sm text-gray-700 mr-2">难度:</span>
            <select
              value={filterDifficulty}
              onChange={(e) => setFilterDifficulty(e.target.value)}
              className="text-sm border border-gray-300 rounded px-2 py-1"
            >
              <option value="all">全部</option>
              <option value="easy">容易</option>
              <option value="medium">中等</option>
              <option value="hard">困难</option>
            </select>
          </div>

          <div className="flex items-center">
            <ArrowsUpDownIcon className="h-4 w-4 text-gray-500 mr-2" />
            <span className="text-sm text-gray-700 mr-2">排序:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'potential' | 'difficulty' | 'confidence')}
              className="text-sm border border-gray-300 rounded px-2 py-1"
            >
              <option value="potential">潜力</option>
              <option value="difficulty">难度</option>
              <option value="confidence">置信度</option>
            </select>
          </div>
        </div>

        {/* 机会列表 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {processedOpportunities.map((opportunity, index) => (
            <div 
              key={index} 
              className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => onOpportunityClick?.(opportunity)}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <div className="flex items-center mb-2">
                    <LightBulbIcon className="h-5 w-5 text-yellow-500 mr-2" />
                    <h3 className="text-lg font-semibold text-gray-900">{opportunity.title}</h3>
                  </div>
                  
                  <p className="text-sm text-gray-600 mb-3 line-clamp-3">
                    {opportunity.description}
                  </p>
                </div>
              </div>

              {/* 评级标签 */}
              <div className="flex items-center space-x-2 mb-4">
                <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getPotentialColor(opportunity.potential)}`}>
                  潜力: {getPotentialLabel(opportunity.potential)}
                </span>
                <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getDifficultyColor(opportunity.difficulty)}`}>
                  难度: {getDifficultyLabel(opportunity.difficulty)}
                </span>
              </div>

              {/* 关键指标 */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                {opportunity.market_size && (
                  <div className="flex items-center">
                    <CurrencyDollarIcon className="h-4 w-4 text-green-500 mr-2" />
                    <div>
                      <div className="text-xs text-gray-500">市场规模</div>
                      <div className="text-sm font-medium text-gray-900">{opportunity.market_size}</div>
                    </div>
                  </div>
                )}

                {opportunity.timeframe && (
                  <div className="flex items-center">
                    <ClockIcon className="h-4 w-4 text-blue-500 mr-2" />
                    <div>
                      <div className="text-xs text-gray-500">时间框架</div>
                      <div className="text-sm font-medium text-gray-900">{opportunity.timeframe}</div>
                    </div>
                  </div>
                )}

                {opportunity.confidence && (
                  <div className="flex items-center col-span-2">
                    <CheckCircleIcon className="h-4 w-4 text-purple-500 mr-2" />
                    <div>
                      <div className="text-xs text-gray-500">置信度</div>
                      <div className="text-sm font-medium text-purple-600">
                        {Math.round(opportunity.confidence * 100)}%
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* 关键洞察 */}
              {opportunity.key_insights.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">关键洞察</h4>
                  <ul className="space-y-1">
                    {opportunity.key_insights.slice(0, 3).map((insight: string, idx: number) => (
                      <li key={idx} className="text-sm text-gray-600 flex items-center">
                        <LightBulbIcon className="h-3 w-3 text-purple-500 mr-2 flex-shrink-0" />
                        {insight}
                      </li>
                    ))}
                  </ul>
                  {opportunity.key_insights.length > 3 && (
                    <p className="text-xs text-gray-500 mt-2">
                      还有 {opportunity.key_insights.length - 3} 个洞察...
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        {processedOpportunities.length === 0 && (
          <div className="text-center py-8">
            <LightBulbIcon className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <p className="text-gray-500">暂无商业机会数据或不符合筛选条件</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default OpportunityMatrix;
