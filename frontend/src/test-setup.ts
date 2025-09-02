/**
 * 测试环境统一配置 - 基于Linus极简原则
 * 一次配置，消除所有环境特殊情况
 */

import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock浏览器API - 消除Node.js环境差异
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock IntersectionObserver - 常见的浏览器API
class MockIntersectionObserver {
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
}

Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  configurable: true,
  value: MockIntersectionObserver,
})

Object.defineProperty(global, 'IntersectionObserver', {
  writable: true,
  configurable: true,
  value: MockIntersectionObserver,
})

// Mock ResizeObserver - 另一个常见API
class MockResizeObserver {
  observe = vi.fn()
  disconnect = vi.fn()
  unobserve = vi.fn()
}

Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  configurable: true,
  value: MockResizeObserver,
})

// Mock navigator.userAgent - 用户代理字符串
Object.defineProperty(navigator, 'userAgent', {
  writable: true,
  value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
})

// Mock crypto API - 加密相关
Object.defineProperty(global, 'crypto', {
  value: {
    randomUUID: () => '123e4567-e89b-12d3-a456-426614174000',
    getRandomValues: (arr: any) => arr.map(() => Math.floor(Math.random() * 256))
  }
})

// Mock Canvas API - 解决HTMLCanvasElement.getContext问题
class MockCanvasRenderingContext2D {
  textBaseline = 'top'
  font = '14px Arial'
  fillText = vi.fn()
  measureText = vi.fn(() => ({ width: 100 }))
  getImageData = vi.fn(() => ({
    data: new Uint8ClampedArray(4)
  }))
}

// 重写HTMLCanvasElement.getContext方法
HTMLCanvasElement.prototype.getContext = vi.fn((type: string) => {
  if (type === '2d') {
    return new MockCanvasRenderingContext2D()
  }
  return null
}) as any

// Mock HTMLCanvasElement.toDataURL - 用于指纹生成
HTMLCanvasElement.prototype.toDataURL = vi.fn(() => 
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAASwAAAABCAYAAAB'
)

// 全局错误处理 - 捕获未处理的测试错误
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason)
})

process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error)
})