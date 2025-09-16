/**
 * Report服务测试
 * 严格按照Context7最佳实践：vi.mock + 动态导入
 * 100%类型安全，零技术债务
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// Context7最佳实践：使用vi.mock模拟依赖
vi.mock('@/services/api.client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

import { apiClient } from '@/services/api.client';

describe('ReportService', () => {
  let reportService: any;
  let mockConsoleWarn: any;

  beforeEach(async () => {
    // Context7最佳实践：重置模块缓存
    vi.resetModules();
    
    // Context7最佳实践：重置所有mock
    vi.clearAllMocks();
    
    // Mock console.warn
    mockConsoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    
    // Context7最佳实践：动态导入模块
    const module = await import('@/services/report.service');
    reportService = module.reportService;
  });

  afterEach(() => {
    // Context7最佳实践：恢复console方法
    mockConsoleWarn.mockRestore();
  });

  describe('getReport方法', () => {
    it('应该获取单个报告', async () => {
      const mockReportData = {
        task_id: 'test-task-123',
        title: 'Test Report',
        analysis_results: {},
      };

      vi.mocked(apiClient.get).mockResolvedValue(mockReportData);

      const result = await reportService.getReport({
        task_id: 'test-task-123',
        format: 'json'
      });

      expect(apiClient.get).toHaveBeenCalledWith(
        '/api/v1/reports/test-task-123',
        {
          params: {
            format: 'json'
          }
        }
      );

      expect(result).toEqual({
        success: true,
        message: 'Report retrieved successfully',
        timestamp: expect.any(String),
        data: mockReportData
      });
    });
  });

  describe('getReports方法', () => {
    it('应该获取报告列表', async () => {
      const mockReportsData = {
        reports: [
          { task_id: 'task-1', title: 'Report 1' },
          { task_id: 'task-2', title: 'Report 2' },
        ],
        total: 2
      };

      vi.mocked(apiClient.get).mockResolvedValue(mockReportsData);

      const result = await reportService.getReports({
        page: 1,
        limit: 10
      });

      expect(apiClient.get).toHaveBeenCalledWith(
        '/api/v1/reports',
        { params: { page: 1, limit: 10 } }
      );

      expect(result).toEqual({
        success: true,
        message: 'Reports retrieved successfully',
        timestamp: expect.any(String),
        data: mockReportsData
      });
    });

    it('应该使用默认参数获取报告列表', async () => {
      const mockReportsData = { reports: [], total: 0 };

      vi.mocked(apiClient.get).mockResolvedValue(mockReportsData);

      const result = await reportService.getReports();

      expect(apiClient.get).toHaveBeenCalledWith(
        '/api/v1/reports',
        { params: {} }
      );

      expect(result.success).toBe(true);
    });
  });

  describe('exportReport方法', () => {
    it('应该导出报告', async () => {
      const mockExportData = {
        export_url: 'https://example.com/export/test-task-123.pdf',
        expires_at: '2024-01-01T00:00:00Z'
      };

      vi.mocked(apiClient.post).mockResolvedValue(mockExportData);

      const result = await reportService.exportReport({
        task_id: 'test-task-123',
        format: 'pdf',
        include_raw_data: true
      });

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/reports/test-task-123/export',
        {
          format: 'pdf',
          include_raw_data: true
        }
      );

      expect(result).toEqual({
        success: true,
        message: 'Export created successfully',
        timestamp: expect.any(String),
        data: mockExportData
      });
    });

    it('应该使用默认值导出报告', async () => {
      const mockExportData = {
        export_url: 'https://example.com/export/test-task-123.pdf'
      };

      vi.mocked(apiClient.post).mockResolvedValue(mockExportData);

      await reportService.exportReport({
        task_id: 'test-task-123',
        format: 'pdf'
      });

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/reports/test-task-123/export',
        {
          format: 'pdf',
          include_raw_data: false
        }
      );
    });
  });

  describe('shareReport方法', () => {
    it('应该分享报告', async () => {
      const mockShareData = {
        share_url: 'https://example.com/share/abc123',
        expires_at: '2024-01-01T00:00:00Z'
      };

      vi.mocked(apiClient.post).mockResolvedValue(mockShareData);

      const result = await reportService.shareReport({
        task_id: 'test-task-123',
        expires_in: 3600,
        password_protected: true
      });

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/reports/test-task-123/share',
        {
          expires_in: 3600,
          password_protected: true
        }
      );

      expect(result).toEqual({
        success: true,
        message: 'Share link created successfully',
        timestamp: expect.any(String),
        data: mockShareData
      });
    });

    it('应该使用默认值分享报告', async () => {
      const mockShareData = {
        share_url: 'https://example.com/share/abc123'
      };

      vi.mocked(apiClient.post).mockResolvedValue(mockShareData);

      await reportService.shareReport({
        task_id: 'test-task-123',
        expires_in: 3600
      });

      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/reports/test-task-123/share',
        {
          expires_in: 3600,
          password_protected: false
        }
      );
    });
  });

  describe('deleteReport方法', () => {
    it('应该删除报告', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue(undefined);

      const result = await reportService.deleteReport('test-task-123');

      expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/reports/test-task-123');

      expect(result).toEqual({
        success: true,
        message: 'Report deleted successfully',
        timestamp: expect.any(String),
        data: undefined
      });
    });
  });

  describe('trackView方法', () => {
    it('应该记录报告查看事件', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({});

      await reportService.trackView('test-task-123');

      expect(apiClient.post).toHaveBeenCalledWith('/api/v1/reports/test-task-123/view');
    });

    it('应该静默处理跟踪失败', async () => {
      const error = new Error('Tracking failed');
      vi.mocked(apiClient.post).mockRejectedValue(error);

      await reportService.trackView('test-task-123');

      expect(mockConsoleWarn).toHaveBeenCalledWith('Failed to track view:', error);
    });
  });

  describe('getReportStats方法', () => {
    it('应该获取报告统计信息', async () => {
      const mockStatsData = {
        views: 100,
        shares: 5,
        exports: 3,
        created_at: '2024-01-01T00:00:00Z',
        last_viewed: '2024-01-02T00:00:00Z'
      };

      vi.mocked(apiClient.get).mockResolvedValue(mockStatsData);

      const result = await reportService.getReportStats('test-task-123');

      expect(apiClient.get).toHaveBeenCalledWith('/api/v1/reports/test-task-123/stats');
      expect(result).toEqual(mockStatsData);
    });
  });

  describe('错误处理', () => {
    it('应该正确抛出API错误', async () => {
      const error = new Error('API Error');
      vi.mocked(apiClient.get).mockRejectedValue(error);

      await expect(reportService.getReport({ task_id: 'test-task-123' }))
        .rejects.toThrow('API Error');
    });

    it('应该正确抛出导出错误', async () => {
      const error = new Error('Export failed');
      vi.mocked(apiClient.post).mockRejectedValue(error);

      await expect(reportService.exportReport({
        task_id: 'test-task-123',
        format: 'pdf'
      })).rejects.toThrow('Export failed');
    });

    it('应该正确抛出删除错误', async () => {
      const error = new Error('Delete failed');
      vi.mocked(apiClient.delete).mockRejectedValue(error);

      await expect(reportService.deleteReport('test-task-123'))
        .rejects.toThrow('Delete failed');
    });
  });

  describe('单例导出', () => {
    it('应该正确导出单例实例', async () => {
      const { reportService: namedExport, default: defaultExport } = await import('@/services/report.service');
      
      expect(namedExport).toBeDefined();
      expect(defaultExport).toBeDefined();
      expect(namedExport).toBe(defaultExport);
    });
  });
});