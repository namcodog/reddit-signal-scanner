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

export interface ReportData {
  // 基本元数据
  task_id: string;
  query: string;
  total_posts: number;
  total_comments: number;
  analysis_duration: number;

  // 核心洞察
  key_insights: InsightItem[];
  sentiment_summary: Record<string, number>;
  trending_topics: string[];
  user_personas: Array<Record<string, unknown>>;

  // 元数据
  generated_at: string;
  data_freshness: string;
  html_content?: string; // 可选字段

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
  insights?: InsightItem[];
  totalPosts?: number;
  totalComments?: number;
  confidence?: number;
  sentimentSummary?: Record<string, number>;
}

export interface PainPointsListProps {
  insights?: InsightItem[];  // 修复：改为可选属性，避免undefined错误
  sentimentSummary?: Record<string, number>;  // 修复：改为可选属性保持一致性
  onInsightClick?: (insight: InsightItem) => void;
}

export interface CompetitorAnalysisProps {
  competitors?: Array<{  // 修复：改为可选属性，避免undefined错误
    name: string;
    strengths: string[];
    weaknesses: string[];
    market_position: string;
  }>;
  onCompetitorSelect?: (competitor: string) => void;
}

export interface OpportunityMatrixProps {
  opportunities?: Array<{  // 修复：改为可选属性，避免undefined错误
    title: string;
    impact: 'low' | 'medium' | 'high';
    difficulty: 'low' | 'medium' | 'high';
    description: string;
  }>;
  onOpportunityClick?: (opportunity: string) => void;
}