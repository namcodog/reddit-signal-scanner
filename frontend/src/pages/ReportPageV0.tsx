/**
 * 报告页面V0 - 类型安全的报告展示页面
 * 基于现有技术栈：Headless UI + Tailwind + Chart.js
 */

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeftIcon, 
  ShareIcon, 
  ArrowDownTrayIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline';

import { ExecutiveSummary } from '@/components/v0/ExecutiveSummary';
import { PainPointsList } from '@/components/v0/PainPointsList';
import { CompetitorAnalysis } from '@/components/v0/CompetitorAnalysis';
import { OpportunityMatrix } from '@/components/v0/OpportunityMatrix';

import { reportService } from '@/services/report.service';
import logger from '@/utils/logger';
import type { 
  ReportData, 
  ReportFormat 
} from '@/types/contracts/report.contract';

interface ReportPageV0Props {
  format?: ReportFormat;
  embedded?: boolean; // 是否嵌入模式
}

const ReportPageV0: React.FC<ReportPageV0Props> = ({ 
  format = 'full' as ReportFormat,
  embedded = false 
}) => {
  // Router hooks
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  
  // State management
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [sharing, setSharing] = useState(false);
  
  // Hooks - auth available if needed
  // const { user } = useAuth();

  // Data fetching
  const fetchReport = useCallback(async (): Promise<void> => {
    if (!taskId) {
      setError('任务ID不能为空');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const response = await reportService.getReport({
        task_id: taskId,
        format
      });
      
      setReportData(response.data);
      
      // 记录查看事件
      await reportService.trackView(taskId);
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '获取报告失败';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [taskId, format]);

  // Effects
  useEffect(() => {
    void fetchReport();
  }, [fetchReport]);

  // Event handlers
  const handleExport = useCallback(async (exportFormat: 'pdf' | 'json'): Promise<void> => {
    if (!taskId || !reportData) return;

    try {
      setExporting(true);
      
      const result = await reportService.exportReport({
        task_id: taskId,
        format: exportFormat,
        include_raw_data: exportFormat === 'json'
      });
      
      // 触发下载
      const link = document.createElement('a');
      link.href = result.data.download_url;
      link.download = `report-${taskId}.${exportFormat}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
    } catch (err) {
      logger.error('Export failed:', err as Error);
    } finally {
      setExporting(false);
    }
  }, [taskId, reportData]);

  const handleShare = useCallback(async (): Promise<void> => {
    if (!taskId) return;

    try {
      setSharing(true);
      
      const result = await reportService.shareReport({
        task_id: taskId,
        expires_in: 7 * 24 * 60 * 60 // 7天
      });
      
      // 复制分享链接到剪贴板
      await navigator.clipboard.writeText(result.data.share_url);
      
      alert('分享链接已复制到剪贴板，有效期7天');
      
    } catch (err) {
      logger.error('Share failed:', err as Error);
    } finally {
      setSharing(false);
    }
  }, [taskId]);

  const handleBack = useCallback((): void => {
    navigate('/dashboard');
  }, [navigate]);

  const handleRetry = useCallback((): void => {
    void fetchReport();
  }, [fetchReport]);

  // Render loading state
  if (loading) {
    return (
      <div data-testid="report-page" className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="container mx-auto px-4 py-8 max-w-7xl">
          <ReportSkeleton />
        </div>
      </div>
    );
  }

  // Render error state
  if (error || !reportData) {
    return (
      <div data-testid="report-page" className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="container mx-auto px-4 py-8 max-w-7xl">
          <div className="max-w-2xl mx-auto">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <div className="flex items-center">
                <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mr-2" />
                <p className="text-red-800">
                  {error || '报告数据不存在或已被删除'}
                </p>
              </div>
            </div>
            
            <div className="text-center space-y-4">
              <button 
                onClick={handleRetry}
                className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                <ArrowPathIcon className="h-4 w-4 mr-2" />
                重试
              </button>
              
              {!embedded && (
                <button 
                  onClick={handleBack}
                  className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 ml-4"
                >
                  <ArrowLeftIcon className="h-4 w-4 mr-2" />
                  返回
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Main render
  return (
    <div data-testid="report-page" className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-4">
              {!embedded && (
                <button
                  onClick={handleBack}
                  className="inline-flex items-center text-gray-600 hover:text-gray-900"
                >
                  <ArrowLeftIcon className="h-4 w-4 mr-2" />
                  返回
                </button>
              )}
              
              <div>
                <h1 className="text-3xl font-bold text-gray-900">
                  分析报告
                </h1>
                <p className="text-gray-600 mt-1">
                  任务ID: <span data-testid="task-id">{taskId}</span> • 生成于 {reportData?.generated_at ? new Date(reportData.generated_at).toLocaleString() : '开发中'}
                </p>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                数据时效: {reportData.data_freshness}
              </span>
              
              <button
                onClick={() => void handleExport('json')}
                disabled={exporting}
                className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
              >
                <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
                JSON
              </button>
              
              <button
                onClick={() => void handleExport('pdf')}
                disabled={exporting}
                className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
              >
                <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
                PDF
              </button>
              
              <button
                onClick={() => void handleShare()}
                disabled={sharing}
                className="inline-flex items-center px-3 py-1 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                <ShareIcon className="h-4 w-4 mr-1" />
                分享
              </button>
            </div>
          </div>
          
          {/* Query display */}
          <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-medium text-gray-900 mb-1">分析查询</h3>
                <p className="text-gray-600">{reportData?.query || '分析查询内容'}</p>
              </div>
              <div className="text-right text-sm text-gray-500">
                <div>帖子: {reportData?.total_posts ? reportData.total_posts.toLocaleString() : '0'}</div>
                <div>评论: {reportData?.total_comments ? reportData.total_comments.toLocaleString() : '0'}</div>
                <div>用时: {reportData?.analysis_duration ? Math.round(reportData.analysis_duration) : '0'}秒</div>
              </div>
            </div>
          </div>
        </div>

        {/* Report Content */}
        <div className="space-y-8">
          {/* Executive Summary */}
          <ExecutiveSummary
            insights={reportData.key_insights}
            totalPosts={reportData.total_posts}
            totalComments={reportData.total_comments}
            confidence={0.85} // 暂时硬编码，后续从数据中获取
            sentimentSummary={reportData.sentiment_summary}
          />

          {/* Pain Points Analysis */}
          <PainPointsList
            insights={reportData.key_insights}
            sentimentSummary={reportData.sentiment_summary}
            onInsightClick={(insight) => {
              alert(`洞察: ${insight.title}\n置信度: ${(insight.confidence * 100).toFixed(1)}%`);
            }}
          />

          {/* Competitor Analysis */}
          <CompetitorAnalysis
            competitors={[]} // 临时为空，等待后端数据结构完善
            onCompetitorSelect={(competitor) => {
              logger.debug('Selected competitor:', competitor);
            }}
          />

          {/* Opportunity Matrix */}
          <OpportunityMatrix
            opportunities={[]} // 临时为空，等待后端数据结构完善
            onOpportunityClick={(opportunity) => {
              logger.debug('Selected opportunity:', opportunity);
            }}
          />
        </div>
      </div>
    </div>
  );
};

// Loading skeleton component
const ReportSkeleton: React.FC = () => (
  <div className="space-y-8">
    <div className="flex items-center justify-between">
      <div className="space-y-2">
        <div className="h-8 w-64 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-96 bg-gray-200 rounded animate-pulse" />
      </div>
      <div className="flex space-x-2">
        <div className="h-10 w-20 bg-gray-200 rounded animate-pulse" />
        <div className="h-10 w-20 bg-gray-200 rounded animate-pulse" />
        <div className="h-10 w-20 bg-gray-200 rounded animate-pulse" />
      </div>
    </div>
    
    <div className="bg-white rounded-lg shadow-sm border p-6">
      <div className="h-4 w-full bg-gray-200 rounded animate-pulse mb-2" />
      <div className="h-4 w-2/3 bg-gray-200 rounded animate-pulse" />
    </div>
    
    {[...Array(4)].map((_, i) => (
      <div key={i} className="bg-white rounded-lg shadow-sm border">
        <div className="p-6 border-b">
          <div className="h-6 w-48 bg-gray-200 rounded animate-pulse" />
        </div>
        <div className="p-6">
          <div className="h-32 w-full bg-gray-200 rounded animate-pulse" />
        </div>
      </div>
    ))}
  </div>
);

export default ReportPageV0;
export { ReportPageV0 };