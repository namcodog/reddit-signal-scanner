export interface User {
  id: string
  name: string
  email: string
  createdAt?: string
  subscription?: "free" | "pro" | "enterprise"
}

export interface AuthState {
  isAuthenticated: boolean
  user: User | null
  token: string | null
}

export interface ProductDescription {
  content: string
  wordCount: number
  createdAt: string
}

export interface AnalysisTask {
  id: string
  status: "pending" | "running" | "completed" | "failed"
  progress: number
  currentStep: AnalysisStep
  productDescription: string
  createdAt: string
  completedAt?: string
  error?: string
}

export interface AnalysisStep {
  name: string
  status: "pending" | "running" | "completed" | "failed"
  progress: number
  startTime?: string
  endTime?: string
  metadata?: Record<string, any>
}

export interface MarketMetrics {
  totalMentions: number
  sentiment: "positive" | "negative" | "neutral"
  sentimentScore: number
  topCommunities: string[]
  timeRange: string
  lastUpdated: string
}

export interface PainPoint {
  id: string
  title: string
  description: string
  mentions: number
  severity: "low" | "medium" | "high"
  examples: UserExample[]
  categories: string[]
  trend: "increasing" | "stable" | "decreasing"
}

export interface UserExample {
  id: string
  content: string
  author: string
  subreddit: string
  upvotes: number
  createdAt: string
  url: string
}

export interface Competitor {
  id: string
  name: string
  sentiment: "positive" | "negative" | "neutral"
  mentions: number
  marketShare: number
  strengths: string[]
  weaknesses: string[]
  pricing?: string
  website?: string
}

export interface BusinessOpportunity {
  id: string
  title: string
  description: string
  potential: "low" | "medium" | "high"
  difficulty: "easy" | "medium" | "hard"
  timeToMarket: string
  targetAudience: string[]
  requiredResources: string[]
  estimatedRevenue?: string
}

export interface AnalysisReport {
  id: string
  taskId: string
  marketMetrics: MarketMetrics
  painPoints: PainPoint[]
  competitors: Competitor[]
  opportunities: BusinessOpportunity[]
  summary: string
  recommendations: string[]
  createdAt: string
  expiresAt: string
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  message?: string
  timestamp: string
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  pagination: {
    page: number
    limit: number
    total: number
    totalPages: number
  }
}

export interface AppConfig {
  api: {
    baseUrl: string
    timeout: number
    retryAttempts: number
  }
  analysis: {
    maxDescriptionLength: number
    minDescriptionLength: number
    estimatedDuration: number
  }
  features: {
    enableAuth: boolean
    enableReports: boolean
    enableExport: boolean
  }
}

export type AppStep = "input" | "analysis" | "report"

export interface AppState {
  currentStep: AppStep
  auth: AuthState
  productDescription: string
  analysisTask: AnalysisTask | null
  report: AnalysisReport | null
  config: AppConfig
}
