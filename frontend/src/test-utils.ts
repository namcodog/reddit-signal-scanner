/**
 * 测试工具函数 - 标准化定时器和异步操作处理
 * 基于Vitest最佳实践，消除定时器使用中的特殊情况
 */

import { act } from '@testing-library/react';
import { vi } from 'vitest';

/**
 * 标准化的定时器推进函数
 * 替代vi.advanceTimersByTime，支持异步操作
 */
export async function advanceTimersAndWait(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

/**
 * 运行所有定时器并等待异步操作完成
 * 替代vi.runAllTimers，支持异步定时器
 */
export async function runAllTimersAndWait(): Promise<void> {
  await act(async () => {
    await vi.runAllTimersAsync();
  });
}

/**
 * 运行所有待处理的定时器（不包括执行过程中创建的新定时器）
 * 替代vi.runOnlyPendingTimers，支持异步操作
 */
export async function runPendingTimersAndWait(): Promise<void> {
  await act(async () => {
    await vi.runOnlyPendingTimersAsync();
  });
}

/**
 * 推进到下一个定时器并等待执行完成
 * 替代vi.advanceTimersToNextTimer，支持异步操作
 */
export async function advanceToNextTimerAndWait(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersToNextTimerAsync();
  });
}

/**
 * 标准化的测试清理函数
 * 确保每个测试后都正确清理定时器状态
 */
export function cleanupTest(): void {
  vi.clearAllTimers();
  vi.clearAllMocks();
}

/**
 * 带act包装的状态更新函数
 * 确保所有状态更新都正确包装，避免act()警告
 */
export async function actAndWait(callback: () => void | Promise<void>): Promise<void> {
  await act(async () => {
    await callback();
  });
}

/**
 * 标准化的beforeEach设置
 */
export function setupFakeTimers(): void {
  vi.useFakeTimers();
}

/**
 * 标准化的afterEach清理 - 使用官方推荐方法
 */
export function cleanupFakeTimers(): void {
  vi.restoreAllMocks();
  vi.clearAllTimers();
}