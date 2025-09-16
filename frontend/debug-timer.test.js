// 简单的定时器测试，验证vi.advanceTimersByTimeAsync是否正常工作
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('Timer Debug', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should advance timers correctly', async () => {
    let executed = false;

    setTimeout(() => {
      executed = true;
      console.log('Timer executed!');
    }, 150);

    expect(executed).toBe(false);

    await vi.advanceTimersByTimeAsync(150);

    expect(executed).toBe(true);
  });
});