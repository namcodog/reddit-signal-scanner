/**
 * V0 API适配器 - 将设计版API调用适配到现有真实API
 * 
 * 功能：
 * 1. 将设计版的Mock API调用转换为真实API调用
 * 2. 处理数据结构映射和字段转换
 * 3. 保持与设计版组件的接口兼容性
 * 4. 集成现有的认证和错误处理机制
 */

import AuthService from './auth.service';
import { apiClient } from './api.client';
import { configService } from './config.service';
import reportService from './report.service';
import {
  ReportFormat,
  type PainPointInsight as ReportPainPointInsight,
  type CompetitorInsight as ReportCompetitorInsight,
  type OpportunityInsight as ReportOpportunityInsight
} from '@/types/contracts/report.contract';
import type { User as AuthUser } from '@/types/auth.types';
import logger from '@/utils/logger';

// 设计版数据类型定义
export interface V0AnalysisTask {
  id: string;
  product_description: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  current_step: string;
  created_at: string;
  updated_at: string;
  estimated_completion: string | null;
  report_id: string | null;
  error_message: string | null;
}

export interface V0AnalysisReport {
  id: string;
  task_id: string;
  created_at: string;
  market_metrics: {
    total_mentions: number;
    sentiment_score: number;
    top_communities: string[];
    trending_keywords: string[];
  };
  pain_points: Array<{
    title: string;
    description: string;
    severity: "high" | "medium" | "low";
    mentions: number;
    examples: string[];
  }>;
  competitors: Array<{
    name: string;
    sentiment: "positive" | "negative" | "mixed";
    mentions: number;
    strengths: string[];
    weaknesses: string[];
    market_share: number;
  }>;
  opportunities: Array<{
    title: string;
    description: string;
    potential: "high" | "medium" | "low";
    difficulty: "easy" | "medium" | "hard";
    timeline: string;
    key_factors: string[];
  }>;
}

export interface V0User {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

export interface V0ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

interface TaskSubmissionResponse {
  task_id: string;
  status: string;
  queue_name?: string;
  progress?: number;
  created_at?: string;
  updated_at?: string;
  submitted_at?: string;
  estimated_start_time?: string | null;
  estimated_completion?: string | null;
  error_message?: string | null;
}

type AnalyzeApiResponse = AnalyzeResponseEnvelope | TaskSubmissionResponse;

type StatusApiResponse = StatusResponseEnvelope | (TaskSubmissionResponse & Record<string, unknown>);

const SUCCESS_STATUSES = new Set(['success', 'ok', 'accepted']);

function isTaskSubmissionResponse(value: unknown): value is TaskSubmissionResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    'task_id' in value &&
    typeof (value as { task_id?: unknown }).task_id === 'string'
  );
}

function normalizeStatus(status: unknown): string {
  return typeof status === 'string' ? status.trim().toLowerCase() : '';
}

/**
 * V0 API适配器类
 */
interface AnalyzeResponseEnvelope {
  status: string;
  message: string;
  timestamp: string;
  data?: TaskSubmissionResponse & Record<string, unknown>;
}

interface StatusResponseEnvelope {
  status: string;
  message: string;
  timestamp: string;
  data?: (TaskSubmissionResponse & Record<string, unknown>) | Record<string, unknown>;
}

class V0ApiAdapter {
  /**
   * 用户认证 - 适配到现有auth.service
   */
  async login(email: string, password: string): Promise<V0ApiResponse<{ user: V0User; token: string }>> {
    try {
      const session = await AuthService.login(email, password);

      return {
        success: true,
        data: {
          user: this.mapUser(session.user, session.user.email),
          token: session.accessToken,
        },
      };
    } catch (error) {
      logger.error('V0ApiAdapter.login failed:', error);
      const authError = AuthService.classifyAuthError(error as Error);
      return {
        success: false,
        error: authError.message,
      };
    }
  }

  /**
   * 用户注册 - 适配到现有auth.service
   */
  async signup(name: string, email: string, password: string): Promise<V0ApiResponse<{ user: V0User; token: string }>> {
    try {
      const payload = {
        email,
        password,
        confirmPassword: password,
        acceptTerms: true,
        acceptPrivacy: true,
      } as const;

      const session = await AuthService.register(payload);

      return {
        success: true,
        data: {
          user: this.mapUser(session.user, name || email),
          token: session.accessToken,
        },
      };
    } catch (error) {
      logger.error('V0ApiAdapter.signup failed:', error);
      const authError = AuthService.classifyAuthError(error as Error);
      return {
        success: false,
        error: authError.message,
      };
    }
  }

  /**
   * 获取当前用户 - 适配到现有auth.service
   */
  async getCurrentUser(): Promise<V0ApiResponse<V0User>> {
    try {
      const restored = AuthService.restoreAuthState();

      if (restored) {
        return {
          success: true,
          data: this.mapUser(restored.user, restored.user.email),
        };
      }

      return {
        success: false,
        error: '用户未登录',
      };
    } catch (error) {
      logger.error('V0ApiAdapter.getCurrentUser failed:', error);
      return {
        success: false,
        error: '网络错误，请稍后重试',
      };
    }
  }

  /**
   * 创建分析任务 - 适配到现有discovery API
   */
  async createAnalysisTask(productDescription: string): Promise<V0ApiResponse<V0AnalysisTask>> {
    try {
      const endpoint = configService.getAnalyzeEndpoint();


      const response = await apiClient.post<AnalyzeApiResponse>(endpoint, {
        product_description: productDescription,
      });



      const envelope = response as AnalyzeResponseEnvelope;
      const envelopeStatus = normalizeStatus(envelope?.status);
      const envelopeData = (envelope && 'data' in envelope ? envelope.data : undefined) as unknown;

      const payload = isTaskSubmissionResponse(response)
        ? response
        : isTaskSubmissionResponse(envelopeData)
          ? envelopeData
          : undefined;

      const isSuccessfulEnvelope = SUCCESS_STATUSES.has(envelopeStatus);
      const isSuccessful = Boolean(payload) && (isSuccessfulEnvelope || isTaskSubmissionResponse(response));

      if (isSuccessful && payload) {
        const createdAt = payload.submitted_at || payload.created_at || new Date().toISOString();
        const updatedAt = payload.updated_at || createdAt;
        const payloadRecord = payload as unknown as Record<string, unknown>;

        const v0Task: V0AnalysisTask = {
          id: payload.task_id,
          product_description: productDescription,
          status: this.mapTaskStatus(payload.status),
          progress: payload.progress ?? 0,
          current_step:
            (payloadRecord.current_step as string | undefined) ??
            (payloadRecord.currentStep as string | undefined) ??
            'community_discovery',
          created_at: createdAt,
          updated_at: updatedAt,
          estimated_completion:
            payload.estimated_completion ??
            payload.estimated_start_time ??
            new Date(Date.now() + 5 * 60 * 1000).toISOString(),
          report_id: (payloadRecord.report_id as string | null | undefined) ?? null,
          error_message: payload.error_message ?? null,
        };

        logger.info('[V0ApiAdapter] createAnalysisTask success', {
          taskId: v0Task.id,
          status: payload.status,
          queue: payload.queue_name,
        });

        return {
          success: true,
          data: v0Task,
        };
      }

      const failureMessage =
        (typeof envelope?.message === 'string' && envelope.message.trim()) ||
        '创建分析任务失败';

      logger.warn('[V0ApiAdapter] createAnalysisTask envelope indicated failure', {
        status: envelope?.status,
        message: envelope?.message,
      });

      return {
        success: false,
        error: failureMessage,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : '网络错误，请稍后重试';
      logger.error('V0ApiAdapter.createAnalysisTask failed:', error);
      return {
        success: false,
        error: message || '网络错误，请稍后重试',
      };
    }
  }

  /**
   * 获取分析任务状态 - 适配到现有status API
   */
  async getAnalysisTask(taskId: string): Promise<V0ApiResponse<V0AnalysisTask>> {
    try {
      const endpoint = configService.getStatusEndpoint(taskId);
      const response = await apiClient.get<StatusApiResponse>(endpoint);

      const envelope = response as StatusResponseEnvelope;
      const envelopeStatus = normalizeStatus(envelope?.status);
      const envelopeData = (envelope && 'data' in envelope ? envelope.data : undefined) as unknown;

      const payload = isTaskSubmissionResponse(response)
        ? response
        : isTaskSubmissionResponse(envelopeData)
          ? envelopeData
          : undefined;

      const isSuccessful = Boolean(payload) && (
        SUCCESS_STATUSES.has(envelopeStatus) || isTaskSubmissionResponse(response)
      );

      if (isSuccessful && payload) {
        const payloadRecord = payload as unknown as Record<string, unknown>;
        const v0Task: V0AnalysisTask = {
          id: payload.task_id || taskId,
          product_description:
            (payloadRecord.description as string | undefined) ??
            (payloadRecord.product_description as string | undefined) ??
            '',
          status: this.mapTaskStatus(payload.status),
          progress: payload.progress ?? 0,
          current_step:
            (payloadRecord.current_step as string | undefined) ??
            (payloadRecord.currentStep as string | undefined) ??
            'community_discovery',
          created_at: payload.created_at || payload.submitted_at || new Date().toISOString(),
          updated_at: payload.updated_at || new Date().toISOString(),
          estimated_completion:
            payload.estimated_completion ??
            payload.estimated_start_time ??
            new Date(Date.now() + 5 * 60 * 1000).toISOString(),
          report_id: (payloadRecord.report_id as string | null | undefined) ?? null,
          error_message: payload.error_message ?? null,
        };

        return {
          success: true,
          data: v0Task,
        };
      }

      const failureMessage =
        (typeof envelope?.message === 'string' && envelope.message.trim()) ||
        '获取任务状态失败';

      logger.warn('[V0ApiAdapter] getAnalysisTask envelope indicated failure', {
        status: envelope?.status,
        message: envelope?.message,
      });

      return {
        success: false,
        error: failureMessage,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : '网络错误，请稍后重试';
      logger.error('V0ApiAdapter.getAnalysisTask failed:', error);
      return {
        success: false,
        error: message || '网络错误，请稍后重试',
      };
    }
  }

    /**
   * 获取分析报告 - 适配到现有report.service
   */
  async getAnalysisReport(taskId: string): Promise<V0ApiResponse<V0AnalysisReport>> {
    try {
      const result = await reportService.getReport({
        task_id: taskId,
        format: ReportFormat.FULL,
      });

      if (result.success && result.data) {
        const reportData = result.data;
        const marketMetrics = reportData.market_metrics ?? {
          total_mentions: reportData.total_posts + reportData.total_comments,
          sentiment_score: 0,
          top_communities: [],
          trending_keywords: reportData.trending_topics ?? [],
        };

        const v0Report: V0AnalysisReport = {
          id: taskId,
          task_id: reportData.task_id,
          created_at: reportData.generated_at || new Date().toISOString(),
          market_metrics: {
            total_mentions: marketMetrics.total_mentions,
            sentiment_score: marketMetrics.sentiment_score ?? 0,
            top_communities: marketMetrics.top_communities ?? [],
            trending_keywords:
              (marketMetrics.trending_keywords?.length ?? 0) > 0
                ? marketMetrics.trending_keywords
                : reportData.trending_topics ?? [],
          },
          pain_points: this.mapPainPoints(
            (reportData.pain_points as ReportPainPointInsight[] | undefined) ?? []
          ),
          competitors: this.mapCompetitors(
            (reportData.competitors as ReportCompetitorInsight[] | undefined) ?? []
          ),
          opportunities: this.mapOpportunities(
            (reportData.opportunities as ReportOpportunityInsight[] | undefined) ?? []
          ),
        };
        
        return {
          success: true,
          data: v0Report,
        };
      }
      
      return {
        success: false,
        error: '获取报告失败',
      };
    } catch (error) {
      logger.error('V0ApiAdapter.getAnalysisReport failed:', error);
      return {
        success: false,
        error: '网络错误，请稍后重试',
      };
    }
  }

  /**
   * 取消分析任务
   */
  async cancelAnalysisTask(taskId: string): Promise<V0ApiResponse<void>> {
    try {
      // 这里可以调用现有的取消API，如果有的话
      // 目前先返回成功，实际实现需要根据后端API确定
      logger.info('V0ApiAdapter.cancelAnalysisTask called for task:', taskId);
      
      return {
        success: true,
      };
    } catch (error) {
      logger.error('V0ApiAdapter.cancelAnalysisTask failed:', error);
      return {
        success: false,
        error: '取消任务失败',
      };
    }
  }

  /**
   * 私有方法：映射任务状态
   */
  private mapTaskStatus(status: string): V0AnalysisTask['status'] {
    switch (status?.toLowerCase()) {
      case 'pending':
      case 'queued':
        return 'pending';
      case 'running':
      case 'processing':
      case 'in_progress':
        return 'processing';
      case 'completed':
      case 'success':
        return 'completed';
      case 'failed':
      case 'error':
        return 'failed';
      default:
        return 'pending';
    }
  }

  /**
   * 私有方法：映射痛点数据
   */
  private mapPainPoints(
    painPoints: ReportPainPointInsight[]
  ): V0AnalysisReport['pain_points'] {
    return painPoints.slice(0, 6).map((point, index) => ({
      title:
        point.tags?.[0] ??
        point.categories?.[0] ??
        (point as unknown as { title?: string }).title ??
        `痛点 #${index + 1}`,
      description: point.description ?? '',
      severity: this.deriveSeverity(
        point.severity,
        point.sentiment_score ?? 0,
        point.frequency ?? 0
      ),
      mentions: point.frequency ?? 0,
      examples: this.extractExamples(point.example_posts),
    }));
  }

  /**
   * 私有方法：映射竞品数据
   */
  private mapCompetitors(
    competitors: ReportCompetitorInsight[]
  ): V0AnalysisReport['competitors'] {
    const totalMentions = competitors.reduce(
      (acc, comp) => acc + (comp.mention_count ?? 0),
      0
    );
    return competitors.slice(0, 6).map((comp) => {
      const share =
        comp.share_of_voice !== undefined
          ? comp.share_of_voice * 100
          : totalMentions > 0
          ? (comp.mention_count / totalMentions) * 100
          : 0;
      return {
        name: comp.name ?? '',
        sentiment: this.mapCompetitorSentiment(comp.sentiment_score ?? 0),
        mentions: comp.mention_count ?? 0,
        strengths: comp.strengths ?? [],
        weaknesses: comp.weaknesses ?? [],
        market_share: Math.round(Math.max(0, Math.min(100, share))),
      };
    });
  }

  /**
   * 私有方法：映射机会数据
   */
  private mapOpportunities(
    opportunities: ReportOpportunityInsight[]
  ): V0AnalysisReport['opportunities'] {
    return opportunities.slice(0, 6).map((opp) => ({
      title: opp.title ?? '',
      description: opp.description ?? '',
      potential: this.mapOpportunityPotential(opp.market_size_indicator, opp.potential_score),
      difficulty: this.mapOpportunityDifficulty(opp.feasibility_score ?? 0),
      timeline: opp.timeframe ?? '',
      key_factors: (opp.related_keywords ?? opp.target_communities ?? []).slice(0, 6),
    }));
  }

  /**
   * 私有方法：将真实用户映射到V0结构
   */
  private mapUser(user: Pick<AuthUser, 'id' | 'email' | 'createdAt'>, fallbackName: string): V0User {
    const candidate = fallbackName || user.email;
    const displayName = candidate.includes('@') ? candidate.split('@')[0] : candidate;

    return {
      id: user.id,
      name: displayName,
      email: user.email,
      created_at: user.createdAt || new Date().toISOString(),
    };
  }

  private deriveSeverity(
    severity: ReportPainPointInsight['severity'] | undefined,
    sentimentScore: number,
    frequency: number
  ): 'high' | 'medium' | 'low' {
    if (severity === 'high' || severity === 'medium' || severity === 'low') {
      return severity;
    }
    if (frequency >= 50 || sentimentScore <= -0.6) {
      return 'high';
    }
    if (frequency >= 20 || sentimentScore <= -0.3) {
      return 'medium';
    }
    return 'low';
  }

  private extractExamples(
    examples: ReportPainPointInsight['example_posts']
  ): string[] {
    if (!examples) {
      return [];
    }
    return examples
      .map((example) => {
        if (!example) {
          return '';
        }
        if (example.content_snippet) {
          return example.content_snippet;
        }
        if (example.permalink) {
          return example.permalink;
        }
        return example.post_id ?? '';
      })
      .filter(Boolean);
  }

  private mapCompetitorSentiment(score: number): 'positive' | 'negative' | 'mixed' {
    if (score > 0.2) {
      return 'positive';
    }
    if (score < -0.2) {
      return 'negative';
    }
    return 'mixed';
  }

  private mapOpportunityPotential(
    indicator: ReportOpportunityInsight['market_size_indicator'],
    potentialScore?: number
  ): 'high' | 'medium' | 'low' {
    if (indicator === 'huge' || indicator === 'large') {
      return 'high';
    }
    if (indicator === 'medium') {
      return 'medium';
    }
    if (indicator === 'tiny' || indicator === 'small') {
      return 'low';
    }
    if (typeof potentialScore === 'number') {
      if (potentialScore >= 0.7) {
        return 'high';
      }
      if (potentialScore >= 0.4) {
        return 'medium';
      }
      return 'low';
    }
    return 'medium';
  }

  private mapOpportunityDifficulty(score: number): 'easy' | 'medium' | 'hard' {
    if (score >= 0.7) {
      return 'easy';
    }
    if (score >= 0.4) {
      return 'medium';
    }
    return 'hard';
  }
}

// 导出单例
export const v0ApiAdapter = new V0ApiAdapter();
export default v0ApiAdapter;
