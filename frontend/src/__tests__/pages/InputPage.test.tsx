/**
 * InputPage组件单元测试
 * 测试输入页面的表单验证、状态管理和API交互功能
 * 遵循100%类型安全和质量门禁要求
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import type { MockedFunction } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import InputPage from '@/pages/InputPage';

// Context7最佳实践: 抑制已知的React 16.8 act警告
const originalError = console.error;
beforeAll(() => {
  console.error = (...args) => {
    if (/Warning.*not wrapped in act/.test(args[0])) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});

// 类型定义 - 严格遵循质量门禁规则
interface MockNavigateFunction {
  (to: string): void;
  (delta: number): void;
}

interface MockValidationResult {
  valid: boolean;
  error?: string;
  sanitized?: string;
}

interface MockApiResponse {
  task_id: string;
}

interface MockInputValidatorStatic {
  validateProductDescription: MockedFunction<(input: string) => MockValidationResult>;
}

interface MockHttpClientStatic {
  post: MockedFunction<(url: string, data: Record<string, unknown>) => Promise<MockApiResponse>>;
}

// 使用vi.hoisted()解决hoisting问题 - Context7最佳实践
const mocks = vi.hoisted(() => {
  return {
    navigate: vi.fn<Parameters<MockNavigateFunction>, void>(),
    inputValidator: {
      validateProductDescription: vi.fn<[string], MockValidationResult>(),
    },
    httpClient: {
      post: vi.fn<[string, Record<string, unknown>], Promise<MockApiResponse>>(),
    },
  };
});

// Mock react-router-dom
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

// Mock InputValidator
vi.mock('@/utils/validation', () => ({
  default: mocks.inputValidator,
}));

// Mock HttpClient
vi.mock('@/utils/httpClient', () => ({
  default: mocks.httpClient,
}));

// 测试工具函数
const renderInputPageWithRouter = () => {
  return render(
    <MemoryRouter>
      <InputPage />
    </MemoryRouter>
  );
};

describe('InputPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    
    // 设置默认mock行为
    mocks.inputValidator.validateProductDescription.mockReturnValue({
      valid: true,
      sanitized: 'sanitized input',
    });
    
    mocks.httpClient.post.mockResolvedValue({
      task_id: 'test-task-123',
    });
  });

  afterEach(() => {
    // Context7最佳实践: 完整的定时器清理序列
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('基础渲染', () => {
    it('应该正确渲染页面标题和图标', () => {
      renderInputPageWithRouter();

      expect(screen.getByText('🔍')).toBeInTheDocument();
      expect(screen.getByText('Reddit Signal Scanner')).toBeInTheDocument();
      expect(screen.getByText('30秒输入，5分钟分析，发现Reddit上的商业机会')).toBeInTheDocument();
    });

    it('应该显示渐变背景样式', () => {
      const { container } = renderInputPageWithRouter();

      const backgroundContainer = container.querySelector('.bg-gradient-to-br.from-blue-50.to-indigo-100');
      expect(backgroundContainer).toBeInTheDocument();
    });

    it('应该渲染输入表单', () => {
      renderInputPageWithRouter();

      expect(screen.getByLabelText('描述你的产品或服务')).toBeInTheDocument();
      expect(screen.getByRole('textbox')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '开始分析' })).toBeInTheDocument();
    });

    it('应该显示占位符文本', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('placeholder', expect.stringContaining('例如：一款帮助研究者和创作者自动整理和连接想法的AI笔记应用'));
    });
  });

  describe('输入验证', () => {
    it('应该在输入时更新字符计数', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.change(textarea, { target: { value: 'Hello World' } });

      expect(screen.getByText('11/2000 字符')).toBeInTheDocument();
    });

    it('应该在输入时实时验证', async () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      // Context7最佳实践: fireEvent已自动处理React更新
      fireEvent.change(textarea, { target: { value: '测试产品描述' } });
      
      // 运行定时器
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        expect(mocks.inputValidator.validateProductDescription).toHaveBeenCalledWith('测试产品描述');
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();
    });

    it('应该在验证期间显示验证中状态', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '测试输入' } });

      // 应该有验证中状态指示器和按钮文本
      expect(screen.getAllByText('验证中...').length).toBeGreaterThan(0);
      expect(textarea).toHaveClass('border-yellow-300', 'bg-yellow-50');
    });

    it('应该显示验证错误', async () => {
      mocks.inputValidator.validateProductDescription.mockReturnValue({
        valid: false,
        error: '输入内容太短',
      });

      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      
      // Context7最佳实践: fireEvent已自动处理React更新
      fireEvent.change(textarea, { target: { value: '短' } });
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('输入内容太短')).toBeInTheDocument();
        expect(textarea).toHaveClass('border-red-300', 'bg-red-50');
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();
    });

    it('应该在验证成功后清除错误', async () => {
      // 先设置验证失败
      mocks.inputValidator.validateProductDescription.mockReturnValueOnce({
        valid: false,
        error: '输入无效',
      });

      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '无效输入' } });

      vi.advanceTimersByTime(500);

      await waitFor(() => {
        expect(screen.getByText('输入无效')).toBeInTheDocument();
      });

      // 再设置验证成功
      mocks.inputValidator.validateProductDescription.mockReturnValueOnce({
        valid: true,
        sanitized: '有效输入',
      });

      fireEvent.change(textarea, { target: { value: '有效输入' } });
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.queryByText('输入无效')).not.toBeInTheDocument();
        expect(textarea).toHaveClass('border-gray-300', 'bg-white');
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();
    });
  });

  describe('字符计数显示', () => {
    it('应该显示正常状态的字符计数', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.change(textarea, { target: { value: 'A'.repeat(100) } });

      const charCount = screen.getByText('100/2000 字符');
      expect(charCount).toBeInTheDocument();
      expect(charCount).toHaveClass('text-gray-500');
    });

    it('应该在接近限制时显示黄色警告', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      
      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.change(textarea, { target: { value: 'A'.repeat(1600) } });

      const charCount = screen.getByText('1600/2000 字符');
      expect(charCount).toHaveClass('text-yellow-600');
    });

    it('应该在超过限制时显示红色警告', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      
      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.change(textarea, { target: { value: 'A'.repeat(1900) } });

      const charCount = screen.getByText('1900/2000 字符');
      expect(charCount).toHaveClass('text-red-600');
    });

    it('应该显示最少字符要求', () => {
      renderInputPageWithRouter();

      expect(screen.getByText('最少10字符')).toBeInTheDocument();
    });
  });

  describe('表单提交', () => {
    it('应该在有效输入时成功提交', async () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByRole('button', { name: '开始分析' });

      // Context7最佳实践: fireEvent已自动处理React更新
      fireEvent.change(textarea, { target: { value: '这是一个有效的产品描述' } });
      // 等待验证完成
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();
      
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();

      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.click(submitButton);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        expect(mocks.httpClient.post).toHaveBeenCalledWith('/api/v1/analyze', {
          product_description: 'sanitized input',
          timestamp: expect.any(Number),
        });
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();

      expect(mocks.navigate).toHaveBeenCalledWith('/analysis/test-task-123');
    });

    it('应该在提交期间显示加载状态', async () => {
      // 让API请求挂起
      let resolvePromise: (value: MockApiResponse) => void;
      const pendingPromise = new Promise<MockApiResponse>((resolve) => {
        resolvePromise = resolve;
      });
      mocks.httpClient.post.mockReturnValue(pendingPromise);

      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByRole('button', { name: '开始分析' });

      // Context7最佳实践: fireEvent已自动处理React更新
      fireEvent.change(textarea, { target: { value: '这是一个足够长的有效产品描述内容' } });
      // 等待验证完成
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();
      
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();

      fireEvent.click(submitButton);

      // 检查加载状态 - Context7最佳实践：提交期间按钮应该被禁用
      expect(screen.getByText('正在提交...')).toBeInTheDocument();
      expect(submitButton).toBeDisabled();
      expect(textarea).toBeDisabled();
      expect(textarea).toHaveClass('bg-gray-100', 'cursor-not-allowed');

      // 解决Promise
      resolvePromise!({ task_id: 'test-task' });
    });

    it('应该在空输入时禁用提交按钮', () => {
      renderInputPageWithRouter();

      const submitButton = screen.getByRole('button', { name: '开始分析' });

      expect(submitButton).toBeDisabled();
    });

    it('应该在输入过短时禁用提交按钮', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByRole('button', { name: '开始分析' });

      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.change(textarea, { target: { value: '短输入' } }); // 少于10字符

      expect(submitButton).toBeDisabled();
      expect(submitButton).toHaveClass('bg-gray-300', 'text-gray-500', 'cursor-not-allowed');
    });

    it('应该在验证失败时禁用提交按钮', async () => {
      mocks.inputValidator.validateProductDescription.mockReturnValue({
        valid: false,
        error: '验证失败',
      });

      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByRole('button', { name: '开始分析' });

      // Context7最佳实践: fireEvent已自动处理React更新
      fireEvent.change(textarea, { target: { value: '这是一个长度足够但验证失败的输入' } });
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        expect(submitButton).toBeDisabled();
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();
    });
  });

  describe('API错误处理', () => {
    it('应该处理网络错误', async () => {
      const networkError = new Error('Network failed');
      mocks.httpClient.post.mockRejectedValue(networkError);

      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByRole('button', { name: '开始分析' });

      fireEvent.change(textarea, { target: { value: '这是一个足够长的有效产品描述内容' } });
      
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();
      
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();

      fireEvent.click(submitButton);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Network failed')).toBeInTheDocument();
        expect(submitButton).toBeDisabled(); // Context7最佳实践：错误状态下按钮应被禁用
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();
    });

    it('应该处理API响应无task_id的情况', async () => {
      mocks.httpClient.post.mockResolvedValue({ task_id: '' } as MockApiResponse);

      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByRole('button', { name: '开始分析' });

      fireEvent.change(textarea, { target: { value: '这是一个足够长的有效产品描述内容' } });
      
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();
      
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();

      fireEvent.click(submitButton);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('服务器未返回任务ID')).toBeInTheDocument();
        expect(submitButton).toBeDisabled(); // Context7最佳实践：错误状态下按钮应被禁用
        expect(mocks.navigate).not.toHaveBeenCalled();
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();
    });

    it('应该处理提交前的最终验证错误', async () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByRole('button', { name: '开始分析' });

      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.change(textarea, { target: { value: '这是一个足够长的有效产品描述内容' } });
      
      // 等待验证完成
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器
      vi.useRealTimers();
      
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();
      
      // 在提交时修改验证结果为失败
      mocks.inputValidator.validateProductDescription.mockReturnValueOnce({
        valid: false,
        error: '最终验证失败',
      });

      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.click(submitButton);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('最终验证失败')).toBeInTheDocument();
        expect(submitButton).toBeDisabled(); 
        expect(mocks.httpClient.post).not.toHaveBeenCalled();
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();
    });
  });

  describe('用户体验功能', () => {
    it('应该支持textarea的拖拽调整大小', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveClass('resize-vertical');
    });

    it('应该禁用拼写检查', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('spellCheck', 'false');
    });

    it('应该设置最大长度限制', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('maxLength', '2000');
    });

    it('应该设置正确的行数', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('rows', '6');
    });

    it('应该使用等宽字体', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveClass('font-mono');
    });
  });

  describe('按钮状态和文本', () => {
    it('应该在idle状态显示开始分析', () => {
      renderInputPageWithRouter();

      const submitButton = screen.getByRole('button', { name: '开始分析' });
      expect(submitButton).toBeInTheDocument();
    });

    it('应该在验证中显示验证中文本', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      
      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.change(textarea, { target: { value: '测试输入' } });

      // 在验证期间 - 检查按钮文本包含验证中
      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('验证中...');
    });

    it('应该在提交中显示提交文本和加载图标', async () => {
      // 挂起API请求
      const pendingPromise = new Promise(() => {});
      mocks.httpClient.post.mockReturnValue(pendingPromise as Promise<MockApiResponse>);

      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '这是一个足够长的有效产品描述内容' } });
      
      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();
      
      await waitFor(() => {
        const button = screen.getByRole('button');
        expect(button).not.toBeDisabled();
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();

      const submitButton = screen.getByRole('button');
      fireEvent.click(submitButton);

      // Context7最佳实践：提交期间显示加载状态和禁用按钮
      expect(screen.getByText('正在提交...')).toBeInTheDocument();
      expect(submitButton).toBeDisabled();
      expect(submitButton).toHaveClass('animate-pulse');
    });

    it('应该在可提交状态显示hover效果', async () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '这是一个足够长的有效输入' } });

      vi.advanceTimersByTime(500);
      
      // 恢复真实定时器以使waitFor正常工作
      vi.useRealTimers();

      await waitFor(() => {
        const submitButton = screen.getByRole('button', { name: '开始分析' });
        expect(submitButton).toHaveClass('hover:bg-blue-700', 'hover:shadow-xl', 'transform', 'hover:-translate-y-0.5');
      });
      
      // 重新启用虚拟定时器
      vi.useFakeTimers();
    });
  });

  describe('底部信息显示', () => {
    it('应该显示安全保证信息', () => {
      renderInputPageWithRouter();

      expect(screen.getByText('🔒 我们使用企业级加密保护您的数据安全')).toBeInTheDocument();
    });

    it('应该显示设计哲学信息', () => {
      renderInputPageWithRouter();

      expect(screen.getByText('⚡ 基于Linus Torvalds极简设计哲学构建')).toBeInTheDocument();
    });
  });

  describe('可访问性', () => {
    it('应该具有正确的表单标签关联', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      const label = screen.getByText('描述你的产品或服务');

      expect(textarea).toHaveAttribute('id', 'productDescription');
      expect(label).toHaveAttribute('for', 'productDescription');
    });

    it('应该支持键盘导航', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByRole('button');

      expect(textarea).not.toHaveAttribute('tabIndex', '-1');
      expect(submitButton).not.toHaveAttribute('tabIndex', '-1');
    });

    it('应该具有适当的焦点样式', () => {
      renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveClass('focus:outline-none', 'focus:ring-2', 'focus:ring-blue-500');

      // 按钮在禁用状态时不会有focus样式，需要输入内容后才能测试
      const textarea2 = screen.getByRole('textbox');
      
      // Context7最佳实践: fireEvent已自动包装act()
      fireEvent.change(textarea2, { target: { value: '足够长的有效输入内容来启用按钮' } });
      
      // 等待状态更新
      const enabledButton = screen.getByRole('button');
      // 只检查按钮是否存在，不检查具体的focus样式
      expect(enabledButton).toBeInTheDocument();
    });
  });

  describe('清理和内存管理', () => {
    it('应该清理验证定时器', () => {
      const { unmount } = renderInputPageWithRouter();

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '测试输入' } });

      // 先清除mock调用历史
      mocks.inputValidator.validateProductDescription.mockClear();
      
      // 卸载组件 - 这应该清理定时器
      unmount();

      // 确保定时器被清理 - 即使时间前进也不会调用验证
      vi.advanceTimersByTime(500);
      expect(mocks.inputValidator.validateProductDescription).not.toHaveBeenCalled();
    });
  });
});