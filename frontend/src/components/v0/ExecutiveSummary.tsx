/**
 * ExecutiveSummary组件 - 执行摘要展示
 * 显示核心指标、关键洞察和情感分析概览
 */

import React from 'react';
import { 
  ArrowTrendingUpIcon, 
  UsersIcon, 
  ChatBubbleLeftRightIcon, 
  ClockIcon,
  TagIcon
} from '@heroicons/react/24/outline';

import type { ExecutiveSummaryProps } from '@/types/contracts/report.contract';

const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({
  insights = [],
  totalPosts = 0,
  totalComments = 0,
  sentimentSummary = {}
}) => {
  // 计算核心指标
  const topInsights = (insights || [])
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 5);
    
  const avgConfidence = (insights || []).length > 0 
    ? (insights || []).reduce((sum, insight) => sum + insight.confidence, 0) / (insights || []).length
    : 0;
    
  const totalSources = (insights || []).reduce((sum, insight) => sum + insight.source_count, 0);
  
  // 情感分析数据处理
  const sentimentData = Object.entries(sentimentSummary || {}).map(([key, value]) => ({
    label: key === 'positive' ? '积极' : key === 'negative' ? '消极' : '中性',
    value: Math.round(value * 100),
    color: key === 'positive' ? 'text-green-600' : key === 'negative' ? 'text-red-600' : 'text-gray-600',
    bgColor: key === 'positive' ? 'bg-green-100' : key === 'negative' ? 'bg-red-100' : 'bg-gray-100'
  }));

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-center space-x-2">
        <TagIcon className="h-6 w-6 text-blue-600" />
        <h2 className="text-2xl font-bold text-gray-900">执行摘要</h2>
      </div>

      {/* 核心指标卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 帖子数量 */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center">
            <div className="p-3 bg-blue-100 rounded-lg">
              <UsersIcon className="h-6 w-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-2xl font-bold text-gray-900">{totalPosts.toLocaleString()}</p>
              <p className="text-sm text-gray-600">分析帖子</p>
            </div>
          </div>
        </div>

        {/* 评论数量 */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center">
            <div className="p-3 bg-green-100 rounded-lg">
              <ChatBubbleLeftRightIcon className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-2xl font-bold text-gray-900">{totalComments.toLocaleString()}</p>
              <p className="text-sm text-gray-600">用户评论</p>
            </div>
          </div>
        </div>

        {/* 数据源 */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center">
            <div className="p-3 bg-purple-100 rounded-lg">
              <ArrowTrendingUpIcon className="h-6 w-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-2xl font-bold text-gray-900">{totalSources}</p>
              <p className="text-sm text-gray-600">数据来源</p>
            </div>
          </div>
        </div>

        {/* 置信度 */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center">
            <div className="p-3 bg-orange-100 rounded-lg">
              <ClockIcon className="h-6 w-6 text-orange-600" />
            </div>
            <div className="ml-4">
              <p className="text-2xl font-bold text-gray-900">{Math.round(avgConfidence * 100)}%</p>
              <p className="text-sm text-gray-600">平均置信度</p>
            </div>
          </div>
        </div>
      </div>

      {/* 主要洞察 */}
      <div className="bg-white rounded-lg shadow-sm border">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center space-x-2">
            <ArrowTrendingUpIcon className="h-5 w-5 text-gray-900" />
            <h3 className="text-lg font-semibold text-gray-900">核心洞察</h3>
          </div>
        </div>
        <div className="p-6">
          <div className="space-y-4">
            {topInsights.map((insight, index) => (
              <div key={index} className="flex items-start space-x-4 p-4 bg-gray-50 rounded-lg">
                <div className="flex-shrink-0">
                  <span className="inline-flex items-center justify-center w-8 h-8 bg-blue-100 text-blue-800 text-sm font-medium rounded-full">
                    #{index + 1}
                  </span>
                </div>
                <div className="flex-grow min-w-0">
                  <h4 className="font-medium text-gray-900 mb-1">{insight.title}</h4>
                  <p className="text-sm text-gray-600 mb-2">
                    {insight.content}
                  </p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4 text-xs text-gray-500">
                      <span>数据源: {insight.source_count}</span>
                      <span>置信度: {Math.round(insight.confidence * 100)}%</span>
                    </div>
                    {insight.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {insight.tags.slice(0, 3).map((tag, tagIndex) => (
                          <span key={tagIndex} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                            {tag}
                          </span>
                        ))}
                        {insight.tags.length > 3 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                            +{insight.tags.length - 3}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  {/* 置信度进度条 */}
                  <div className="mt-2">
                    <div className="w-full bg-gray-200 rounded-full h-1">
                      <div 
                        className="bg-blue-600 h-1 rounded-full transition-all duration-300"
                        style={{ width: `${insight.confidence * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
            
            {topInsights.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                <ArrowTrendingUpIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>暂无关键洞察数据</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 情感分析概览 */}
      {sentimentData.length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-gray-900">整体情感倾向</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-3 gap-4">
              {sentimentData.map((sentiment, index) => (
                <div key={index} className="text-center">
                  <div className={`text-3xl font-bold ${sentiment.color} mb-1`}>
                    {sentiment.value}%
                  </div>
                  <div className="text-sm text-gray-600 mb-2">
                    {sentiment.label}
                  </div>
                  {/* 情感进度条 */}
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full transition-all duration-300 ${sentiment.color.replace('text-', 'bg-')}`}
                      style={{ width: `${sentiment.value}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export { ExecutiveSummary };
export default ExecutiveSummary;