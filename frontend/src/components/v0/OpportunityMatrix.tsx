/**
 * OpportunityMatrix组件 - 机会矩阵可视化
 * 显示影响力vs难度的二维矩阵图，包含机会卡片和散点图可视化
 */

import React, { useState, useMemo } from 'react';
import { 
  SparklesIcon,
  LightBulbIcon,
  FunnelIcon,
  AdjustmentsHorizontalIcon
} from '@heroicons/react/24/outline';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import type { TooltipItem } from 'chart.js';
import { Scatter } from 'react-chartjs-2';

import type { OpportunityMatrixProps } from '@/types/contracts/report.contract';

// 注册Chart.js组件
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

// 扩展机会类型定义
interface ExtendedOpportunity {
  id: string;
  title: string;
  description: string;
  impact: 'low' | 'medium' | 'high';
  difficulty: 'low' | 'medium' | 'high';
  // 数值化的impact和difficulty (1-3)
  impactScore: number;
  difficultyScore: number;
  // 优先级计算
  priority: number;
  category: string;
  potentialValue?: string;
}

const OpportunityMatrix: React.FC<OpportunityMatrixProps> = ({
  opportunities: rawOpportunities = [],  // 修复：添加默认值，避免undefined.map()错误
  onOpportunityClick
}) => {
  const [filterByImpact, setFilterByImpact] = useState<'all' | 'low' | 'medium' | 'high'>('all');
  const [filterByDifficulty, setFilterByDifficulty] = useState<'all' | 'low' | 'medium' | 'high'>('all');
  const [sortBy, setSortBy] = useState<'priority' | 'impact' | 'difficulty'>('priority');

  // 转换和模拟数据
  const opportunities: ExtendedOpportunity[] = useMemo(() => {
    if (rawOpportunities && rawOpportunities.length > 0) {
      return rawOpportunities.map((opp, index) => {
        const impactScore = opp.impact === 'low' ? 1 : opp.impact === 'medium' ? 2 : 3;
        const difficultyScore = opp.difficulty === 'low' ? 1 : opp.difficulty === 'medium' ? 2 : 3;
        
        return {
          id: `opp-${index}`,
          title: opp.title,
          description: opp.description,
          impact: opp.impact,
          difficulty: opp.difficulty,
          impactScore,
          difficultyScore,
          priority: impactScore / difficultyScore, // 简单的优先级计算
          category: 'market',
          potentialValue: `$${(Math.random() * 500 + 100).toFixed(0)}K`
        };
      });
    }
    
    // 如果没有真实数据，提供示例数据
    return [
      {
        id: 'opp-1',
        title: '移动端体验优化',
        description: '改进移动端用户界面和交互流程，提升用户留存率',
        impact: 'high',
        difficulty: 'medium',
        impactScore: 3,
        difficultyScore: 2,
        priority: 1.5,
        category: 'product',
        potentialValue: '$350K'
      },
      {
        id: 'opp-2',
        title: '人工智能推荐系统',
        description: '基于用户行为数据建立个性化推荐引擎',
        impact: 'high',
        difficulty: 'high',
        impactScore: 3,
        difficultyScore: 3,
        priority: 1.0,
        category: 'technology',
        potentialValue: '$600K'
      },
      {
        id: 'opp-3',
        title: '社交媒体整合',
        description: '与主流社交平台建立API集成，扩大用户触达',
        impact: 'medium',
        difficulty: 'low',
        impactScore: 2,
        difficultyScore: 1,
        priority: 2.0,
        category: 'marketing',
        potentialValue: '$180K'
      },
      {
        id: 'opp-4',
        title: '数据分析仪表板',
        description: '为企业用户提供深度业务洞察和趋势分析',
        impact: 'medium',
        difficulty: 'medium',
        impactScore: 2,
        difficultyScore: 2,
        priority: 1.0,
        category: 'analytics',
        potentialValue: '$420K'
      }
    ];
  }, [rawOpportunities]);

  // 过滤和排序
  const filteredOpportunities = useMemo(() => {
    const filtered = opportunities.filter(opp =>
      (filterByImpact === 'all' || opp.impact === filterByImpact) &&
      (filterByDifficulty === 'all' || opp.difficulty === filterByDifficulty)
    );

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'impact':
          return b.impactScore - a.impactScore;
        case 'difficulty':
          return a.difficultyScore - b.difficultyScore; // 难度低的优先
        case 'priority':
        default:
          return b.priority - a.priority;
      }
    });

    return filtered;
  }, [opportunities, filterByImpact, filterByDifficulty, sortBy]);

  // Chart.js散点图数据
  const chartData = useMemo(() => {
    const data = filteredOpportunities.map(opp => ({
      x: opp.difficultyScore,
      y: opp.impactScore,
      label: opp.title,
      category: opp.category
    }));

    // 按类别分组
    const categories = ['product', 'technology', 'marketing', 'analytics', 'market'];
    const colors = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6'];
    
    const datasets = categories.map((category, index) => ({
      label: category.charAt(0).toUpperCase() + category.slice(1),
      data: data.filter(point => point.category === category),
      backgroundColor: colors[index % colors.length],
      borderColor: colors[index % colors.length],
      pointRadius: 8,
      pointHoverRadius: 12
    }));

    return { datasets };
  }, [filteredOpportunities]);

  // Chart.js配置
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: '机会矩阵：影响力 vs 实施难度'
      },
      tooltip: {
        callbacks: {
          title: (items: TooltipItem<'scatter'>[]) => {
            const raw = items[0]?.raw as { label?: string } | undefined;
            return raw?.label || '';
          },
          label: (context: TooltipItem<'scatter'>) => {
            const point = context.raw as { x: number; y: number };
            return [
              `影响力: ${point.y === 1 ? '低' : point.y === 2 ? '中' : '高'}`,
              `实施难度: ${point.x === 1 ? '低' : point.x === 2 ? '中' : '高'}`
            ];
          }
        }
      }
    },
    scales: {
      x: {
        type: 'linear' as const,
        position: 'bottom' as const,
        title: {
          display: true,
          text: '实施难度'
        },
        min: 0.5,
        max: 3.5,
        ticks: {
          stepSize: 1,
          callback: (value: number | string) => {
            if (value === 1) return '低';
            if (value === 2) return '中';
            if (value === 3) return '高';
            return '';
          }
        }
      },
      y: {
        title: {
          display: true,
          text: '业务影响力'
        },
        min: 0.5,
        max: 3.5,
        ticks: {
          stepSize: 1,
          callback: (value: number | string) => {
            if (value === 1) return '低';
            if (value === 2) return '中';
            if (value === 3) return '高';
            return '';
          }
        }
      }
    }
  };

  const getImpactColor = (impact: string): string => {
    switch (impact) {
      case 'high': return 'text-green-600 bg-green-100';
      case 'medium': return 'text-yellow-600 bg-yellow-100';
      case 'low': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getDifficultyColor = (difficulty: string): string => {
    switch (difficulty) {
      case 'low': return 'text-green-600 bg-green-100';
      case 'medium': return 'text-yellow-600 bg-yellow-100'; 
      case 'high': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getPriorityLabel = (priority: number): { label: string; color: string } => {
    if (priority >= 2) return { label: '高优先级', color: 'text-green-600 bg-green-100' };
    if (priority >= 1.5) return { label: '中优先级', color: 'text-yellow-600 bg-yellow-100' };
    return { label: '低优先级', color: 'text-red-600 bg-red-100' };
  };

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center space-x-2">
        <SparklesIcon className="h-6 w-6 text-indigo-600" />
        <h2 className="text-2xl font-bold text-gray-900">机会矩阵</h2>
      </div>

      {/* 控制栏 */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <FunnelIcon className="h-4 w-4 text-gray-500" />
              <span className="text-sm text-gray-700">影响力:</span>
              <select
                value={filterByImpact}
                onChange={(e) => setFilterByImpact(e.target.value as typeof filterByImpact)}
                className="border border-gray-300 rounded-md px-2 py-1 text-sm"
              >
                <option value="all">全部</option>
                <option value="high">高</option>
                <option value="medium">中</option>
                <option value="low">低</option>
              </select>
            </div>

            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-700">难度:</span>
              <select
                value={filterByDifficulty}
                onChange={(e) => setFilterByDifficulty(e.target.value as typeof filterByDifficulty)}
                className="border border-gray-300 rounded-md px-2 py-1 text-sm"
              >
                <option value="all">全部</option>
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
              </select>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <AdjustmentsHorizontalIcon className="h-4 w-4 text-gray-500" />
            <span className="text-sm text-gray-700">排序:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="border border-gray-300 rounded-md px-2 py-1 text-sm"
            >
              <option value="priority">优先级</option>
              <option value="impact">影响力</option>
              <option value="difficulty">难度</option>
            </select>
          </div>
        </div>
      </div>

      {/* 散点图可视化 */}
      {filteredOpportunities.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="h-96">
            <Scatter data={chartData} options={chartOptions} />
          </div>
        </div>
      )}

      {/* 机会卡片列表 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {filteredOpportunities.map((opportunity) => {
          const priorityInfo = getPriorityLabel(opportunity.priority);
          
          return (
            <div key={opportunity.id} className="bg-white rounded-lg shadow-sm border hover:shadow-md transition-shadow">
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center space-x-2">
                    <LightBulbIcon className="h-5 w-5 text-yellow-500" />
                    <h3 className="text-lg font-semibold text-gray-900">{opportunity.title}</h3>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${priorityInfo.color}`}>
                    {priorityInfo.label}
                  </span>
                </div>
                
                <p className="text-gray-600 mb-4">{opportunity.description}</p>
                
                {/* 指标 */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-gray-500">业务影响</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getImpactColor(opportunity.impact)}`}>
                        {opportunity.impact === 'high' ? '高' : opportunity.impact === 'medium' ? '中' : '低'}
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-green-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${(opportunity.impactScore / 3) * 100}%` }}
                      />
                    </div>
                  </div>
                  
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-gray-500">实施难度</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getDifficultyColor(opportunity.difficulty)}`}>
                        {opportunity.difficulty === 'high' ? '高' : opportunity.difficulty === 'medium' ? '中' : '低'}
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${(opportunity.difficultyScore / 3) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
                
                {/* 底部信息 */}
                <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                  <div className="text-sm text-gray-500">
                    <span className="font-medium">潜在价值: </span>
                    <span className="text-green-600 font-semibold">{opportunity.potentialValue}</span>
                  </div>
                  <button
                    onClick={() => onOpportunityClick?.(opportunity.title)}
                    className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50"
                  >
                    查看详情
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {filteredOpportunities.length === 0 && (
        <div className="bg-white rounded-lg shadow-sm border">
          <div className="p-8 text-center text-gray-500">
            <SparklesIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>暂无机会数据或不符合筛选条件</p>
          </div>
        </div>
      )}
    </div>
  );
};

export { OpportunityMatrix };
export default OpportunityMatrix;