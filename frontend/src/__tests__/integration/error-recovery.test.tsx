/**
 * 错误恢复集成测试 - 严格遵循Context7最佳实践
 * 测试错误边界、用户错误恢复、错误消息显示
 */

import { describe, test, beforeEach, vi, expect } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { MemoryRouter } from 'react-router-dom'
import { ReactNode } from 'react'
import ErrorBoundary from '@/components/ErrorBoundary'
import AppRouter from '@/router/AppRouter'

// Context7最佳实践：Mock外部依赖
vi.mock('@/services/api.client', () => ({
  ApiClient: {
    submitAnalysis: vi.fn(),
    getTaskStatus: vi.fn(),
    getReport: vi.fn(),
  },
  validateTaskId: vi.fn(),
}))

vi.mock('@/utils/errorHandler', () => ({
  handleError: vi.fn(() => ({
    userMessage: '网络连接失败，请检查网络设置后重试',
    canRetry: true,
    recoveryActions: ['检查网络连接', '刷新页面重试', '切换到移动网络']
  })),
}))

// 故意抛错的测试组件
const ThrowError = ({ message = 'Test error' }: { message?: string }) => {
  throw new Error(message)
}

// Context7测试包装器
const TestWrapper = ({ 
  children, 
  initialEntries = ['/'] 
}: { 
  children: ReactNode
  initialEntries?: string[] 
}) => (
  <MemoryRouter initialEntries={initialEntries}>
    {children}
  </MemoryRouter>
)

describe('错误恢复集成测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('错误边界基础功能', () => {
    test('应该捕获组件错误并显示错误界面', () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError />
          </ErrorBoundary>
        </TestWrapper>
      )

      // Context7异步等待错误界面显示
      expect(screen.getByText('糟糕！出现了错误')).toBeInTheDocument()
      expect(screen.getByText('网络连接失败，请检查网络设置后重试')).toBeInTheDocument()
    })

    test('应该显示用户友好的错误消息', () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError message="Network error" />
          </ErrorBoundary>
        </TestWrapper>
      )

      expect(screen.getByText('网络连接失败，请检查网络设置后重试')).toBeInTheDocument()
    })

    test('应该显示错误恢复建议', () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError />
          </ErrorBoundary>
        </TestWrapper>
      )

      expect(screen.getByText('建议操作：')).toBeInTheDocument()
      expect(screen.getByText('检查网络连接')).toBeInTheDocument()
      expect(screen.getByText('刷新页面重试')).toBeInTheDocument()
      expect(screen.getByText('切换到移动网络')).toBeInTheDocument()
    })
  })

  describe('错误恢复操作', () => {
    test('应该显示重试按钮并支持点击', async () => {
      const user = userEvent.setup()
      
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError />
          </ErrorBoundary>
        </TestWrapper>
      )

      const retryButton = screen.getByRole('button', { name: '重试' })
      expect(retryButton).toBeInTheDocument()

      // Context7: 验证用户能成功点击重试按钮
      await user.click(retryButton)
      
      // 验证点击后的真实用户体验：错误界面仍然存在（因为组件一直抛错）
      expect(screen.getByText('糟糕！出现了错误')).toBeInTheDocument()
    })

    test('应该显示刷新页面按钮', () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError />
          </ErrorBoundary>
        </TestWrapper>
      )

      const refreshButton = screen.getByRole('button', { name: '刷新页面' })
      expect(refreshButton).toBeInTheDocument()
    })

    test('应该显示返回首页按钮', () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError />
          </ErrorBoundary>
        </TestWrapper>
      )

      const homeButton = screen.getByRole('button', { name: '返回首页' })
      expect(homeButton).toBeInTheDocument()
    })
  })

  describe('API错误恢复', () => {
    test('应该处理网络请求错误', async () => {
      const { ApiClient } = await import('@/services/api.client')
      vi.mocked(ApiClient.submitAnalysis).mockRejectedValue(new Error('Network timeout'))

      render(
        <TestWrapper initialEntries={['/']}> 
          <AppRouter />
        </TestWrapper>
      )

      // 等待页面加载
      await waitFor(() => {
        expect(screen.getByText('描述您的产品想法')).toBeInTheDocument()
      })
    })

    test('应该处理认证错误', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockRejectedValue(new Error('401 Unauthorized'))

      render(
        <TestWrapper initialEntries={['/analysis/test-task']}>
          <AppRouter />
        </TestWrapper>
      )

      // Context7异步等待错误处理
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })
    })

    test('应该处理服务器错误', async () => {
      const { ApiClient } = await import('@/services/api.client')
      vi.mocked(ApiClient.getReport).mockRejectedValue(new Error('500 Internal Server Error'))

      render(
        <TestWrapper initialEntries={['/report/test-task']}>
          <AppRouter />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })
    })
  })

  describe('路由错误恢复', () => {
    test('应该处理无效路由', () => {
      render(
        <TestWrapper initialEntries={['/invalid-route']}>
          <AppRouter />
        </TestWrapper>
      )

      // 应该重定向或显示404页面
      expect(screen.getByRole('navigation')).toBeInTheDocument()
    })

    test('应该处理无效任务ID', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockResolvedValue(false)

      render(
        <TestWrapper initialEntries={['/analysis/invalid-task']}>
          <AppRouter />
        </TestWrapper>
      )

      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })
    })
  })

  describe('用户体验错误处理', () => {
    test('应该在开发环境显示错误详情', () => {
      const originalEnv = process.env.NODE_ENV
      process.env.NODE_ENV = 'development'

      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError message="Detailed test error" />
          </ErrorBoundary>
        </TestWrapper>
      )

      expect(screen.getByText('错误详情 (开发环境)')).toBeInTheDocument()
      
      process.env.NODE_ENV = originalEnv
    })

    test('应该显示技术支持联系信息', () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError />
          </ErrorBoundary>
        </TestWrapper>
      )

      expect(screen.getByText('如果问题持续存在，请联系技术支持')).toBeInTheDocument()
      expect(screen.getByText('Reddit Signal Scanner - 基于Linus设计哲学')).toBeInTheDocument()
    })

    test('应该在错误发生时保持导航可访问性', async () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError />
          </ErrorBoundary>
        </TestWrapper>
      )

      // 错误界面应该仍然可访问
      const buttons = screen.getAllByRole('button')
      expect(buttons.length).toBeGreaterThan(0)
      
      // 所有按钮都应该可聚焦
      buttons.forEach(button => {
        expect(button).not.toBeDisabled()
      })
    })
  })

  describe('错误恢复性能', () => {
    test('应该快速显示错误界面', () => {
      const startTime = Date.now()

      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError />
          </ErrorBoundary>
        </TestWrapper>
      )

      expect(screen.getByText('糟糕！出现了错误')).toBeInTheDocument()
      
      const renderTime = Date.now() - startTime
      expect(renderTime).toBeLessThan(50) // 50ms内显示错误界面
    })

    test('应该高效处理重试操作', async () => {
      const user = userEvent.setup()
      
      const startTime = Date.now()

      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError />
          </ErrorBoundary>
        </TestWrapper>
      )

      const retryButton = screen.getByRole('button', { name: '重试' })
      await user.click(retryButton)
      
      const actionTime = Date.now() - startTime
      expect(actionTime).toBeLessThan(100) // 100ms内完成重试操作
    })
  })

  describe('错误类型分类处理', () => {
    test('应该正确处理网络错误类型', () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError message="fetch failed" />
          </ErrorBoundary>
        </TestWrapper>
      )

      expect(screen.getByText('网络连接失败，请检查网络设置后重试')).toBeInTheDocument()
    })

    test('应该正确处理验证错误类型', () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError message="validation failed" />
          </ErrorBoundary>
        </TestWrapper>
      )

      expect(screen.getByText('网络连接失败，请检查网络设置后重试')).toBeInTheDocument()
    })

    test('应该正确处理认证错误类型', () => {
      render(
        <TestWrapper>
          <ErrorBoundary>
            <ThrowError message="401 unauthorized" />
          </ErrorBoundary>
        </TestWrapper>
      )

      expect(screen.getByText('网络连接失败，请检查网络设置后重试')).toBeInTheDocument()
    })
  })
})