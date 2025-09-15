import type { ApiResponse, PaginatedResponse, User, AnalysisTask, AnalysisReport } from "@/types"
import { appConfig } from "@/config/app"

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

class ApiService {
  private baseUrl: string
  private timeout: number
  private retryAttempts: number
  private mockMode: boolean

  constructor() {
    this.baseUrl = appConfig.api.baseUrl
    this.timeout = appConfig.api.timeout
    this.retryAttempts = appConfig.api.retryAttempts
    this.mockMode = appConfig.api.baseUrl.includes("localhost") || process.env.NODE_ENV === "development"
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
    if (this.mockMode) {
      console.log("[v0] Using mock API for:", endpoint)
      return this.mockRequest<T>(endpoint, options)
    }

    const url = `${this.baseUrl}${endpoint}`
    const token = this.getAuthToken()

    const config: RequestInit = {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    }

    let lastError: Error

    for (let attempt = 0; attempt <= this.retryAttempts; attempt++) {
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), this.timeout)

        const response = await fetch(url, {
          ...config,
          signal: controller.signal,
        })

        clearTimeout(timeoutId)

        if (!response.ok) {
          throw new ApiError(`HTTP ${response.status}: ${response.statusText}`, response.status)
        }

        const data = await response.json()
        return data
      } catch (error) {
        lastError = error as Error

        if (attempt < this.retryAttempts && this.shouldRetry(error as Error)) {
          await this.delay(Math.pow(2, attempt) * 1000) // Exponential backoff
          continue
        }

        break
      }
    }

    throw lastError!
  }

  private shouldRetry(error: Error): boolean {
    if (error instanceof ApiError) {
      return error.status >= 500 || error.status === 429
    }
    return error.name === "AbortError" || error.name === "TypeError"
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  }

  private getAuthToken(): string | null {
    if (typeof window === "undefined") return null
    return localStorage.getItem("auth_token")
  }

  private setAuthToken(token: string): void {
    if (typeof window !== "undefined") {
      localStorage.setItem("auth_token", token)
    }
  }

  private removeAuthToken(): void {
    if (typeof window !== "undefined") {
      localStorage.removeItem("auth_token")
    }
  }

  private generateMockTask(productDescription: string): AnalysisTask {
    const taskId = `task_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    return {
      id: taskId,
      product_description: productDescription,
      status: "pending",
      progress: 0,
      current_step: "community_discovery",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      estimated_completion: new Date(Date.now() + 15000).toISOString(), // 15 seconds from now
      report_id: null,
      error_message: null,
    }
  }

  private generateMockReport(): AnalysisReport {
    return {
      id: `report_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      task_id: "",
      created_at: new Date().toISOString(),
      market_metrics: {
        total_mentions: 2847,
        sentiment_score: 0.72,
        top_communities: ["r/entrepreneur", "r/startups", "r/SaaS"],
        trending_keywords: ["automation", "productivity", "workflow"],
      },
      pain_points: [
        {
          title: "手动数据收集效率低下",
          description: "用户反映需要花费大量时间手动收集和整理市场数据，影响决策速度",
          severity: "high",
          mentions: 342,
          examples: ["每天要花3-4小时整理数据", "手动收集容易出错", "数据更新不及时"],
        },
        {
          title: "缺乏实时市场洞察",
          description: "现有工具无法提供实时的市场趋势分析，错失商业机会",
          severity: "medium",
          mentions: 198,
          examples: ["市场变化太快，工具跟不上", "需要更及时的趋势预警", "竞品动态发现太晚"],
        },
        {
          title: "数据分析门槛过高",
          description: "非技术背景的用户难以进行深度的数据分析和解读",
          severity: "medium",
          mentions: 156,
          examples: ["不懂如何解读数据", "需要更直观的可视化", "希望有智能推荐"],
        },
      ],
      competitors: [
        {
          name: "Product Hunt平台",
          sentiment: "positive",
          mentions: 1247,
          strengths: ["社区活跃度高", "产品发现机制完善", "用户参与度强"],
          weaknesses: ["商业化程度不够", "对中文产品支持有限", "缺乏深度分析功能"],
          market_share: 35,
        },
        {
          name: "BetaList社区",
          sentiment: "neutral",
          mentions: 892,
          strengths: ["早期产品聚焦", "投资人关注度高", "质量控制严格"],
          weaknesses: ["用户基数较小", "更新频率不高", "地域局限性强"],
          market_share: 22,
        },
        {
          name: "Indie Hackers社区",
          sentiment: "positive",
          mentions: 634,
          strengths: ["创业者社区活跃", "经验分享丰富", "商业化导向强"],
          weaknesses: ["技术门槛较高", "非英语用户参与度低", "产品类型相对局限"],
          market_share: 18,
        },
      ],
      opportunities: [
        {
          title: "中文市场产品发现平台",
          description: "针对中文用户的产品发现和推广平台存在巨大空白",
          potential: "high",
          difficulty: "medium",
          timeline: "6-12个月",
          key_factors: ["本土化运营", "中文内容生态", "本地支付集成"],
        },
        {
          title: "AI驱动的市场分析工具",
          description: "结合人工智能技术，提供更智能的市场洞察和趋势预测",
          potential: "high",
          difficulty: "hard",
          timeline: "12-18个月",
          key_factors: ["AI算法优化", "大数据处理能力", "实时分析引擎"],
        },
        {
          title: "垂直行业解决方案",
          description: "针对特定行业（如SaaS、电商、教育）的专业化分析工具",
          potential: "medium",
          difficulty: "easy",
          timeline: "3-6个月",
          key_factors: ["行业专业知识", "垂直数据源", "定制化功能"],
        },
      ],
    }
  }

  private async mockRequest<T>(endpoint: string, options: RequestInit = {}): Promise<ApiResponse<T>> {
    await this.delay(500 + Math.random() * 1000)

    if (endpoint === "/analysis/tasks" && options.method === "POST") {
      const body = JSON.parse(options.body as string)
      const task = this.generateMockTask(body.product_description)
      return { success: true, data: task as T }
    }

    if (endpoint.startsWith("/analysis/tasks/") && !endpoint.includes("/cancel")) {
      const taskId = endpoint.split("/")[3]
      const progress = Math.min(100, Math.floor(Math.random() * 100))
      const isComplete = progress >= 100

      const task: AnalysisTask = {
        id: taskId,
        product_description: "模拟产品描述",
        status: isComplete ? "completed" : "processing",
        progress,
        current_step: isComplete ? "insight_generation" : "nlp_analysis",
        created_at: new Date(Date.now() - 60000).toISOString(),
        updated_at: new Date().toISOString(),
        estimated_completion: new Date(Date.now() + 5000).toISOString(),
        report_id: isComplete ? `report_${taskId}` : null,
        error_message: null,
      }
      return { success: true, data: task as T }
    }

    if (endpoint.startsWith("/reports/") && !endpoint.includes("/feedback")) {
      const report = this.generateMockReport()
      return { success: true, data: report as T }
    }

    if (endpoint.includes("/feedback")) {
      return { success: true, data: null as T }
    }

    return { success: true, data: null as T }
  }

  // Auth endpoints
  async login(email: string, password: string): Promise<ApiResponse<{ user: User; token: string }>> {
    const response = await this.request<{ user: User; token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })

    if (response.success && response.data) {
      this.setAuthToken(response.data.token)
    }

    return response
  }

  async signup(name: string, email: string, password: string): Promise<ApiResponse<{ user: User; token: string }>> {
    const response = await this.request<{ user: User; token: string }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    })

    if (response.success && response.data) {
      this.setAuthToken(response.data.token)
    }

    return response
  }

  async logout(): Promise<void> {
    try {
      await this.request("/auth/logout", { method: "POST" })
    } finally {
      this.removeAuthToken()
    }
  }

  async getCurrentUser(): Promise<ApiResponse<User>> {
    return this.request<User>("/auth/me")
  }

  // Analysis endpoints
  async createAnalysisTask(productDescription: string): Promise<ApiResponse<AnalysisTask>> {
    return this.request<AnalysisTask>("/analysis/tasks", {
      method: "POST",
      body: JSON.stringify({ product_description: productDescription }),
    })
  }

  async getAnalysisTask(taskId: string): Promise<ApiResponse<AnalysisTask>> {
    return this.request<AnalysisTask>(`/analysis/tasks/${taskId}`)
  }

  async cancelAnalysisTask(taskId: string): Promise<ApiResponse<void>> {
    return this.request<void>(`/analysis/tasks/${taskId}/cancel`, {
      method: "POST",
    })
  }

  // Report endpoints
  async getAnalysisReport(reportId: string): Promise<ApiResponse<AnalysisReport>> {
    return this.request<AnalysisReport>(`/reports/${reportId}`)
  }

  async getUserReports(page = 1, limit = 10): Promise<PaginatedResponse<AnalysisReport>> {
    return this.request<AnalysisReport[]>(`/reports?page=${page}&limit=${limit}`)
  }

  async submitReportFeedback(
    reportId: string,
    rating: "valuable" | "average" | "not_valuable",
  ): Promise<ApiResponse<void>> {
    return this.request<void>(`/reports/${reportId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ rating }),
    })
  }

  // WebSocket connection for real-time updates
  createTaskWebSocket(taskId: string): WebSocket | null {
    if (typeof window === "undefined") return null

    if (this.mockMode) {
      console.log("[v0] Skipping WebSocket creation in mock mode")
      return null
    }

    const wsUrl = this.baseUrl.replace("http", "ws") + `/analysis/tasks/${taskId}/ws`
    const token = this.getAuthToken()

    try {
      return new WebSocket(`${wsUrl}${token ? `?token=${token}` : ""}`)
    } catch (error) {
      console.error("[v0] WebSocket creation failed:", error)
      return null
    }
  }
}

export const apiService = new ApiService()
export { ApiError }
