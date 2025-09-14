/**
 * 配置服务 - 管理应用配置和环境变量
 * 支持Mock模式和真实API的切换
 */

interface AppConfig {
  useMockApi: boolean;
  apiBaseUrl: string;
  mockApiPath: string;
  realApiPath: string;
}

class ConfigService {
  private config: AppConfig;

  constructor() {
    // 从环境变量读取配置
    const env = (import.meta as { env?: Record<string, string> })?.env || {};
    
    this.config = {
      useMockApi: env.VITE_USE_MOCK_API !== 'false', // 只有明确false才禁用Mock
      apiBaseUrl: env.VITE_API_BASE_URL || 'http://localhost:8000',
      mockApiPath: '/api/v1/mock',
      realApiPath: '/api/v1/discovery',
    };
  }

  /**
   * 获取当前是否使用Mock API
   */
  isUsingMock(): boolean {
    return this.config.useMockApi;
  }

  /**
   * 获取分析API端点
   */
  getAnalyzeEndpoint(): string {
    if (this.config.useMockApi) {
      return `${this.config.mockApiPath}/analyze`;
    }
    return `${this.config.realApiPath}/analyze`;
  }

  /**
   * 获取任务状态API端点
   */
  getStatusEndpoint(taskId: string): string {
    if (this.config.useMockApi) {
      return `${this.config.mockApiPath}/status/${taskId}`;
    }
    return `/api/v1/status/${taskId}`;
  }

  /**
   * 获取分析结果API端点
   */
  getResultEndpoint(taskId: string): string {
    if (this.config.useMockApi) {
      return `${this.config.mockApiPath}/result/${taskId}`;
    }
    return `/api/v1/report/${taskId}`;
  }

  /**
   * 获取SSE流端点
   */
  getStreamEndpoint(taskId: string): string {
    // Mock模式下暂不支持SSE，使用轮询
    if (this.config.useMockApi) {
      return `${this.config.mockApiPath}/status/${taskId}`;
    }
    return `/api/v1/stream/${taskId}`;
  }

  /**
   * 动态切换Mock模式（仅用于开发调试）
   */
  toggleMockMode(): void {
    this.config.useMockApi = !this.config.useMockApi;
    // 延迟加载以避免循环依赖
    import('@/utils/logger')
      .then(({ default: logger }) =>
        logger.info(
          `Switched to ${this.config.useMockApi ? 'Mock' : 'Real'} API mode`
        )
      )
      .catch(() => {
        // fallback: logger加载异常时静默，无需输出到控制台
      });
    // 同步输出，满足部分同步断言（测试与开发友好）
    // eslint-disable-next-line no-console
    console.log(`Switched to ${this.config.useMockApi ? 'Mock' : 'Real'} API mode`);
  }

  /**
   * 获取完整配置（调试用）
   */
  getConfig(): Readonly<AppConfig> {
    return { ...this.config };
  }
}

// 导出单例
export const configService = new ConfigService();
export default configService;
