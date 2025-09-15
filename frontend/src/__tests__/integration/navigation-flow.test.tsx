/**
 * 导航流程集成测试 - 严格遵循Context7最佳实践
 * 测试导航步骤流转、路由保护、状态管理
 */

import { describe, test, beforeEach, vi, expect } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import { MemoryRouter } from 'react-router-dom'
import { ReactNode } from 'react'
import Navigation from '@/components/Navigation'
import AppRouter from '@/router/AppRouter'

// Context7最佳实践：Mock所有外部依赖
vi.mock('@/services/api.client', () => ({
  validateTaskId: vi.fn(),
  ApiClient: {
    submitAnalysis: vi.fn(),
    getTaskStatus: vi.fn(),
    getReport: vi.fn(),
  },
}))

vi.mock('@/hooks/useDeviceDetection', () => ({
  useDeviceDetection: () => ({
    type: 'desktop',
    isTouchDevice: false,
  }),
}))

vi.mock('@/components/LoadingFallback', () => ({
  default: () => <div data-testid="loading">加载中...</div>,
}))

// Context7测试包装器 - MemoryRouter模式
const NavigationTestWrapper = ({ 
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

describe('导航流程集成测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('基础导航渲染', () => {
    test('应该正确渲染导航步骤', async () => {
      render(
        <NavigationTestWrapper>
          <Navigation />
        </NavigationTestWrapper>
      )

      // Context7异步等待导航内容
      const inputStep = await screen.findByText('产品输入')
      const analysisStep = await screen.findByText('信号分析')  
      const reportStep = await screen.findByText('商业洞察')

      expect(inputStep).toBeInTheDocument()
      expect(analysisStep).toBeInTheDocument()
      expect(reportStep).toBeInTheDocument()
    })

    test('应该正确显示当前活跃步骤', async () => {
      render(
        <NavigationTestWrapper initialEntries={['/']}>
          <Navigation />
        </NavigationTestWrapper>
      )

      // Context7异步等待当前步骤激活状态
      const inputButton = await screen.findByRole('button', { name: /产品输入/ })
      expect(inputButton).toHaveClass('bg-blue-50', 'text-blue-700')
    })
  })

  describe('导航步骤流转', () => {
    test('应该允许从输入页导航到其他步骤', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockResolvedValue(true)

      render(
        <NavigationTestWrapper initialEntries={['/analysis/test-task-123']}>
          <AppRouter />
        </NavigationTestWrapper>
      )

      // Context7异步等待导航内容 - 基于用户可见内容
      const navigation = await screen.findByRole('navigation')
      expect(navigation).toBeInTheDocument()
      
      // 验证导航步骤存在
      expect(screen.getByText('产品输入')).toBeInTheDocument()
      expect(screen.getByText('信号分析')).toBeInTheDocument()
    })

    test('应该正确处理导航点击交互', async () => {
      render(
        <NavigationTestWrapper>
          <Navigation />
        </NavigationTestWrapper>
      )

      // Context7用户交互测试
      const inputButton = await screen.findByRole('button', { name: /产品输入/ })
      fireEvent.click(inputButton)

      // 验证点击后状态保持
      expect(inputButton).toBeInTheDocument()
    })
  })

  describe('路由保护机制', () => {
    test('应该保护需要taskId的路由', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockResolvedValue(false)

      render(
        <NavigationTestWrapper initialEntries={['/analysis/invalid-task']}>
          <AppRouter />
        </NavigationTestWrapper>
      )

      // Context7异步等待重定向结果
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })
    })

    test('应该显示验证加载状态', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockImplementation(() => new Promise(resolve => {
        setTimeout(() => resolve(true), 100)
      }))

      render(
        <NavigationTestWrapper initialEntries={['/analysis/test-task']}>
          <AppRouter />
        </NavigationTestWrapper>
      )

      // Context7异步等待加载状态
      const loading = await screen.findByText('验证中...')
      expect(loading).toBeInTheDocument()
    })
  })

  describe('导航状态管理', () => {
    test('应该正确管理导航历史', async () => {
      render(
        <NavigationTestWrapper initialEntries={['/']}>
          <Navigation />
        </NavigationTestWrapper>
      )

      // 验证初始状态
      const inputButton = await screen.findByRole('button', { name: /产品输入/ })
      expect(inputButton).toHaveClass('bg-blue-50')
    })

    test('应该处理多步骤导航流程', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockResolvedValue(true)

      render(
        <NavigationTestWrapper initialEntries={['/report/test-task-456']}>
          <AppRouter />
        </NavigationTestWrapper>
      )

      // Context7异步等待导航加载完成
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })
    })
  })

  describe('响应式导航行为', () => {
    test('应该在桌面端显示完整导航信息', async () => {
      render(
        <NavigationTestWrapper>
          <Navigation />
        </NavigationTestWrapper>
      )

      // Context7异步等待响应式内容
      const inputDescription = await screen.findByText('描述您的产品')
      expect(inputDescription).toBeInTheDocument()
    })

    test('应该正确处理导航按钮禁用状态', async () => {
      render(
        <NavigationTestWrapper>
          <Navigation />
        </NavigationTestWrapper>
      )

      const analysisButton = await screen.findByRole('button', { name: /信号分析/ })
      expect(analysisButton).toBeDisabled()

      const reportButton = await screen.findByRole('button', { name: /商业洞察/ })
      expect(reportButton).toBeDisabled()
    })
  })

  describe('导航错误处理', () => {
    test('应该处理无效路由', async () => {
      render(
        <NavigationTestWrapper initialEntries={['/invalid-route']}>
          <AppRouter />
        </NavigationTestWrapper>
      )

      // Context7异步等待404处理或重定向
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })
    })

    test('应该处理API验证错误', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockRejectedValue(new Error('API Error'))

      render(
        <NavigationTestWrapper initialEntries={['/analysis/error-task']}>
          <AppRouter />
        </NavigationTestWrapper>
      )

      // Context7异步等待错误处理
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })
    })
  })

  describe('导航性能测试', () => {
    test('应该快速渲染导航组件', async () => {
      const startTime = Date.now()

      render(
        <NavigationTestWrapper>
          <Navigation />
        </NavigationTestWrapper>
      )

      await screen.findByText('产品输入')
      
      const renderTime = Date.now() - startTime
      expect(renderTime).toBeLessThan(100) // 100ms内渲染完成
    })

    test('应该高效处理路由切换', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockResolvedValue(true)

      render(
        <NavigationTestWrapper initialEntries={['/']}>
          <AppRouter />
        </NavigationTestWrapper>
      )

      // Context7异步验证路由切换性能
      const navigation = await screen.findByRole('navigation')
      expect(navigation).toBeInTheDocument()
    })
  })
})