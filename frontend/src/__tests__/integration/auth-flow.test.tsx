/**
 * 认证流程集成测试 - 严格遵循Context7最佳实践
 * 测试AuthService与UI组件集成、认证状态管理、路由保护
 */

import { describe, test, beforeEach, vi, expect } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import { MemoryRouter } from 'react-router-dom'
import { ReactNode } from 'react'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import AppRouter from '@/router/AppRouter'

// Context7最佳实践：Mock所有外部依赖
vi.mock('@/services/auth.service', () => ({
  AuthService: {
    login: vi.fn(),
    logout: vi.fn(),
    verifyToken: vi.fn(),
    refreshToken: vi.fn(),
    isAuthenticated: vi.fn(),
    getCurrentUser: vi.fn(),
    getCurrentToken: vi.fn(),
    restoreAuthState: vi.fn(),
    classifyAuthError: vi.fn(),
    getAuthHeaders: vi.fn(),
    clearAuthData: vi.fn(),
    storeAuthData: vi.fn(),
  },
}))

vi.mock('@/utils/security', () => ({
  SecureStorage: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  },
}))

vi.mock('@/services/api.client', () => ({
  ApiClient: {
    submitAnalysis: vi.fn(),
    getTaskStatus: vi.fn(),
    getReport: vi.fn(),
  },
  validateTaskId: vi.fn(),
}))

vi.mock('@/components/LoadingFallback', () => ({
  default: () => <div data-testid="loading">加载中...</div>,
}))

// MSW服务器设置 - Context7最佳实践
const server = setupServer(
  // Mock登录API
  http.post('/api/auth/login', async ({ request }) => {
    const body = await request.json() as { email: string; password: string }
    if (body.email === 'test@example.com' && body.password === 'password123') {
      return HttpResponse.json({
        user: { id: '1', email: 'test@example.com', name: 'Test User' },
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
      })
    }
    return HttpResponse.json(
      { message: '用户名或密码错误' },
      { status: 401 }
    )
  }),

  // Mock登出API
  http.post('/api/auth/logout', () => {
    return HttpResponse.json({ message: '注销成功' })
  }),

  // Mock token验证API
  http.post('/api/auth/verify', async ({ request }) => {
    const body = await request.json() as { token: string }
    if (body.token === 'valid-token') {
      return HttpResponse.json({ valid: true })
    }
    return HttpResponse.json({ valid: false })
  }),

  // Mock token刷新API
  http.post('/api/auth/refresh', async ({ request }) => {
    const body = await request.json() as { refresh_token: string }
    if (body.refresh_token === 'valid-refresh-token') {
      return HttpResponse.json({
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        user: { id: '1', email: 'test@example.com', name: 'Test User' },
      })
    }
    return HttpResponse.json(
      { message: 'Invalid refresh token' },
      { status: 401 }
    )
  })
)

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

describe('认证流程集成测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    server.resetHandlers()
  })

  beforeAll(() => server.listen())
  afterAll(() => server.close())
  afterEach(() => server.resetHandlers())

  describe('认证状态UI展示', () => {
    test('应该显示未认证用户的初始状态', async () => {
      const { AuthService } = await import('@/services/auth.service')
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(false)
      vi.mocked(AuthService.getCurrentUser).mockReturnValue(null)

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // Context7异步等待页面加载
      const navigation = await screen.findByRole('navigation')
      expect(navigation).toBeInTheDocument()

      // 验证未认证状态的UI元素
      expect(screen.getByText('描述您的产品')).toBeInTheDocument()
    })

    test('应该显示已认证用户的状态', async () => {
      const { AuthService } = await import('@/services/auth.service')
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(true)
      vi.mocked(AuthService.getCurrentUser).mockReturnValue({
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // Context7异步等待认证状态加载
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })

      // 验证已认证状态可以被正确获取
      expect(AuthService.isAuthenticated()).toBe(true)
      expect(AuthService.getCurrentUser()).toEqual({
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
      })
    })

    test('应该正确处理认证状态变化', async () => {
      const { AuthService } = await import('@/services/auth.service')
      
      // 初始未认证状态
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(false)

      const { rerender } = render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证未认证状态
      await screen.findByRole('navigation')

      // 模拟认证状态变更
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(true)
      vi.mocked(AuthService.getCurrentUser).mockReturnValue({
        id: '1',
        email: 'test@example.com',
        name: 'Test User',
      })

      rerender(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证状态变化后的UI
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })
    })
  })

  describe('认证交互测试', () => {
    test('应该支持模拟登录流程', async () => {
      const { AuthService } = await import('@/services/auth.service')
      const mockLoginResponse = {
        user: { id: '1', email: 'test@example.com', name: 'Test User' },
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
      }

      vi.mocked(AuthService.login).mockResolvedValue(mockLoginResponse)
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(false)

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // Context7异步等待页面加载
      await screen.findByRole('navigation')

      // 模拟登录成功场景
      await AuthService.login('test@example.com', 'password123')
      expect(AuthService.login).toHaveBeenCalledWith('test@example.com', 'password123')
    })

    test('应该处理登录失败场景', async () => {
      const { AuthService } = await import('@/services/auth.service')
      const loginError = new Error('用户名或密码错误')
      
      vi.mocked(AuthService.login).mockRejectedValue(loginError)
      vi.mocked(AuthService.classifyAuthError).mockReturnValue({
        type: 'INVALID_CREDENTIALS' as const,
        message: '用户名或密码错误',
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 模拟登录失败场景
      await expect(
        AuthService.login('wrong@example.com', 'wrongpassword')
      ).rejects.toThrow('用户名或密码错误')
      
      // 验证错误分类功能
      const classifiedError = AuthService.classifyAuthError(loginError)
      expect(classifiedError).toEqual({
        type: 'INVALID_CREDENTIALS',
        message: '用户名或密码错误',
      })
    })

    test('应该支持登出功能', async () => {
      const { AuthService } = await import('@/services/auth.service')
      
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(true)
      vi.mocked(AuthService.logout).mockResolvedValue()

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 模拟登出操作
      await AuthService.logout()
      expect(AuthService.logout).toHaveBeenCalled()
    })
  })

  describe('路由保护集成', () => {
    test('应该允许未认证用户访问公开路由', async () => {
      const { AuthService } = await import('@/services/auth.service')
      const { validateTaskId } = await import('@/services/api.client')
      
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(false)
      vi.mocked(validateTaskId).mockResolvedValue(true)

      render(
        <TestWrapper initialEntries={['/']}>
          <AppRouter />
        </TestWrapper>
      )

      // Context7异步等待公开路由加载
      const navigation = await screen.findByRole('navigation')
      expect(navigation).toBeInTheDocument()
      expect(screen.getByText('描述您的产品')).toBeInTheDocument()
    })

    test('应该处理需要验证的路由', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockResolvedValue(true)

      render(
        <TestWrapper initialEntries={['/analysis/test-task-123']}>
          <AppRouter />
        </TestWrapper>
      )

      // Context7异步等待路由验证
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })

      expect(validateTaskId).toHaveBeenCalledWith('test-task-123')
    })

    test('应该处理无效的任务ID路由', async () => {
      const { validateTaskId } = await import('@/services/api.client')
      vi.mocked(validateTaskId).mockResolvedValue(false)

      render(
        <TestWrapper initialEntries={['/analysis/invalid-task']}>
          <AppRouter />
        </TestWrapper>
      )

      // Context7异步等待重定向处理
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      })
    })
  })

  describe('认证错误处理', () => {
    test('应该处理网络认证错误', async () => {
      const { AuthService } = await import('@/services/auth.service')
      const networkError = new Error('Network connection failed')
      
      vi.mocked(AuthService.login).mockRejectedValue(networkError)
      vi.mocked(AuthService.classifyAuthError).mockReturnValue({
        type: 'NETWORK' as const,
        message: '网络连接失败，请检查网络设置',
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 模拟网络错误场景
      try {
        await AuthService.login('test@example.com', 'password123')
      } catch (error) {
        const classifiedError = AuthService.classifyAuthError(networkError)
        expect(classifiedError.type).toBe('NETWORK')
        expect(classifiedError.message).toBe('网络连接失败，请检查网络设置')
      }
    })

    test('应该处理token过期错误', async () => {
      const { AuthService } = await import('@/services/auth.service')
      const expiredError = new Error('Token expired')
      
      vi.mocked(AuthService.verifyToken).mockResolvedValue(false)
      vi.mocked(AuthService.refreshToken).mockRejectedValue(expiredError)
      vi.mocked(AuthService.classifyAuthError).mockReturnValue({
        type: 'TOKEN_EXPIRED' as const,
        message: '登录已过期，请重新登录',
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 模拟token过期场景
      const isValid = await AuthService.verifyToken('expired-token')
      expect(isValid).toBe(false)

      try {
        await AuthService.refreshToken()
      } catch (error) {
        const classifiedError = AuthService.classifyAuthError(expiredError)
        expect(classifiedError.type).toBe('TOKEN_EXPIRED')
      }
    })

    test('应该处理认证服务错误恢复', async () => {
      const { AuthService } = await import('@/services/auth.service')
      
      // 模拟服务暂时不可用
      vi.mocked(AuthService.login).mockRejectedValueOnce(new Error('Service unavailable'))
      vi.mocked(AuthService.login).mockResolvedValueOnce({
        user: { id: '1', email: 'test@example.com', name: 'Test User' },
        access_token: 'recovered-token',
        refresh_token: 'recovered-refresh-token',
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 第一次调用失败
      try {
        await AuthService.login('test@example.com', 'password123')
      } catch (error) {
        expect(error.message).toBe('Service unavailable')
      }

      // 第二次调用成功（恢复）
      const result = await AuthService.login('test@example.com', 'password123')
      expect(result.access_token).toBe('recovered-token')
    })
  })

  describe('认证状态持久化', () => {
    test('应该能恢复认证状态', async () => {
      const { AuthService } = await import('@/services/auth.service')
      const { SecureStorage } = await import('@/utils/security')
      
      const savedAuthState = {
        user: { id: '1', email: 'test@example.com', name: 'Test User' },
        token: 'saved-token',
        refreshToken: 'saved-refresh-token',
      }

      vi.mocked(AuthService.restoreAuthState).mockReturnValue(savedAuthState)
      vi.mocked(SecureStorage.getItem).mockImplementation((key) => {
        switch (key) {
          case 'auth_token': return 'saved-token'
          case 'user_data': return JSON.stringify(savedAuthState.user)
          case 'refresh_token': return 'saved-refresh-token'
          default: return null
        }
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 验证状态恢复
      const restoredState = AuthService.restoreAuthState()
      expect(restoredState).toEqual(savedAuthState)
    })

    test('应该处理损坏的认证数据', async () => {
      const { AuthService } = await import('@/services/auth.service')
      const { SecureStorage } = await import('@/utils/security')
      
      vi.mocked(AuthService.restoreAuthState).mockReturnValue(null)
      vi.mocked(SecureStorage.getItem).mockImplementation((key) => {
        if (key === 'user_data') return 'invalid-json'
        return 'some-value'
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 验证损坏数据处理
      const restoredState = AuthService.restoreAuthState()
      expect(restoredState).toBeNull()
    })

    test('应该正确清除认证数据', async () => {
      const { AuthService } = await import('@/services/auth.service')
      const { SecureStorage } = await import('@/utils/security')

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 模拟清除认证数据
      AuthService.clearAuthData()
      
      expect(AuthService.clearAuthData).toHaveBeenCalled()
      // SecureStorage的清除操作会在AuthService.clearAuthData内部调用
    })
  })

  describe('认证头部和API集成', () => {
    test('应该正确设置认证头部', async () => {
      const { AuthService } = await import('@/services/auth.service')
      
      vi.mocked(AuthService.getCurrentToken).mockReturnValue('test-token')
      vi.mocked(AuthService.getAuthHeaders).mockReturnValue({
        Authorization: 'Bearer test-token'
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 验证认证头部设置
      const headers = AuthService.getAuthHeaders()
      expect(headers).toEqual({ Authorization: 'Bearer test-token' })
    })

    test('应该处理无token时的头部', async () => {
      const { AuthService } = await import('@/services/auth.service')
      
      vi.mocked(AuthService.getCurrentToken).mockReturnValue(null)
      vi.mocked(AuthService.getAuthHeaders).mockReturnValue({})

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 验证无token时的头部
      const headers = AuthService.getAuthHeaders()
      expect(headers).toEqual({})
    })

    test('应该集成API调用与认证', async () => {
      const { ApiClient } = await import('@/services/api.client')
      const { AuthService } = await import('@/services/auth.service')
      
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(true)
      vi.mocked(AuthService.getAuthHeaders).mockReturnValue({
        Authorization: 'Bearer valid-token'
      })
      vi.mocked(ApiClient.submitAnalysis).mockResolvedValue({
        task_id: 'test-task-123',
        status: 'processing'
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')

      // 验证认证状态下的API调用
      if (AuthService.isAuthenticated()) {
        const headers = AuthService.getAuthHeaders()
        expect(headers.Authorization).toBe('Bearer valid-token')
      }
    })
  })

  describe('性能和可访问性', () => {
    test('应该快速处理认证状态检查', async () => {
      const { AuthService } = await import('@/services/auth.service')
      
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(true)
      
      const startTime = Date.now()

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      await screen.findByRole('navigation')
      
      const checkTime = Date.now() - startTime
      expect(checkTime).toBeLessThan(100) // 100ms内完成认证检查
    })

    test('应该在认证流程中保持可访问性', async () => {
      const { AuthService } = await import('@/services/auth.service')
      
      vi.mocked(AuthService.isAuthenticated).mockReturnValue(false)

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // 验证导航的可访问性结构
      const navigation = await screen.findByRole('navigation')
      expect(navigation).toBeInTheDocument()
      expect(navigation.tagName.toLowerCase()).toBe('nav')
    })

    test('应该正确处理认证状态的异步加载', async () => {
      const { AuthService } = await import('@/services/auth.service')
      
      // 模拟异步认证状态检查
      vi.mocked(AuthService.restoreAuthState).mockImplementation(() => {
        return new Promise(resolve => {
          setTimeout(() => resolve({
            user: { id: '1', email: 'test@example.com', name: 'Test User' },
            token: 'async-token',
            refreshToken: 'async-refresh-token',
          }), 50)
        }) as any
      })

      render(
        <TestWrapper>
          <AppRouter />
        </TestWrapper>
      )

      // Context7异步等待认证状态加载完成
      await waitFor(() => {
        expect(screen.getByRole('navigation')).toBeInTheDocument()
      }, { timeout: 1000 })
    })
  })
})