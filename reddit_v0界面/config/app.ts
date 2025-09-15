import type { AppConfig } from "./types" // Assuming AppConfig is declared in another file

export const appConfig: AppConfig = {
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
    timeout: 30000,
    retryAttempts: 3,
  },
  analysis: {
    maxDescriptionLength: 500,
    minDescriptionLength: 10,
    estimatedDuration: 300000, // 5 minutes in milliseconds
  },
  features: {
    enableAuth: process.env.NEXT_PUBLIC_ENABLE_AUTH === "true",
    enableReports: process.env.NEXT_PUBLIC_ENABLE_REPORTS !== "false",
    enableExport: process.env.NEXT_PUBLIC_ENABLE_EXPORT === "true",
  },
}

export const analysisSteps = [
  {
    key: "community_discovery",
    name: "社区发现",
    description: "识别相关Reddit社区",
    estimatedDuration: 60000, // 1 minute
  },
  {
    key: "content_extraction",
    name: "内容抓取",
    description: "提取相关帖子和评论",
    estimatedDuration: 120000, // 2 minutes
  },
  {
    key: "nlp_analysis",
    name: "NLP分析",
    description: "分析用户情感和痛点",
    estimatedDuration: 90000, // 1.5 minutes
  },
  {
    key: "insight_generation",
    name: "洞察生成",
    description: "生成商业洞察报告",
    estimatedDuration: 30000, // 30 seconds
  },
] as const

export type AnalysisStepKey = (typeof analysisSteps)[number]["key"]
