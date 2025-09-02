/**
 * 错误处理系统测试 - 验证智能错误分类和处理
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { 
  ErrorClassifier, 
  ErrorType, 
  ErrorSeverity, 
  GlobalErrorHandler,
  handleError 
} from '@/utils/errorHandler';

describe('ErrorClassifier', () => {
  describe('错误类型分类', () => {
    it('应该正确分类网络错误', () => {
      const networkErrors = [
        'Network error occurred',
        'Fetch failed',
        'Connection refused',
        'Request timeout',
        'DNS error'
      ];

      networkErrors.forEach(error => {
        const type = ErrorClassifier.classify(error);
        expect(type).toBe(ErrorType.NETWORK);
      });
    });

    it('应该正确分类验证错误', () => {
      const validationErrors = [
        'Validation failed',
        'Invalid input provided',
        'Required field missing',
        '输入格式错误',
        '输入内容无效'
      ];

      validationErrors.forEach(error => {
        const type = ErrorClassifier.classify(error);
        expect(type).toBe(ErrorType.VALIDATION);
      });
    });

    it('应该正确分类认证错误', () => {
      const authErrors = [
        'Unauthorized access',
        'HTTP 401',
        'Authentication failed',
        'Invalid credentials',
        '登录失败',
        '身份验证失败'
      ];

      authErrors.forEach(error => {
        const type = ErrorClassifier.classify(error);
        expect(type).toBe(ErrorType.AUTHENTICATION);
      });
    });

    it('应该正确分类频率限制错误', () => {
      const rateLimitErrors = [
        'Rate limit exceeded',
        'HTTP 429',
        'Too many requests',
        '请求过于频繁',
        '限流'
      ];

      rateLimitErrors.forEach(error => {
        const type = ErrorClassifier.classify(error);
        expect(type).toBe(ErrorType.RATE_LIMIT);
      });
    });

    it('应该处理未知错误', () => {
      const unknownError = 'Something completely unexpected happened';
      const type = ErrorClassifier.classify(unknownError);
      expect(type).toBe(ErrorType.UNKNOWN);
    });
  });

  describe('错误严重级别', () => {
    it('应该为认证错误分配高严重级别', () => {
      const severity = ErrorClassifier.getSeverity(ErrorType.AUTHENTICATION);
      expect(severity).toBe(ErrorSeverity.HIGH);
    });

    it('应该为验证错误分配低严重级别', () => {
      const severity = ErrorClassifier.getSeverity(ErrorType.VALIDATION);
      expect(severity).toBe(ErrorSeverity.LOW);
    });

    it('应该为网络错误分配中等严重级别', () => {
      const severity = ErrorClassifier.getSeverity(ErrorType.NETWORK);
      expect(severity).toBe(ErrorSeverity.MEDIUM);
    });
  });

  describe('用户友好消息', () => {
    it('应该提供网络错误的友好消息', () => {
      const message = ErrorClassifier.getUserFriendlyMessage(ErrorType.NETWORK);
      expect(message).toContain('网络连接失败');
    });

    it('应该提供验证错误的友好消息', () => {
      const message = ErrorClassifier.getUserFriendlyMessage(ErrorType.VALIDATION);
      expect(message).toContain('输入信息有误');
    });

    it('应该提供认证错误的友好消息', () => {
      const message = ErrorClassifier.getUserFriendlyMessage(ErrorType.AUTHENTICATION);
      expect(message).toContain('登录已过期');
    });
  });

  describe('重试逻辑', () => {
    it('应该允许网络错误重试', () => {
      const canRetry = ErrorClassifier.canRetry(ErrorType.NETWORK);
      expect(canRetry).toBe(true);
    });

    it('应该不允许验证错误重试', () => {
      const canRetry = ErrorClassifier.canRetry(ErrorType.VALIDATION);
      expect(canRetry).toBe(false);
    });

    it('应该为重试提供合理的延迟时间', () => {
      const delay1 = ErrorClassifier.getRetryDelay(ErrorType.NETWORK, 1);
      const delay2 = ErrorClassifier.getRetryDelay(ErrorType.NETWORK, 2);
      const delay3 = ErrorClassifier.getRetryDelay(ErrorType.NETWORK, 3);

      // 指数退避策略
      expect(delay2).toBeGreaterThan(delay1);
      expect(delay3).toBeGreaterThan(delay2);

      // 最大延迟限制
      const maxDelay = ErrorClassifier.getRetryDelay(ErrorType.NETWORK, 10);
      expect(maxDelay).toBeLessThanOrEqual(30000);
    });
  });

  describe('恢复建议', () => {
    it('应该为网络错误提供恢复建议', () => {
      const actions = ErrorClassifier.getRecoveryActions(ErrorType.NETWORK);
      expect(actions).toContain('检查网络连接');
      expect(actions).toContain('刷新页面重试');
    });

    it('应该为验证错误提供恢复建议', () => {
      const actions = ErrorClassifier.getRecoveryActions(ErrorType.VALIDATION);
      expect(actions).toContain('检查输入格式');
      expect(actions).toContain('填写必填字段');
    });

    it('应该为所有错误类型提供建议', () => {
      Object.values(ErrorType).forEach(errorType => {
        const actions = ErrorClassifier.getRecoveryActions(errorType);
        expect(actions.length).toBeGreaterThan(0);
        expect(Array.isArray(actions)).toBe(true);
      });
    });
  });
});

describe('GlobalErrorHandler', () => {
  let errorHandler: GlobalErrorHandler;

  beforeEach(() => {
    errorHandler = GlobalErrorHandler.getInstance();
    errorHandler.clearErrorLog();
  });

  describe('错误处理', () => {
    it('应该处理Error对象', () => {
      const error = new Error('Test error');
      const result = errorHandler.handleError(error);

      expect(result).toBeDefined();
      expect(result.message).toBe('Test error');
      expect(result.userMessage).toBeDefined();
      expect(result.type).toBeDefined();
      expect(result.severity).toBeDefined();
    });

    it('应该处理字符串错误', () => {
      const error = 'Network connection failed';
      const result = errorHandler.handleError(error);

      expect(result.type).toBe(ErrorType.NETWORK);
      expect(result.message).toBe(error);
    });

    it('应该记录错误上下文', () => {
      const error = 'Test error';
      const context = {
        component: 'TestComponent',
        action: 'testAction',
        userId: 'user123'
      };

      errorHandler.handleError(error, context);
      const recentErrors = errorHandler.getRecentErrors(1);

      expect(recentErrors).toHaveLength(1);
      expect(recentErrors[0].component).toBe('TestComponent');
      expect(recentErrors[0].action).toBe('testAction');
      expect(recentErrors[0].userId).toBe('user123');
    });
  });

  describe('错误统计', () => {
    it('应该正确统计错误类型', () => {
      // 添加不同类型的错误
      errorHandler.handleError('Network error');
      errorHandler.handleError('Validation failed');
      errorHandler.handleError('Network timeout');

      const stats = errorHandler.getErrorStats();
      expect(stats[ErrorType.NETWORK]).toBe(2);
      expect(stats[ErrorType.VALIDATION]).toBe(1);
    });

    it('应该限制错误日志大小', () => {
      // 添加大量错误以测试大小限制
      for (let i = 0; i < 150; i++) {
        errorHandler.handleError(`Error ${i}`);
      }

      const recentErrors = errorHandler.getRecentErrors(200);
      expect(recentErrors.length).toBeLessThanOrEqual(100); // MAX_LOG_SIZE
    });
  });

  describe('单例模式', () => {
    it('应该返回同一个实例', () => {
      const instance1 = GlobalErrorHandler.getInstance();
      const instance2 = GlobalErrorHandler.getInstance();
      
      expect(instance1).toBe(instance2);
    });
  });
});

describe('便捷函数', () => {
  describe('handleError函数', () => {
    it('应该作为GlobalErrorHandler的便捷接口', () => {
      const error = 'Test error';
      const context = { component: 'TestComponent' };
      
      const result = handleError(error, context);
      
      expect(result).toBeDefined();
      expect(result.message).toBe(error);
    });
  });
});