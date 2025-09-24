export enum ReportFormat {
  SUMMARY = 'summary',
  FULL = 'full',
}

export interface InsightItem {
  title: string;
  content: string;
  confidence?: number;
  source_count?: number;
  tags?: string[];
}

export interface ReportData {
  task_id: string;
  query?: string;
  summary?: string;
  key_insights?: InsightItem[];
  generated_at?: string;
}

export interface ChartData {
  id: string;
  type: 'pie' | 'bar' | 'line';
  title: string;
  data: Array<{ label: string; value: number }>;
}

export interface VisualizationConfig {
  theme?: 'light' | 'dark';
  responsive?: boolean;
}

export interface ReportPageProps {
  taskId: string;
  format?: ReportFormat;
}

export interface ExecutiveSummaryProps {
  insights?: InsightItem[];
}

export interface PainPointsListProps {
  insights?: InsightItem[];
  onInsightClick?: (insight: InsightItem) => void;
}

export interface CompetitorAnalysisProps {
  competitors?: Array<{ name: string }>;
}

export interface OpportunityMatrixProps {
  opportunities?: Array<{ title: string }>;
}
