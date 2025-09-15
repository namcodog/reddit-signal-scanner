import type { ApiResponse, PaginatedResponse } from './base.api';
import type { ReportData, ReportFormat } from '../contracts/report.contract';

// 获取报告请求参数
export interface GetReportRequest {
  task_id: string;
  format?: ReportFormat;
}

// 获取报告响应
export type GetReportResponse = ApiResponse<ReportData>;

// 报告列表请求参数
export interface GetReportsRequest {
  page?: number;
  page_size?: number;
  status?: string;
  user_id?: string;
  start_date?: string;
  end_date?: string;
}

// 报告列表项
export interface ReportListItem {
  task_id: string;
  query: string;
  status: string;
  created_at: string;
  completed_at?: string;
  total_posts: number;
  confidence_score: number;
}

// 报告列表响应
export type GetReportsResponse = PaginatedResponse<ReportListItem>;

// 导出报告请求
export interface ExportReportRequest {
  task_id: string;
  format: 'pdf' | 'json' | 'csv';
  include_raw_data?: boolean;
}

// 导出报告响应
export interface ExportReportResponse {
  download_url: string;
  expires_at: string;
  file_size: number;
  format: string;
}

// 分享报告请求
export interface ShareReportRequest {
  task_id: string;
  expires_in?: number; // 秒数
  password_protected?: boolean;
}

// 分享报告响应
export interface ShareReportResponse {
  share_url: string;
  share_token: string;
  expires_at: string;
  password?: string;
}

// 报告API客户端接口
export interface ReportApiClient {
  getReport(params: GetReportRequest): Promise<GetReportResponse>;
  getReports(params?: GetReportsRequest): Promise<GetReportsResponse>;
  exportReport(params: ExportReportRequest): Promise<ApiResponse<ExportReportResponse>>;
  shareReport(params: ShareReportRequest): Promise<ApiResponse<ShareReportResponse>>;
  deleteReport(taskId: string): Promise<ApiResponse<void>>;
}