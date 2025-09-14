/**
 * ReportPage组件单元测试
 * 测试报告页面的基础渲染和参数处理功能
 * 遵循100%类型安全和质量门禁要求
 */

import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import ReportPage from '@/pages/ReportPage';

// 类型定义 - 严格遵循质量门禁规则
interface MockUseParamsReturn {
  taskId?: string;
}

// Mock react-router-dom hooks
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useParams: vi.fn<[], MockUseParamsReturn>(),
  };
});

// 测试工具函数
const renderReportPageWithRouter = (taskId: string = 'test-task-123') => {
  const TestComponent = () => (
    <MemoryRouter initialEntries={[`/report/${taskId}`]}>
      <Routes>
        <Route path="/report/:taskId" element={<ReportPage />} />
      </Routes>
    </MemoryRouter>
  );

  return render(<TestComponent />);
};

describe('ReportPage', () => {
  // 获取mock函数 - 使用正确的导入方式
  const getMockUseParams = () => vi.mocked(useParams);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('基础渲染', () => {
    it('应该正确渲染页面标题', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      renderReportPageWithRouter();

      expect(screen.getByRole('heading', { level: 1, name: '分析报告' })).toBeInTheDocument();
    });

    it('应该显示页面背景和容器样式', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      const { container } = renderReportPageWithRouter();

      const mainContainer = container.querySelector('.min-h-screen.bg-gray-50');
      expect(mainContainer).toBeInTheDocument();

      const contentContainer = container.querySelector('.max-w-4xl.mx-auto');
      expect(contentContainer).toBeInTheDocument();
    });

    it('应该显示报告卡片容器', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      const { container } = renderReportPageWithRouter();

      const reportCard = container.querySelector('.bg-white.rounded-lg.shadow-lg');
      expect(reportCard).toBeInTheDocument();
    });
  });

  describe('任务ID显示', () => {
    it('应该正确显示有效的任务ID', () => {
      const taskId = 'valid-task-id-456';
      getMockUseParams().mockReturnValue({ taskId });
      renderReportPageWithRouter(taskId);

      expect(screen.getByText(`任务ID: ${taskId}`)).toBeInTheDocument();
    });

    it('应该处理未定义的任务ID', () => {
      getMockUseParams().mockReturnValue({ taskId: undefined });
      renderReportPageWithRouter();

      expect(screen.getByText('任务ID: 未知')).toBeInTheDocument();
    });

    it('应该处理空字符串任务ID', () => {
      getMockUseParams().mockReturnValue({ taskId: '' });
      renderReportPageWithRouter();

      expect(screen.getByText('任务ID: 未知')).toBeInTheDocument();
    });

    it('应该处理长任务ID的显示', () => {
      const longTaskId = 'very-long-task-id-with-many-characters-and-hyphens-12345';
      getMockUseParams().mockReturnValue({ taskId: longTaskId });
      renderReportPageWithRouter(longTaskId);

      expect(screen.getByText(`任务ID: ${longTaskId}`)).toBeInTheDocument();
    });
  });

  describe('开发中状态显示', () => {
    it('应该显示开发中的图标', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      renderReportPageWithRouter();

      expect(screen.getByText('📊')).toBeInTheDocument();
    });

    it('应该显示开发中的标题', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      renderReportPageWithRouter();

      expect(screen.getByRole('heading', { level: 2, name: '报告页面开发中' })).toBeInTheDocument();
    });

    it('应该显示PRD任务说明', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      renderReportPageWithRouter();

      expect(screen.getByText('将在PRD-05-05任务中实现完整的数据可视化功能')).toBeInTheDocument();
    });

    it('应该显示功能预览信息', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      renderReportPageWithRouter();

      expect(screen.getByText('包含：执行摘要、痛点分析、竞品情报、机会矩阵')).toBeInTheDocument();
    });
  });

  describe('样式和布局', () => {
    it('应该具有居中的文本对齐', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      const { container } = renderReportPageWithRouter();

      // 检查标题部分的居中样式
      const titleSection = container.querySelector('.text-center.mb-8');
      expect(titleSection).toBeInTheDocument();

      // 检查开发中状态的居中样式
      const developmentSection = container.querySelector('.text-center.text-gray-500.py-12');
      expect(developmentSection).toBeInTheDocument();
    });

    it('应该具有正确的间距类', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      const { container } = renderReportPageWithRouter();

      // 检查页面间距
      const pageContainer = container.querySelector('.py-8');
      expect(pageContainer).toBeInTheDocument();

      // 检查内容间距
      const contentContainer = container.querySelector('.px-4');
      expect(contentContainer).toBeInTheDocument();

      // 检查卡片内边距
      const cardContainer = container.querySelector('.p-8');
      expect(cardContainer).toBeInTheDocument();
    });

    it('应该具有正确的颜色主题', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      const { container } = renderReportPageWithRouter();

      // 检查背景颜色
      const background = container.querySelector('.bg-gray-50');
      expect(background).toBeInTheDocument();

      // 检查卡片背景
      const cardBackground = container.querySelector('.bg-white');
      expect(cardBackground).toBeInTheDocument();

      // 检查文本颜色
      const grayText = container.querySelector('.text-gray-600');
      expect(grayText).toBeInTheDocument();

      const darkText = container.querySelector('.text-gray-900');
      expect(darkText).toBeInTheDocument();
    });

    it('应该具有正确的阴影和圆角', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      const { container } = renderReportPageWithRouter();

      const card = container.querySelector('.shadow-lg.rounded-lg');
      expect(card).toBeInTheDocument();
    });
  });

  describe('文本内容验证', () => {
    it('应该包含所有必要的文本内容', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      renderReportPageWithRouter();

      // 验证所有关键文本都存在
      const expectedTexts = [
        '分析报告',
        '任务ID: test-task-123',
        '📊',
        '报告页面开发中',
        '将在PRD-05-05任务中实现完整的数据可视化功能',
        '包含：执行摘要、痛点分析、竞品情报、机会矩阵',
      ];

      expectedTexts.forEach((text) => {
        expect(screen.getByText(text)).toBeInTheDocument();
      });
    });

    it('应该显示功能列表的详细内容', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      renderReportPageWithRouter();

      const featureList = screen.getByText('包含：执行摘要、痛点分析、竞品情报、机会矩阵');
      expect(featureList).toBeInTheDocument();
      expect(featureList).toHaveClass('text-sm', 'text-gray-400');
    });
  });

  describe('可访问性', () => {
    it('应该具有正确的语义HTML结构', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      renderReportPageWithRouter();

      // 检查标题层级
      const h1 = screen.getByRole('heading', { level: 1 });
      expect(h1).toHaveTextContent('分析报告');

      const h2 = screen.getByRole('heading', { level: 2 });
      expect(h2).toHaveTextContent('报告页面开发中');
    });

    it('应该具有合适的文字大小和对比度', () => {
      getMockUseParams().mockReturnValue({ taskId: 'test-task-123' });
      const { container } = renderReportPageWithRouter();

      // 检查主标题样式
      const mainTitle = container.querySelector('h1.text-3xl.font-bold');
      expect(mainTitle).toBeInTheDocument();

      // 检查副标题样式
      const subTitle = container.querySelector('h2.text-xl.font-semibold');
      expect(subTitle).toBeInTheDocument();
    });
  });

  describe('路由集成', () => {
    it('应该在不同路由参数下正确渲染', () => {
      const testCases = [
        'simple-id',
        'complex-id-with-hyphens-123',
        'UPPERCASE-ID',
        '12345',
        'mixed_case-ID_456',
      ];

      testCases.forEach((taskId) => {
        getMockUseParams().mockReturnValue({ taskId });
        const { unmount } = renderReportPageWithRouter(taskId);

        expect(screen.getByText(`任务ID: ${taskId}`)).toBeInTheDocument();
        expect(screen.getByText('分析报告')).toBeInTheDocument();

        unmount();
      });
    });

    it('应该在路由参数为空对象时处理正确', () => {
      getMockUseParams().mockReturnValue({});
      renderReportPageWithRouter();

      expect(screen.getByText('任务ID: 未知')).toBeInTheDocument();
      expect(screen.getByText('分析报告')).toBeInTheDocument();
    });
  });

  describe('边界情况处理', () => {
    it('应该处理null taskId', () => {
      getMockUseParams().mockReturnValue({ taskId: undefined });
      renderReportPageWithRouter();

      expect(screen.getByText('任务ID: 未知')).toBeInTheDocument();
    });

    it('应该处理taskId为数字的情况', () => {
      getMockUseParams().mockReturnValue({ taskId: '12345' });
      renderReportPageWithRouter();

      expect(screen.getByText('任务ID: 12345')).toBeInTheDocument();
    });

    it('应该处理特殊字符的taskId', () => {
      const specialTaskId = 'task_with-special@chars.123';
      getMockUseParams().mockReturnValue({ taskId: specialTaskId });
      renderReportPageWithRouter();

      expect(screen.getByText(`任务ID: ${specialTaskId}`)).toBeInTheDocument();
    });

    it('应该处理非常长的taskId', () => {
      const longTaskId = 'a'.repeat(100);
      getMockUseParams().mockReturnValue({ taskId: longTaskId });
      renderReportPageWithRouter();

      expect(screen.getByText(`任务ID: ${longTaskId}`)).toBeInTheDocument();
    });
  });
});