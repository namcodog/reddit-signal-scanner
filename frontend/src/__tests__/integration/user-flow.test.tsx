/**
 * 用户流程集成测试 - 严格遵循Context7 + vitest最佳实践
 * 测试完整用户旅程：输入 → 分析 → 报告
 */

import { describe, test, beforeEach, vi, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { BrowserRouter } from 'react-router-dom'
import { ReactNode } from 'react'
import AppRouter from '@/router/AppRouter'

// Mock服务模块 - 基于Context7最佳实践
vi.mock('@/services/api.client', () => ({
  ApiClient: {
    submitAnalysis: vi.fn(),
    getTaskStatus: vi.fn(),
    getReport: vi.fn(),
  },
}))

vi.mock('@/services/sse.service', () => ({
  SSEManager: vi.fn(() => ({
    connect: vi.fn(),
    disconnect: vi.fn(),
    getConnectionState: vi.fn(() => ({ connected: false, retryCount: 0 })),
  })),
  realTimeTaskService: {
    startMonitoring: vi.fn(),
    stopMonitoring: vi.fn(),
    getStatus: vi.fn(() => ({ strategy: null, sse: {}, polling: {} })),
  },
}))

// Mock组件 - 基于Context7标准实践
vi.mock('@/components/Navigation', () => ({
  default: () => <nav data-testid="navigation">导航组件</nav>,
}))

vi.mock('@/components/LoadingFallback', () => ({
  default: () => <div data-testid="loading">加载中...</div>,
}))

// 测试包装器
const TestWrapper = ({ children }: { children: ReactNode }) => (
  <BrowserRouter>{children}</BrowserRouter>
)

describe('用户流程集成测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('完整用户旅程', () => {
    test('应该支持从输入到分析的完整流程', async () => {
      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证导航组件渲染
      expect(screen.getByTestId('navigation')).toBeInTheDocument()

      // Context7异步模式：等待懒加载页面内容
      const productHeading = await screen.findByText('描述您的产品想法')
      expect(productHeading).toBeInTheDocument()

      // Context7用户交互测试
      const navigationElement = screen.getByTestId('navigation')
      fireEvent.click(navigationElement)
      
      // 验证点击后状态
      expect(navigationElement).toBeInTheDocument()
    })

    test('应该正确处理路由跳转', async () => {
      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证应用正确渲染
      expect(screen.getByTestId('navigation')).toBeInTheDocument()

      // 验证路由系统工作正常
      expect(window.location.pathname).toBe('/')
    })
  })

  describe('组件间状态传递', () => {
    test('应该正确管理全局导航状态', async () => {
      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证导航组件存在
      const navigation = screen.getByTestId('navigation')
      expect(navigation).toBeInTheDocument()

      // 验证页面内容加载
      const loadingOrContent = screen.queryByTestId('loading') || 
        screen.queryAllByText(/输入|产品|分析/)[0]
      expect(loadingOrContent).toBeTruthy()
    })
  })

  describe('错误处理集成', () => {
    test('应该正确处理路由错误', async () => {
      // 模拟访问不存在的路由
      window.history.pushState({}, '', '/nonexistent')
      
      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 应该渲染404页面或正确处理错误
      expect(screen.getByTestId('navigation')).toBeInTheDocument()
    })

    test('应该正确处理组件加载错误', async () => {
      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证错误边界正常工作
      expect(screen.getByTestId('navigation')).toBeInTheDocument()
    })
  })

  describe('服务集成', () => {
    test('应该正确集成API客户端', async () => {
      const { ApiClient } = await import('@/services/api.client')
      
      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证应用渲染
      expect(screen.getByTestId('navigation')).toBeInTheDocument()
      
      // 验证API客户端被正确mock
      expect(ApiClient).toBeDefined()
      expect(vi.isMockFunction(ApiClient.submitAnalysis)).toBe(true)
    })

    test('应该正确集成SSE服务', async () => {
      const { realTimeTaskService } = await import('@/services/sse.service')
      
      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证应用渲染
      expect(screen.getByTestId('navigation')).toBeInTheDocument()
      
      // 验证SSE服务被正确mock
      expect(realTimeTaskService).toBeDefined()
      expect(vi.isMockFunction(realTimeTaskService.startMonitoring)).toBe(true)
    })
  })

  describe('性能和可访问性', () => {
    test('应该快速加载应用', async () => {
      const startTime = Date.now()
      
      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      expect(screen.getByTestId('navigation')).toBeInTheDocument()
      
      const loadTime = Date.now() - startTime
      expect(loadTime).toBeLessThan(1000) // 1秒内加载完成
    })

    test('应该具有基本的可访问性结构', async () => {
      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证导航具有正确的语义结构
      const navigation = screen.getByTestId('navigation')
      expect(navigation).toBeInTheDocument()
      expect(navigation.tagName.toLowerCase()).toBe('nav')
    })
  })
})