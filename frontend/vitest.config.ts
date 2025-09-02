/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

/**
 * Vitest配置 - 基于Linus极简原则
 * 消除测试环境特殊情况，统一DOM API支持
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/components': path.resolve(__dirname, './src/components'),
      '@/pages': path.resolve(__dirname, './src/pages'),
      '@/services': path.resolve(__dirname, './src/services'),
      '@/hooks': path.resolve(__dirname, './src/hooks'),
      '@/types': path.resolve(__dirname, './src/types'),
      '@/styles': path.resolve(__dirname, './src/styles'),
      '@/utils': path.resolve(__dirname, './src/utils'),
    },
  },
  test: {
    // 配置DOM环境 - 消除浏览器API缺失问题
    environment: 'jsdom',
    
    // 全局设置 - 避免每个测试文件重复导入
    globals: true,
    
    // 自动导入测试工具 - 减少样板代码
    setupFiles: ['./src/test-setup.ts'],
    
    // 测试覆盖率配置
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test-setup.ts',
      ],
    },
    
    // 超时配置 - 防止测试卡死
    testTimeout: 10000,
    hookTimeout: 10000,
  },
})