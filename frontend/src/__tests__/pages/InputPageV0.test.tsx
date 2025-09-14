/**
 * InputPageV0组件单元测试
 * 测试v0风格输入页面的响应式设计、示例交互和API集成功能
 * 遵循100%类型安全和质量门禁要求
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import type { MockedFunction } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import InputPageV0 from '@/pages/InputPageV0';

// 类型定义 - 严格遵循质量门禁规则
interface MockNavigateFunction {
  (to: string): void;
  (delta: number): void;
}

interface MockDeviceInfo {
  type: 'mobile' | 'tablet' | 'desktop';
  isTouchDevice: boolean;
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

interface MockConfigService {
  getAnalyzeEndpoint: MockedFunction<() => string>;
  isUsingMock: MockedFunction<() => boolean>;
}

interface MockSwipeConfig {
  threshold: number;
  preventScroll: boolean;
}

interface MockSwipeHandlers {
  onSwipeLeft: () => void;
  config: MockSwipeConfig;
}

interface MockResponsiveLayoutProps {
  children: React.ReactNode;
  variant?: 'compact' | 'comfortable' | 'spacious';
  className?: string;
  ref?: React.Ref<HTMLDivElement>;
}

interface MockResponsiveButtonProps {
  children: React.ReactNode;
  type?: 'button' | 'submit' | 'reset';
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'sm' | 'md' | 'lg';
  fullWidth?: boolean;
  loading?: boolean;
  disabled?: boolean;
  icon?: React.ReactNode;
  onClick?: () => void;
}

// Mock hooks and services using vi.hoisted() to solve hoisting issues
const mocks = vi.hoisted(() => {
  return {
    navigate: vi.fn<Parameters<MockNavigateFunction>, void>(),
    useDeviceDetection: vi.fn<[], MockDeviceInfo>(),
    useSwipeGesture: vi.fn<[React.RefObject<HTMLElement>, MockSwipeHandlers], void>(),
    inputValidator: {
      validateProductDescription: vi.fn(),
    } as MockInputValidatorStatic,
    httpClient: {
      post: vi.fn(),
    } as MockHttpClientStatic,
    configService: {
      getAnalyzeEndpoint: vi.fn().mockReturnValue('/api/v1/analyze'),
      isUsingMock: vi.fn().mockReturnValue(false),
    } as MockConfigService,
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

// Mock useDeviceDetection
vi.mock('@/hooks/useDeviceDetection', () => ({
  useDeviceDetection: mocks.useDeviceDetection,
}));

// Mock useSwipeGesture
vi.mock('@/hooks/useSwipeGesture', () => ({
  useSwipeGesture: mocks.useSwipeGesture,
}));

// Mock InputValidator
vi.mock('@/utils/validation', () => ({
  default: mocks.inputValidator,
}));

// Mock HttpClient
vi.mock('@/utils/httpClient', () => ({
  default: mocks.httpClient,
}));

// Mock configService
vi.mock('@/services/config.service', () => ({
  default: mocks.configService,
}));

// Mock ResponsiveLayout
vi.mock('@/components/ResponsiveLayout', () => ({
  default: React.forwardRef<HTMLDivElement, MockResponsiveLayoutProps>(
    ({ children, variant, className }, ref) => (
      <div 
        ref={ref} 
        data-testid="responsive-layout" 
        data-variant={variant}
        className={className}
      >
        {children}
      </div>
    )
  ),
}));

// Mock ResponsiveButton
vi.mock('@/components/ResponsiveButton', () => ({
  default: React.forwardRef<HTMLButtonElement, MockResponsiveButtonProps>(
    ({ children, type = 'button', variant, size, fullWidth, loading, disabled, icon, ...props }, ref) => (
      <button
        ref={ref}
        type={type}
        data-testid="responsive-button"
        data-variant={variant}
        data-size={size}
        data-full-width={fullWidth}
        data-loading={loading}
        disabled={disabled}
        {...props}
      >
        {icon && <span data-testid="button-icon">{icon}</span>}
        {loading ? '加载中...' : children}
      </button>
    )
  ),
}));

// Mock Lucide React icons
vi.mock('lucide-react', () => ({
  Zap: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="zap-icon" className={className} {...props} />
  ),
  LightbulbIcon: ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
    <svg data-testid="lightbulb-icon" className={className} {...props} />
  ),
}));

// 测试工具函数
const renderInputPageV0WithRouter = () => {
  return render(
    <MemoryRouter>
      <InputPageV0 />
    </MemoryRouter>
  );
};

describe('InputPageV0', () => {
  // 默认mock返回值
  const defaultDeviceInfo: MockDeviceInfo = {
    type: 'desktop',
    isTouchDevice: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    
    // 设置默认的device detection
    mocks.useDeviceDetection.mockReturnValue(defaultDeviceInfo);
    
    // 设置默认的validation
    mocks.inputValidator.validateProductDescription.mockReturnValue({
      valid: true,
      sanitized: 'sanitized input',
    });
    
    // 设置默认的API响应
    mocks.httpClient.post.mockResolvedValue({
      task_id: 'test-task-123',
    });
    
    // 设置默认的config service  
    mocks.configService.getAnalyzeEndpoint.mockReturnValue('/api/v1/analyze');
    mocks.configService.isUsingMock.mockReturnValue(false);
  });

  describe('基础渲染', () => {
    it('应该正确渲染页面标题和图标', () => {
      renderInputPageV0WithRouter();

      expect(screen.getByTestId('lightbulb-icon')).toBeInTheDocument();
      expect(screen.getByText('描述您的产品想法')).toBeInTheDocument();
      expect(screen.getByText('详细告诉我们您的产品或服务。您描述得越具体，我们能提供的洞察就越好。')).toBeInTheDocument();
    });

    it('应该使用ResponsiveLayout组件', () => {
      renderInputPageV0WithRouter();

      expect(screen.getByTestId('responsive-layout')).toBeInTheDocument();
    });

    it('应该显示产品描述表单', () => {
      renderInputPageV0WithRouter();

      expect(screen.getByText('产品描述')).toBeInTheDocument();
      expect(screen.getByRole('textbox')).toBeInTheDocument();
      expect(screen.getByText('包括您的目标受众、核心功能以及您要解决的问题')).toBeInTheDocument();
    });

    it('应该显示字符计数器', () => {
      renderInputPageV0WithRouter();

      expect(screen.getByText('0 字')).toBeInTheDocument();
    });
  });

  describe('响应式设计', () => {
    it('应该在移动端使用compact变体', () => {
      mocks.useDeviceDetection.mockReturnValue({
        type: 'mobile',
        isTouchDevice: true,
      });

      renderInputPageV0WithRouter();

      const layout = screen.getByTestId('responsive-layout');
      expect(layout).toHaveAttribute('data-variant', 'compact');
    });

    it('应该在桌面端使用comfortable变体', () => {
      mocks.useDeviceDetection.mockReturnValue({
        type: 'desktop',
        isTouchDevice: false,
      });

      renderInputPageV0WithRouter();

      const layout = screen.getByTestId('responsive-layout');
      expect(layout).toHaveAttribute('data-variant', 'comfortable');
    });

    it('应该在触摸设备上禁用textarea调整大小', () => {
      mocks.useDeviceDetection.mockReturnValue({
        type: 'mobile',
        isTouchDevice: true,
      });

      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveClass('resize-none');
    });

    it('应该在非触摸设备上启用垂直调整大小', () => {
      mocks.useDeviceDetection.mockReturnValue({
        type: 'desktop',
        isTouchDevice: false,
      });

      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveClass('resize-y');
    });

    it('应该在触摸设备上设置16px字体大小防止缩放', () => {
      mocks.useDeviceDetection.mockReturnValue({
        type: 'mobile',
        isTouchDevice: true,
      });

      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveStyle({ fontSize: '16px' });
    });
  });

  describe('输入验证和处理', () => {
    it('应该在输入时更新字符计数', () => {
      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'Test input' } });

      expect(screen.getByText('10 字')).toBeInTheDocument();
    });

    it('应该在输入时验证长度', () => {
      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '这是一个有效的产品描述输入' } });

      // 字符计数应该显示绿色（有效状态）
      const charCounter = screen.getByText('13 字');
      expect(charCounter.closest('div')).toHaveClass('bg-green-100', 'text-green-700');
    });

    it('应该在输入过短时显示提示', () => {
      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '短' } });

      expect(screen.getByText(/还需要至少/)).toBeInTheDocument();
    });

    it('应该在输入过长时显示警告', () => {
      renderInputPageV0WithRouter();

      const longText = 'A'.repeat(2100);
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: longText } });

      expect(screen.getByText(/超出.*个字/)).toBeInTheDocument();
      
      // 字符计数应该显示红色（错误状态）
      const charCounter = screen.getByText('2100 字');
      expect(charCounter.closest('div')).toHaveClass('bg-red-100', 'text-red-700');
    });

    it('应该在输入有效时显示成功提示', () => {
      renderInputPageV0WithRouter();

      const validText = '这是一个有效长度的产品描述';
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: validText } });

      expect(screen.getByText('字数适合分析')).toBeInTheDocument();
    });

    it('应该在输入变化时清除错误', async () => {
      renderInputPageV0WithRouter();

      // 先设置一个错误状态
      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: '' } });
      
      const submitButton = screen.getByTestId('submit-button');
      fireEvent.click(submitButton);

      // 等待错误信息出现
      await waitFor(() => {
        expect(screen.getByText('请输入有效的产品描述（10-2000字符）')).toBeInTheDocument();
      });

      // 然后输入有效文本，错误应该被清除
      fireEvent.change(textarea, { target: { value: '这是一个有效的输入' } });

      expect(screen.queryByText('请输入有效的产品描述（10-2000字符）')).not.toBeInTheDocument();
    });
  });

  describe('示例功能', () => {
    it('应该显示产品示例', () => {
      renderInputPageV0WithRouter();

      expect(screen.getByText('需要灵感？试试这些示例：')).toBeInTheDocument();
      expect(screen.getByText('SaaS工具')).toBeInTheDocument();
      expect(screen.getByText('移动应用')).toBeInTheDocument();
      expect(screen.getByText('电商平台')).toBeInTheDocument();
    });

    it('应该在点击示例时填充输入框', () => {
      renderInputPageV0WithRouter();

      const exampleCard = screen.getByText('SaaS工具').closest('div');
      fireEvent.click(exampleCard!);

      const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
      expect(textarea.value).toContain('一个面向远程团队的项目管理工具');
    });

    it('应该在点击示例后更新字符计数和验证状态', () => {
      renderInputPageV0WithRouter();

      const exampleCard = screen.getByText('移动应用').closest('div');
      fireEvent.click(exampleCard!);

      // 应该显示字符数 - Context7最佳实践：使用getAllByText处理多个匹配元素
      const charCountElements = screen.getAllByText(/\d+ 字/);
      expect(charCountElements[0]).toBeInTheDocument();
      
      // 应该是有效状态（绿色） - 使用更具体的选择器
      const charCounterElements = screen.getAllByText(/\d+ 字/);
      const charCounter = charCounterElements[0]; // 选择第一个字符计数器元素
      expect(charCounter.closest('div')).toHaveClass('bg-green-100', 'text-green-700');
    });

    it('应该根据设备类型调整示例网格布局', () => {
      // 移动端应该是单列
      mocks.useDeviceDetection.mockReturnValue({
        type: 'mobile',
        isTouchDevice: true,
      });

      const { rerender } = renderInputPageV0WithRouter();

      let grid = document.querySelector('.grid');
      expect(grid).toHaveClass('grid-cols-1');

      // 平板端应该是双列
      mocks.useDeviceDetection.mockReturnValue({
        type: 'tablet',
        isTouchDevice: true,
      });

      rerender(
        <MemoryRouter>
          <InputPageV0 />
        </MemoryRouter>
      );

      grid = document.querySelector('.grid');
      expect(grid).toHaveClass('grid-cols-2');

      // 桌面端应该是三列
      mocks.useDeviceDetection.mockReturnValue({
        type: 'desktop',
        isTouchDevice: false,
      });

      rerender(
        <MemoryRouter>
          <InputPageV0 />
        </MemoryRouter>
      );

      grid = document.querySelector('.grid');
      expect(grid).toHaveClass('grid-cols-3');
    });
  });

  describe('表单提交', () => {
    it('应该在有效输入时成功提交', async () => {
      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(textarea, { target: { value: '这是一个有效的产品描述' } });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mocks.inputValidator.validateProductDescription).toHaveBeenCalledWith('这是一个有效的产品描述');
        expect(mocks.httpClient.post).toHaveBeenCalledWith('/api/v1/analyze', {
          description: 'sanitized input',
          urgent: false,
        });
        expect(mocks.navigate).toHaveBeenCalledWith('/analysis/test-task-123');
      });
    });


    it('应该在无效输入时显示错误', async () => {
      renderInputPageV0WithRouter();

      const submitButton = screen.getByTestId('submit-button');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText('请输入有效的产品描述（10-2000字符）')).toBeInTheDocument();
      });
    });

    it('应该处理验证失败', async () => {
      // Context7最佳实践：确保mock在组件提交时返回错误
      mocks.inputValidator.validateProductDescription.mockReturnValue({
        valid: false,
        error: '输入包含无效字符',
      });

      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(textarea, { target: { value: '这是一个有效长度但无效内容的测试输入' } });
      fireEvent.click(submitButton);

      // Context7模式：等待错误警告出现
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(/输入包含无效字符/i);
      expect(mocks.httpClient.post).not.toHaveBeenCalled();
    });

    it('应该处理API错误', async () => {
      // Context7最佳实践：使用mockRejectedValue模拟API错误
      mocks.httpClient.post.mockRejectedValue(new Error('网络错误'));

      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(textarea, { target: { value: '这是一个有效长度的产品描述测试输入用于API错误测试' } });
      fireEvent.click(submitButton);

      // Context7模式：等待错误警告出现
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(/网络错误/i);
    });

    it('应该处理空任务ID响应', async () => {
      // Context7最佳实践：使用mockResolvedValue模拟空任务ID
      mocks.httpClient.post.mockResolvedValue({ task_id: '' });

      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(textarea, { target: { value: '这是一个有效长度的产品描述测试输入用于空任务ID测试' } });
      fireEvent.click(submitButton);

      // Context7模式：等待错误警告出现
      const alert = await screen.findByRole('alert');
      expect(alert).toHaveTextContent(/服务器未返回任务ID/i);
    });
  });

  describe('配置服务集成', () => {
    it('应该使用配置服务获取API端点', async () => {
      const customEndpoint = '/api/v2/custom-analyze';
      // Context7最佳实践：确保mock在组件调用前被正确设置
      mocks.configService.getAnalyzeEndpoint.mockReturnValue(customEndpoint);
      mocks.httpClient.post.mockResolvedValue({ task_id: 'test-task-123' });

      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(textarea, { target: { value: '这是一个有效长度的产品描述测试输入用于配置服务测试' } });
      fireEvent.click(submitButton);

      // Context7模式：直接断言异步调用
      expect(mocks.configService.getAnalyzeEndpoint).toHaveBeenCalled();
      expect(mocks.httpClient.post).toHaveBeenCalledWith(customEndpoint, expect.any(Object));
    });

    it('应该在开发模式下记录API模式', async () => {
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
      
      // Context7最佳实践：设置开发环境和mock配置
      const originalEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = 'development';

      mocks.configService.isUsingMock.mockReturnValue(true);
      mocks.configService.getAnalyzeEndpoint.mockReturnValue('/api/v1/analyze');
      mocks.httpClient.post.mockResolvedValue({ task_id: 'test-task-123' });

      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      const submitButton = screen.getByTestId('submit-button');

      fireEvent.change(textarea, { target: { value: '这是一个有效长度的产品描述测试输入用于API模式记录测试' } });
      fireEvent.click(submitButton);

      // Context7模式：等待异步操作完成后断言console调用
      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith('Using Mock API: /api/v1/analyze');
      });

      // 恢复环境
      process.env.NODE_ENV = originalEnv;
      consoleSpy.mockRestore();
    });
  });

  describe('响应式按钮配置', () => {
    it('应该在移动端使用大尺寸全宽按钮', () => {
      mocks.useDeviceDetection.mockReturnValue({
        type: 'mobile',
        isTouchDevice: true,
      });

      renderInputPageV0WithRouter();

      const submitButton = screen.getByTestId('submit-button');
      expect(submitButton).toHaveAttribute('data-size', 'lg');
      expect(submitButton).toHaveAttribute('data-full-width', 'true');
    });

    it('应该在桌面端使用中等尺寸非全宽按钮', () => {
      mocks.useDeviceDetection.mockReturnValue({
        type: 'desktop',
        isTouchDevice: false,
      });

      renderInputPageV0WithRouter();

      const submitButton = screen.getByTestId('submit-button');
      expect(submitButton).toHaveAttribute('data-size', 'md');
      expect(submitButton).toHaveAttribute('data-full-width', 'false');
    });

    it('应该显示按钮图标', () => {
      renderInputPageV0WithRouter();

      expect(screen.getByTestId('button-icon')).toBeInTheDocument();
      expect(screen.getByTestId('zap-icon')).toBeInTheDocument();
    });

    it('应该在输入无效时仍保持按钮可点击', () => {
      renderInputPageV0WithRouter();

      const submitButton = screen.getByTestId('submit-button');
      expect(submitButton).not.toBeDisabled();
    });
  });

  describe('滑动手势支持', () => {
    it('应该初始化滑动手势处理', () => {
      renderInputPageV0WithRouter();

      expect(mocks.useSwipeGesture).toHaveBeenCalledWith(
        expect.any(Object), // ref
        expect.objectContaining({
          onSwipeLeft: expect.any(Function),
          config: {
            threshold: 100,
            preventScroll: false,
          },
        })
      );
    });

    it('应该处理向左滑动事件', () => {
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
      
      renderInputPageV0WithRouter();

      // 获取传递给useSwipeGesture的处理函数
      const swipeHandler = mocks.useSwipeGesture.mock.calls[0][1];
      swipeHandler.onSwipeLeft();

      expect(consoleSpy).toHaveBeenCalledWith('Swipe left detected');
      
      consoleSpy.mockRestore();
    });
  });

  describe('流程时间轴', () => {
    it('应该显示分析流程说明', () => {
      renderInputPageV0WithRouter();

      expect(screen.getByText('接下来会发生什么？')).toBeInTheDocument();
      expect(screen.getByText('步骤 1：分析')).toBeInTheDocument();
      expect(screen.getByText('步骤 2：处理')).toBeInTheDocument();
      expect(screen.getByText('步骤 3：洞察')).toBeInTheDocument();
    });

    it('应该显示每个步骤的详细描述', () => {
      renderInputPageV0WithRouter();

      expect(screen.getByText('我们扫描相关的 Reddit 社区，寻找关于您市场的讨论')).toBeInTheDocument();
      expect(screen.getByText('AI 分析用户痛点、竞品提及和市场机会')).toBeInTheDocument();
      expect(screen.getByText('获得包含可操作商业洞察的综合报告')).toBeInTheDocument();
    });

    it('应该根据设备类型调整时间轴布局', () => {
      // 移动端测试
      mocks.useDeviceDetection.mockReturnValue({
        type: 'mobile',
        isTouchDevice: true,
      });

      const { container } = renderInputPageV0WithRouter();
      const timelineGrid = container.querySelector('.grid.grid-cols-1');
      expect(timelineGrid).toBeInTheDocument();
    });
  });

  describe('表单属性和可访问性', () => {
    it('应该设置正确的textarea属性', () => {
      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('id', 'product-description');
      expect(textarea).toHaveAttribute('autoComplete', 'off');
      expect(textarea).toHaveAttribute('autoCorrect', 'off');
      expect(textarea).toHaveAttribute('spellCheck', 'false');
      expect(textarea).toHaveAttribute('maxLength', '2100');
    });

    it('应该有适当的占位符文本', () => {
      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveAttribute('placeholder', expect.stringContaining('示例：一个帮助忙碌专业人士'));
    });

    it('应该有正确的焦点样式', () => {
      renderInputPageV0WithRouter();

      const textarea = screen.getByRole('textbox');
      expect(textarea).toHaveClass('focus:outline-none', 'focus:ring-2', 'focus:ring-blue-500');
    });
  });
});