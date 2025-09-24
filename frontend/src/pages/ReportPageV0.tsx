import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeftIcon, ShareIcon, DocumentArrowDownIcon } from '@heroicons/react/24/outline';

import { ReportData } from '@/types/contracts/report.contract';
import { reportService } from '@/services/report.service';
import ExecutiveSummary from '@/components/v0/ExecutiveSummary';
import PainPointsList from '@/components/v0/PainPointsList';
import CompetitorAnalysis from '@/components/v0/CompetitorAnalysis';
import OpportunityMatrix from '@/components/v0/OpportunityMatrix';

const ReportPageV0: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReport = async () => {
      if (!taskId) {
        setError('任务ID缺失');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const response = await reportService.getReport({ task_id: taskId });
        setReportData(response.data);
        setError(null);
      } catch (err) {
        console.error('获取报告失败:', err);
        setError('获取报告失败，请稍后重试');
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [taskId]);

  const handleExport = (format: 'pdf' | 'json') => {
    if (!reportData) return;
    
    if (format === 'json') {
      const dataStr = JSON.stringify(reportData, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `report-${taskId}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } else {
      // PDF导出功能待实现
      console.log('PDF导出功能开发中...');
    }
  };

  const handleShare = () => {
    if (navigator.share) {
      navigator.share({
        title: `Reddit信号分析报告 - ${reportData?.query}`,
        url: window.location.href,
      });
    } else {
      // 复制链接到剪贴板
      navigator.clipboard.writeText(window.location.href);
      alert('链接已复制到剪贴板');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">正在加载报告...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-xl mb-4">⚠️ {error}</div>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  if (!reportData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">报告数据不存在</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 头部导航 */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <button
                onClick={() => navigate('/')}
                className="flex items-center text-gray-600 hover:text-gray-900"
              >
                <ArrowLeftIcon className="h-5 w-5 mr-2" />
                返回
              </button>
              <div className="ml-4">
                <h1 className="text-lg font-semibold text-gray-900">
                  {reportData.query} - 分析报告
                </h1>
                <p className="text-sm text-gray-500">
                  任务ID: {reportData.task_id}
                </p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              <button
                onClick={() => handleExport('json')}
                className="flex items-center px-3 py-2 text-sm text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
                导出JSON
              </button>
              <button
                onClick={handleShare}
                className="flex items-center px-3 py-2 text-sm text-white bg-blue-600 rounded-md hover:bg-blue-700"
              >
                <ShareIcon className="h-4 w-4 mr-2" />
                分享
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 主要内容 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-8">
          {/* 执行摘要 */}
          <ExecutiveSummary
            executiveSummary={reportData.executive_summary}
            totalPosts={reportData.total_posts}
            totalComments={reportData.total_comments}
            confidence={reportData.confidence_score || reportData.executive_summary?.confidence_score || 0.85}
            sentimentSummary={reportData.sentiment_summary}
          />

          {/* 市场指标 */}
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">市场指标</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {reportData.market_metrics.total_mentions}
                </div>
                <div className="text-sm text-gray-500">总提及数</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {(reportData.market_metrics.sentiment_score * 100).toFixed(1)}%
                </div>
                <div className="text-sm text-gray-500">情感分数</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-600">
                  {reportData.market_metrics.top_communities.length}
                </div>
                <div className="text-sm text-gray-500">热门社区</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">
                  {reportData.market_metrics.trending_keywords.length}
                </div>
                <div className="text-sm text-gray-500">热门关键词</div>
              </div>
            </div>
          </div>

          {/* 痛点分析 */}
          <PainPointsList
            painPoints={reportData.pain_points}
            sentimentSummary={reportData.sentiment_summary}
            onInsightClick={(insight) => {
              console.log('查看痛点详情:', insight);
            }}
          />

          {/* 竞品分析 */}
          <CompetitorAnalysis
            competitors={reportData.competitors}
            onCompetitorSelect={(competitor) => {
              console.log('选择竞品:', competitor);
            }}
          />

          {/* 商业机会 */}
          <OpportunityMatrix
            opportunities={reportData.opportunities}
            onOpportunityClick={(opportunity) => {
              console.log('查看机会详情:', opportunity);
            }}
          />
        </div>
      </div>
    </div>
  );
};

export default ReportPageV0;
