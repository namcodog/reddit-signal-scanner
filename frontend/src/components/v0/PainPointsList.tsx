/**
 * PainPointsList组件 - 用户痛点分析展示
 * 显示用户痛点、严重程度、情感倾向和交互式筛选功能
 */

import React, { useState, useMemo } from 'react';
import logger from '@/utils/logger';
import { 
  ExclamationTriangleIcon, 
  HandThumbUpIcon, 
  HandThumbDownIcon, 
  MinusIcon, 
  EyeIcon,
  FunnelIcon,
  AdjustmentsHorizontalIcon
} from '@heroicons/react/24/outline';

import type { PainPointsListProps } from '@/types/contracts/report.contract';

// 扩展洞察类型以包含计算字段
interface ProcessedInsight {
  title: string;
  content: string;
  confidence: number;
  source_count: number;
  tags: string[];
  // 计算字段
  frequency: number;
  sentiment: number;
  severity: 'high' | 'medium' | 'low';
}

const PainPointsList: React.FC<PainPointsListProps> = ({
  insights = [],  // 修复：添加默认值，避免undefined.map()错误
  sentimentSummary: _sentimentSummary = {},  // 修复：添加默认值
  onInsightClick
}) => {
  const [sortBy, setSortBy] = useState<'confidence' | 'frequency' | 'sentiment'>('confidence');
  const [filterBy, setFilterBy] = useState<'all' | 'high' | 'medium' | 'low'>('all');

  // 数据处理和排序
  const processedInsights: ProcessedInsight[] = useMemo(() => {
    // 类型安全检查：确保insights是数组
    let processed = (insights || []).map(insight => ({
      ...insight,
      // 计算频率评分（基于source_count）
      frequency: Math.min(insight.source_count / 10, 1), // 标准化到0-1
      // 模拟情感评分（实际应从后端获取）
      sentiment: insight.tags.includes('negative') ? 0.3 : 
                insight.tags.includes('positive') ? 0.8 : 0.5,
      // 严重程度分类
      severity: (insight.confidence > 0.8 ? 'high' : 
               insight.confidence > 0.5 ? 'medium' : 'low') as 'high' | 'medium' | 'low'
    }));

    // 过滤
    if (filterBy !== 'all') {
      processed = processed.filter(insight => insight.severity === filterBy);
    }

    // 排序
    processed.sort((a, b) => {
      switch (sortBy) {
        case 'frequency':
          return b.frequency - a.frequency;
        case 'sentiment':
          return a.sentiment - b.sentiment; // 情感问题优先（分数低的）
        case 'confidence':
        default:
          return b.confidence - a.confidence;
      }
    });

    return processed;
  }, [insights, sortBy, filterBy]);

  // 类型安全检查：确保insights存在且是数组
  if (!insights || !Array.isArray(insights)) {
    logger.warn('PainPointsList: insights 属性必须是数组');
  }

  const getSeverityConfig = (severity: string): { color: string; bgColor: string; label: string } => {
    switch (severity) {
      case 'high': 
        return { color: 'text-red-600', bgColor: 'bg-red-50 border-red-200', label: '高' };
      case 'medium': 
        return { color: 'text-yellow-600', bgColor: 'bg-yellow-50 border-yellow-200', label: '中' };
      case 'low': 
        return { color: 'text-blue-600', bgColor: 'bg-blue-50 border-blue-200', label: '低' };
      default: 
        return { color: 'text-gray-600', bgColor: 'bg-gray-50 border-gray-200', label: '未知' };
    }
  };

  const getSentimentIcon = (sentiment: number): React.ReactNode => {
    if (sentiment > 0.6) return <HandThumbUpIcon className="h-4 w-4 text-green-600" />;
    if (sentiment < 0.4) return <HandThumbDownIcon className="h-4 w-4 text-red-600" />;
    return <MinusIcon className="h-4 w-4 text-gray-600" />;
  };

  // 统计数据
  const stats = {
    high: processedInsights.filter(i => i.severity === 'high').length,
    medium: processedInsights.filter(i => i.severity === 'medium').length,
    low: processedInsights.filter(i => i.severity === 'low').length,
    avgConfidence: processedInsights.length > 0 
      ? Math.round(processedInsights.reduce((sum, i) => sum + i.confidence, 0) / processedInsights.length * 100)
      : 0
  };

  return (
    <div className="space-y-6">
      {/* 标题和控制 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <ExclamationTriangleIcon className="h-6 w-6 text-orange-600" />
          <h2 className="text-2xl font-bold text-gray-900">用户痛点分析</h2>
        </div>
        
        <div className="flex items-center space-x-4">
          {/* 过滤器 */}
          <div className="flex items-center space-x-2">
            <FunnelIcon className="h-4 w-4 text-gray-500" />
            <select
              value={filterBy}
              onChange={(e) => setFilterBy(e.target.value as typeof filterBy)}
              className="border border-gray-300 rounded-md px-3 py-1 text-sm"
            >
              <option value="all">全部</option>
              <option value="high">高严重</option>
              <option value="medium">中严重</option>
              <option value="low">低严重</option>
            </select>
          </div>
          
          {/* 排序 */}
          <div className="flex items-center space-x-2">
            <AdjustmentsHorizontalIcon className="h-4 w-4 text-gray-500" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="border border-gray-300 rounded-md px-3 py-1 text-sm"
            >
              <option value="confidence">置信度</option>
              <option value="frequency">频率</option>
              <option value="sentiment">情感</option>
            </select>
          </div>
        </div>
      </div>

      {/* 统计概览 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm border p-6 text-center">
          <div className="text-2xl font-bold text-red-600 mb-1">{stats.high}</div>
          <div className="text-sm text-gray-600">高严重性问题</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm border p-6 text-center">
          <div className="text-2xl font-bold text-yellow-600 mb-1">{stats.medium}</div>
          <div className="text-sm text-gray-600">中严重性问题</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm border p-6 text-center">
          <div className="text-2xl font-bold text-blue-600 mb-1">{stats.low}</div>
          <div className="text-sm text-gray-600">低严重性问题</div>
        </div>
        
        <div className="bg-white rounded-lg shadow-sm border p-6 text-center">
          <div className="text-2xl font-bold text-gray-900 mb-1">{stats.avgConfidence}%</div>
          <div className="text-sm text-gray-600">平均置信度</div>
        </div>
      </div>

      {/* 痛点列表 */}
      <div className="space-y-4">
        {processedInsights.map((insight, index) => {
          const severityConfig = getSeverityConfig(insight.severity);
          
          return (
            <div key={index} className="bg-white rounded-lg shadow-sm border hover:shadow-md transition-shadow">
              <div className="p-6">
                <div className="flex items-start space-x-4">
                  {/* 严重程度指示器 */}
                  <div className={`flex-shrink-0 w-12 h-12 rounded-lg border-2 flex items-center justify-center ${severityConfig.bgColor} ${severityConfig.color}`}>
                    <span className="font-bold text-lg">
                      {severityConfig.label}
                    </span>
                  </div>
                  
                  {/* 内容区域 */}
                  <div className="flex-grow min-w-0">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-lg font-semibold text-gray-900">{insight.title}</h3>
                      <div className="flex items-center space-x-2 flex-shrink-0 ml-4">
                        {getSentimentIcon(insight.sentiment)}
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          置信度: {Math.round(insight.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                    
                    <p className="text-gray-600 mb-4">
                      {insight.content}
                    </p>
                    
                    {/* 指标 */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-gray-500">提及频率</span>
                          <span className="text-sm font-medium text-gray-900">{insight.source_count}次</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${insight.frequency * 100}%` }}
                          />
                        </div>
                      </div>
                      
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-gray-500">置信度</span>
                          <span className="text-sm font-medium text-gray-900">{Math.round(insight.confidence * 100)}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-green-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${insight.confidence * 100}%` }}
                          />
                        </div>
                      </div>
                      
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-gray-500">情感倾向</span>
                          <span className="text-sm font-medium text-gray-900">
                            {insight.sentiment > 0.6 ? '积极' : insight.sentiment < 0.4 ? '消极' : '中性'}
                          </span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className={`h-2 rounded-full transition-all duration-300 ${
                              insight.sentiment > 0.6 ? 'bg-green-600' : 
                              insight.sentiment < 0.4 ? 'bg-red-600' : 'bg-gray-600'
                            }`}
                            style={{ width: `${insight.sentiment * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                    
                    {/* 标签和操作 */}
                    <div className="flex items-center justify-between">
                      <div className="flex flex-wrap gap-1">
                        {insight.tags.map((tag, tagIndex) => (
                          <span key={tagIndex} className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                            {tag}
                          </span>
                        ))}
                      </div>
                      
                      <button
                        onClick={() => onInsightClick?.(insight)}
                        className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50"
                      >
                        <EyeIcon className="h-4 w-4 mr-1" />
                        查看详情
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        
        {processedInsights.length === 0 && (
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

export { PainPointsList };
export default PainPointsList;
