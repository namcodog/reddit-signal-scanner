import { apiClient } from './api.client';
import logger from '@/utils/logger';
import type {
  GetReportRequest,
  GetReportResponse,
  GetReportsRequest,
  GetReportsResponse,
  ExportReportRequest,
  ExportReportResponse,
  ShareReportRequest,
  ShareReportResponse,
  ReportApiClient
} from '@/types/api/report.api';
import type { ApiResponse } from '@/types/api/base.api';
import type { ReportData } from '@/types/contracts/report.contract';

type BackendSuccessResponse<T> = {
  status: 'success';
  message: string;
  timestamp: string;
  data: T;
  request_id?: string;
};

class ReportService implements ReportApiClient {
  private readonly baseUrl = '/api/v1/report';
  private readonly collectionUrl = '/api/v1/reports';

  /**
   * 获取单个报告
   */
  async getReport(params: GetReportRequest): Promise<GetReportResponse> {
    const response = await apiClient.get<BackendSuccessResponse<ReportData>>(
      `${this.baseUrl}/${params.task_id}`,
      {
        params: {
          format: params.format
        }
      }
    );

    if (response.status !== 'success') {
      throw new Error(response.message || '获取报告失败');
    }

    return {
      success: true,
      message: response.message || '分析报告获取成功',
      timestamp: response.timestamp,
      data: response.data
    };
  }

  /**
   * 获取报告列表
   */
  async getReports(params: GetReportsRequest = {}): Promise<GetReportsResponse> {
    return await apiClient
      .get<GetReportsResponse['data']>(this.collectionUrl, { params })
      .then(data => ({
        success: true,
        message: 'Reports retrieved successfully',
        timestamp: new Date().toISOString(),
        data
      }));
  }

  /**
   * 导出报告
   */
  async exportReport(params: ExportReportRequest): Promise<ApiResponse<ExportReportResponse>> {
    const response = await apiClient.post<BackendSuccessResponse<ExportReportResponse>>(
      `${this.baseUrl}/${params.task_id}/export`,
      {
        format: params.format,
        include_raw_data: params.include_raw_data ?? false
      }
    );

    if (response.status !== 'success') {
      throw new Error(response.message || '导出报告失败');
    }

    return {
      success: true,
      message: response.message || 'Export created successfully',
      timestamp: response.timestamp,
      data: response.data
    };
  }

  /**
   * 分享报告
   */
  async shareReport(params: ShareReportRequest): Promise<ApiResponse<ShareReportResponse>> {
    const response = await apiClient.post<BackendSuccessResponse<ShareReportResponse>>(
      `${this.baseUrl}/${params.task_id}/share`,
      {
        expires_in: params.expires_in,
        password_protected: params.password_protected ?? false
      }
    );

    if (response.status !== 'success') {
      throw new Error(response.message || '分享报告失败');
    }

    return {
      success: true,
      message: response.message || 'Share link created successfully',
      timestamp: response.timestamp,
      data: response.data
    };
  }

  /**
   * 删除报告
   */
  async deleteReport(taskId: string): Promise<ApiResponse<void>> {
    await apiClient.delete(`${this.baseUrl}/${taskId}`);

    return {
      success: true,
      message: 'Report deleted successfully',
      timestamp: new Date().toISOString(),
      data: undefined
    };
  }

  /**
   * 记录报告查看事件（统计用）
   */
  async trackView(taskId: string): Promise<void> {
    try {
      await apiClient.post(`${this.baseUrl}/${taskId}/view`);
    } catch (error) {
      // 静默失败，不影响主要功能
      logger.warn('Failed to track view:', error as Error);
    }
  }

  /**
   * 获取报告统计信息
   */
  async getReportStats(taskId: string): Promise<{
    views: number;
    shares: number;
    exports: number;
    created_at: string;
    last_viewed: string;
  }> {
    const response = await apiClient.get<{
      views: number;
      shares: number;
      exports: number;
      created_at: string;
      last_viewed: string;
    }>(`${this.baseUrl}/${taskId}/stats`);
    
    return response;
  }
}

// 单例导出
export const reportService = new ReportService();
export default reportService;
