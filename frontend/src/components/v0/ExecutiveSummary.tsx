import React from 'react';
import {
  ChartBarIcon,
  UserGroupIcon,
  LightBulbIcon,
  ArrowTrendingUpIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';

import { ExecutiveSummaryProps } from '@/types/contracts/report.contract';

const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({
  executiveSummary,
  totalPosts = 0,
  totalComments = 0,
  confidence = 0,
  sentimentSummary = {}
}) => {
  // 计算情感分布
  const sentimentData = Object.entries(sentimentSummary).map(([key, value]) => ({
    label: key === 'positive' ? '积极' : key === 'negative' ? '消极' : '中性',
    value: Math.round(value * 100),
    color: key === 'positive' ? 'text-green-600' : key === 'negative' ? 'text-red-600' : 'text-gray-600'
  }));

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">执行摘要</h2>
          <div className="flex items-center text-sm text-gray-500">
            <CheckCircleIcon className="h-4 w-4 mr-1 text-green-500" />
            置信度: {Math.round(confidence * 100)}%
          </div>
        </div>

        {/* 主要标题 */}
        {executiveSummary?.headline && (
          <div className="mb-6">
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {executiveSummary.headline}
            </h3>
          </div>
        )}

        {/* 关键指标 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="flex items-center">
              <ChartBarIcon className="h-8 w-8 text-blue-600 mr-3" />
              <div>
                <div className="text-2xl font-bold text-blue-600">{totalPosts}</div>
                <div className="text-sm text-gray-600">分析帖子</div>
              </div>
            </div>
          </div>

          <div className="bg-green-50 rounded-lg p-4">
            <div className="flex items-center">
              <UserGroupIcon className="h-8 w-8 text-green-600 mr-3" />
              <div>
                <div className="text-2xl font-bold text-green-600">{totalComments}</div>
                <div className="text-sm text-gray-600">用户评论</div>
              </div>
            </div>
          </div>

          <div className="bg-purple-50 rounded-lg p-4">
            <div className="flex items-center">
              <LightBulbIcon className="h-8 w-8 text-purple-600 mr-3" />
              <div>
                <div className="text-2xl font-bold text-purple-600">
                  {executiveSummary?.key_insights || 0}
                </div>
                <div className="text-sm text-gray-600">关键洞察</div>
              </div>
            </div>
          </div>

          <div className="bg-orange-50 rounded-lg p-4">
            <div className="flex items-center">
              <ArrowTrendingUpIcon className="h-8 w-8 text-orange-600 mr-3" />
              <div>
                <div className="text-2xl font-bold text-orange-600">
                  {executiveSummary?.total_communities || 0}
                </div>
                <div className="text-sm text-gray-600">覆盖社区</div>
              </div>
            </div>
          </div>
        </div>

        {/* 情感分析 */}
        {sentimentData.length > 0 && (
          <div className="mb-6">
            <h4 className="text-sm font-medium text-gray-900 mb-3">情感分布</h4>
            <div className="flex space-x-4">
              {sentimentData.map((item, index) => (
                <div key={index} className="flex items-center">
                  <div className={`text-lg font-semibold ${item.color} mr-2`}>
                    {item.value}%
                  </div>
                  <div className="text-sm text-gray-600">{item.label}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 核心要点 */}
        {executiveSummary?.summary_points && executiveSummary.summary_points.length > 0 && (
          <div className="mb-6">
            <h4 className="text-sm font-medium text-gray-900 mb-3">核心要点</h4>
            <ul className="space-y-2">
              {executiveSummary.summary_points.map((point, index) => (
                <li key={index} className="flex items-start">
                  <div className="flex-shrink-0 w-2 h-2 bg-blue-600 rounded-full mt-2 mr-3"></div>
                  <span className="text-sm text-gray-700">{point}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 顶级机会 */}
        {executiveSummary?.top_opportunity && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-start">
              <LightBulbIcon className="h-5 w-5 text-yellow-600 mt-0.5 mr-3 flex-shrink-0" />
              <div>
                <h4 className="text-sm font-medium text-yellow-800 mb-1">顶级商业机会</h4>
                <p className="text-sm text-yellow-700">{executiveSummary.top_opportunity}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ExecutiveSummary;
