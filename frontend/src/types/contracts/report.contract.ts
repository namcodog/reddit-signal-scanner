/**
 * 报告相关类型契约
 * 与backend/app/schemas/contracts/report_contract.py完全对应
 */

export enum ReportFormat {
  FULL = "full",
  SUMMARY = "summary",
  INSIGHTS = "insights"
}

export interface InsightItem {
  title: string;
  content: string;
  confidence: number; // 0.0 - 1.0
  source_count: number;
  tags: string[];
}

// 5个关键字段的类型定义
export interface ExecutiveSummary {
  headline?: string;
  total_communities: number;
  key_insights: number;
  top_opportunity?: string;
  confidence_score?: number;
  summary_points: string[];
}

export interface MarketMetrics {
  total_mentions: number;
  sentiment_score: number;
  top_communities: string[];
  trending_keywords: string[];
  engagement_rate?: number;
  sample_size?: number;
}

export interface PainPointExample {
  post_id: string;
  community?: string;
  permalink?: string;
  content_snippet?: string;
  upvotes?: number;
}

export interface PainPointInsight {
  description: string;
  sentiment_score: number;
  frequency: number;
  confidence?: number;
  severity?: "low" | "medium" | "high";
  categories: string[];
  example_posts: PainPointExample[];
  tags: string[];
}

export interface CompetitorInsight {
  name: string;
  description?: string;
  market_position?: "leader" | "challenger" | "follower" | "niche";
  mention_count: number;
  sentiment_score: number;
  strengths: string[];
  weaknesses: string[];
  market_share_estimate?: number;
}

export interface OpportunityInsight {
  title: string;
  description: string;
  potential: "low" | "medium" | "high";
  difficulty: "easy" | "medium" | "hard";
  market_size?: string;
  confidence?: number;
  timeframe?: string;
  key_insights: string[];
}

export interface ReportData {
  // 基本元数据
  task_id: string;
  query: string;
  total_posts: number;
  total_comments: number;
  analysis_duration: number;
  confidence_score?: number;

  // 核心洞察
  key_insights: InsightItem[];
  sentiment_summary: Record<string, number>;
  trending_topics: string[];
  user_personas: Array<Record<string, unknown>>;

  // 元数据
  generated_at: string;
  data_freshness: string;
  html_content?: string; // 可选字段

  // 5个关键字段
  executive_summary: ExecutiveSummary;
  market_metrics: MarketMetrics;
  pain_points: PainPointInsight[];
  competitors: CompetitorInsight[];
  opportunities: OpportunityInsight[];

  // 前端扩展的可视化数据
  charts?: ChartData[];
  visualization_config?: VisualizationConfig;
}

// 前端专用的可视化类型
export interface ChartData {
  id: string;
  type: 'pie' | 'bar' | 'line' | 'radar';
  title: string;
  data: Array<{
    label: string;
    value: number;
    color?: string;
  }>;
}

export interface VisualizationConfig {
  theme: 'light' | 'dark';
  colorScheme: string[];
  responsive: boolean;
  animations: boolean;
}

// 报告页面组件Props
export interface ReportPageProps {
  taskId: string;
  format?: ReportFormat;
  onExport?: (format: 'pdf' | 'json') => void;
  onShare?: () => void;
}

// 子组件Props类型
export interface ExecutiveSummaryProps {
  executiveSummary?: ExecutiveSummary;
  totalPosts?: number;
  totalComments?: number;
  confidence?: number;
  sentimentSummary?: Record<string, number>;
}

export interface PainPointsListProps {
  painPoints?: PainPointInsight[];
  sentimentSummary?: Record<string, number>;
  onInsightClick?: (insight: PainPointInsight) => void;
}

export interface CompetitorAnalysisProps {
  competitors?: CompetitorInsight[];
  onCompetitorSelect?: (competitor: CompetitorInsight) => void;
}

export interface OpportunityMatrixProps {
  opportunities?: OpportunityInsight[];
  onOpportunityClick?: (opportunity: OpportunityInsight) => void;
}
