/**
 * InputPage组件测试 - 验证用户输入功能
 * 测试用户体验改进的核心功能
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import InputPage from '@/pages/InputPage';

// Mock navigate函数
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock验证工具
const mockValidateProductDescription = vi.fn();
const mockHttpClientPost = vi.fn();

vi.mock('@/utils/validation', () => ({
  default: {
    validateProductDescription: mockValidateProductDescription,
  },
}));

vi.mock('@/utils/httpClient', () => ({
  default: {
    post: mockHttpClientPost,
  },
}));

// 包装组件用于测试
const InputPageWrapper = () => (
  <BrowserRouter>
    <InputPage />
  </BrowserRouter>
);

describe('InputPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockValidateProductDescription.mockReset();
    mockHttpClientPost.mockReset();
  });

  describe('页面渲染', () => {
    it('应该渲染基本页面元素', () => {
      render(<InputPageWrapper />);
      
      expect(screen.getByText('Reddit Signal Scanner')).toBeInTheDocument();
      expect(screen.getByText('30秒输入，5分钟分析，发现Reddit上的商业机会')).toBeInTheDocument();
      expect(screen.getByLabelText('描述你的产品或服务')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '开始分析' })).toBeInTheDocument();
    });

    it('应该显示字符计数', () => {
      render(<InputPageWrapper />);
      
      expect(screen.getByText('0/2000 字符')).toBeInTheDocument();
      expect(screen.getByText('最少10字符')).toBeInTheDocument();
    });

    it('应该显示安全提示', () => {
      render(<InputPageWrapper />);
      
      expect(screen.getByText(/我们使用企业级加密保护您的数据安全/)).toBeInTheDocument();
      expect(screen.getByText(/基于Linus Torvalds极简设计哲学构建/)).toBeInTheDocument();
    });
  });

  describe('用户输入交互', () => {
    it('应该更新字符计数', async () => {
      const user = userEvent.setup();
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      await user.type(textarea, '测试输入内容');
      
      expect(screen.getByText('6/2000 字符')).toBeInTheDocument();
    });

    it('应该在字符数接近限制时改变颜色', async () => {
      const user = userEvent.setup();
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      const longText = 'a'.repeat(1600);
      await user.type(textarea, longText);
      
      const counter = screen.getByText('1600/2000 字符');
      expect(counter).toHaveClass('text-yellow-600');
    });

    it('应该在输入为空时禁用提交按钮', () => {
      render(<InputPageWrapper />);
      
      const submitButton = screen.getByRole('button', { name: '开始分析' });
      expect(submitButton).toBeDisabled();
    });

    it('应该在输入长度足够时启用提交按钮', async () => {
      mockValidateProductDescription.mockReturnValue({
        valid: true,
        sanitized: '测试产品描述内容'
      });

      const user = userEvent.setup();
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      await user.type(textarea, '这是一个测试产品描述');
      
      // 等待验证完成
      await waitFor(() => {
        const submitButton = screen.getByRole('button', { name: '开始分析' });
        expect(submitButton).not.toBeDisabled();
      });
    });
  });

  describe('输入验证', () => {
    it('应该显示验证错误', async () => {
      mockValidateProductDescription.mockReturnValue({
        valid: false,
        error: '输入内容包含不安全的代码'
      });

      const user = userEvent.setup();
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      await user.type(textarea, '<script>alert("xss")</script>');
      
      await waitFor(() => {
        expect(screen.getByText('输入内容包含不安全的代码')).toBeInTheDocument();
      });
    });

    it('应该显示验证中状态', async () => {
      const user = userEvent.setup();
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      await user.type(textarea, '正在输入的内容');
      
      // 验证中状态应该短暂显示
      expect(screen.getByText('验证中...')).toBeInTheDocument();
    });
  });

  describe('表单提交', () => {
    it('应该在提交时显示加载状态', async () => {
      mockValidateProductDescription.mockReturnValue({
        valid: true,
        sanitized: '测试产品描述内容'
      });
      
      // Mock成功的API调用
      mockHttpClientPost.mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({
          task_id: 'test-task-123'
        }), 100))
      );

      const user = userEvent.setup();
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      await user.type(textarea, '这是一个测试产品描述');
      
      await waitFor(() => {
        const submitButton = screen.getByRole('button');
        expect(submitButton).not.toBeDisabled();
      });
      
      const submitButton = screen.getByRole('button');
      await user.click(submitButton);
      
      expect(screen.getByText('正在提交...')).toBeInTheDocument();
      expect(submitButton).toBeDisabled();
    });

    it('应该在提交成功后跳转', async () => {
      mockValidateProductDescription.mockReturnValue({
        valid: true,
        sanitized: '测试产品描述内容'
      });
      
      mockHttpClientPost.mockResolvedValue({
        task_id: 'test-task-123'
      });

      const user = userEvent.setup();
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      await user.type(textarea, '这是一个测试产品描述');
      
      await waitFor(() => {
        const submitButton = screen.getByRole('button');
        expect(submitButton).not.toBeDisabled();
      });
      
      const submitButton = screen.getByRole('button');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/analysis/test-task-123');
      }, { timeout: 3000 });
    });

    it('应该处理提交错误', async () => {
      mockValidateProductDescription.mockReturnValue({
        valid: true,
        sanitized: '测试产品描述内容'
      });
      
      mockHttpClientPost.mockRejectedValue(new Error('网络错误'));

      const user = userEvent.setup();
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      await user.type(textarea, '这是一个测试产品描述');
      
      await waitFor(() => {
        const submitButton = screen.getByRole('button');
        expect(submitButton).not.toBeDisabled();
      });
      
      const submitButton = screen.getByRole('button');
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/提交失败/)).toBeInTheDocument();
      });
    });
  });

  describe('响应式设计', () => {
    it('应该适应不同屏幕尺寸', () => {
      render(<InputPageWrapper />);
      
      const container = screen.getByRole('main') || document.querySelector('.min-h-screen');
      expect(container).toHaveClass('min-h-screen');
      
      const form = document.querySelector('.max-w-2xl');
      expect(form).toBeInTheDocument();
    });
  });

  describe('可访问性', () => {
    it('应该有正确的标签关联', () => {
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      expect(textarea).toHaveAttribute('id', 'productDescription');
    });

    it('应该支持键盘导航', () => {
      render(<InputPageWrapper />);
      
      const textarea = screen.getByLabelText('描述你的产品或服务');
      const submitButton = screen.getByRole('button');
      
      expect(textarea).toHaveAttribute('tabindex', '0');
      expect(submitButton).not.toHaveAttribute('tabindex', '-1');
    });

    it('应该提供适当的ARIA属性', () => {
      render(<InputPageWrapper />);
      
      const form = screen.getByRole('form') || document.querySelector('form');
      expect(form).toBeInTheDocument();
    });
  });
});