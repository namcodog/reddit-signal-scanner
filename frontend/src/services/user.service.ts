/**
 * Phase4 用户管理服务
 * 负责用户个人中心、会员管理、使用统计等API调用
 */

import {
  MembershipInfo,
  MembershipLevel,
  MembershipUpgradeRequest,
  PasswordChangeRequest,
  UserHistoryItem,
  UserHistoryResponse,
  UserProfile,
  UserProfileUpdateRequest,
  UserUsageStats,
  USER_ENDPOINTS,
} from '@/types/user.types';
import { httpClient } from './http.client';

type UserProfileApiResponse = {
  id: string;
  tenant_id: string;
  email: string;
  email_verified: boolean;
  is_active: boolean;
  membership_level: MembershipLevel;
  created_at: string;
  updated_at: string;
};

type UserHistoryItemApi = {
  task_id: string;
  status: string;
  status_label: string;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  description?: string | null;
};

type UserUsageStatsApi = {
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  active_tasks: number;
  pending_tasks: number;
  current_month_total: number;
  current_month_quota?: number | null;
  remaining_quota?: number | null;
  last_activity_at?: string | null;
};

type MembershipInfoApi = {
  level: MembershipLevel;
  label: string;
  used_this_month: number;
  remaining_quota: number | null;
  quota: number | null;
  features: {
    can_export_report: boolean;
    realtime_updates: boolean;
    priority_support: boolean;
    max_tasks_per_month: number | null;
    highlight?: string | null;
  };
  upgrade_options: MembershipLevel[];
};

const mapUserProfile = (payload: UserProfileApiResponse): UserProfile => ({
  id: payload.id,
  tenantId: payload.tenant_id,
  email: payload.email,
  emailVerified: payload.email_verified,
  isActive: payload.is_active,
  membershipLevel: payload.membership_level,
  createdAt: payload.created_at,
  updatedAt: payload.updated_at,
});

const mapHistoryItem = (item: UserHistoryItemApi): UserHistoryItem => ({
  taskId: item.task_id,
  status: item.status as UserHistoryItem['status'],
  statusLabel: item.status_label,
  createdAt: item.created_at,
  updatedAt: item.updated_at,
  completedAt: item.completed_at ?? null,
  description: item.description ?? null,
});

const mapUsageStats = (payload: UserUsageStatsApi): UserUsageStats => ({
  totalTasks: payload.total_tasks,
  completedTasks: payload.completed_tasks,
  failedTasks: payload.failed_tasks,
  activeTasks: payload.active_tasks,
  pendingTasks: payload.pending_tasks,
  currentMonthTotal: payload.current_month_total,
  currentMonthQuota: payload.current_month_quota ?? null,
  remainingQuota: payload.remaining_quota ?? null,
  lastActivityAt: payload.last_activity_at ?? null,
});

const mapMembershipInfo = (payload: MembershipInfoApi): MembershipInfo => ({
  level: payload.level,
  label: payload.label,
  usedThisMonth: payload.used_this_month,
  remainingQuota: payload.remaining_quota,
  quota: payload.quota,
  features: {
    canExportReport: payload.features.can_export_report,
    realtimeUpdates: payload.features.realtime_updates,
    prioritySupport: payload.features.priority_support,
    maxTasksPerMonth: payload.features.max_tasks_per_month,
    highlight: payload.features.highlight ?? null,
  },
  upgradeOptions: payload.upgrade_options,
});

export class UserService {
  /** 获取用户个人资料 */
  async getProfile(): Promise<UserProfile> {
    const response = await httpClient.get<UserProfileApiResponse>(
      USER_ENDPOINTS.PROFILE
    );
    return mapUserProfile(response);
  }

  /** 更新用户个人资料 */
  async updateProfile(updates: UserProfileUpdateRequest): Promise<UserProfile> {
    const payload = { ...updates };
    const response = await httpClient.patch<UserProfileApiResponse>(
      USER_ENDPOINTS.PROFILE,
      payload
    );
    return mapUserProfile(response);
  }

  /** 获取用户分析历史（按页模拟） */
  async getHistory(page = 1, limit = 20): Promise<UserHistoryResponse> {
    const safePage = Math.max(1, page);
    const safeLimit = Math.max(1, limit);
    const effectiveLimit = safePage * safeLimit;
    const rawItems = await httpClient.get<UserHistoryItemApi[]>(
      USER_ENDPOINTS.HISTORY,
      {
        params: { limit: effectiveLimit.toString() },
      }
    );

    const startIndex = (safePage - 1) * safeLimit;
    const pageItems = rawItems.slice(startIndex, startIndex + safeLimit);
    const items = pageItems.map(mapHistoryItem);
    const hasMore = rawItems.length === effectiveLimit;

    return {
      items,
      total: rawItems.length,
      page: safePage,
      limit: safeLimit,
      hasMore,
    };
  }

  /** 获取用户使用统计 */
  async getUsageStats(): Promise<UserUsageStats> {
    const response = await httpClient.get<UserUsageStatsApi>(
      USER_ENDPOINTS.USAGE
    );
    return mapUsageStats(response);
  }

  /** 获取会员权益信息 */
  async getMembershipInfo(): Promise<MembershipInfo> {
    const response = await httpClient.get<MembershipInfoApi>(
      USER_ENDPOINTS.MEMBERSHIP
    );
    return mapMembershipInfo(response);
  }

  /** 升级会员 */
  async upgradeMembership(request: MembershipUpgradeRequest): Promise<MembershipInfo> {
    const response = await httpClient.post<MembershipInfoApi>(
      USER_ENDPOINTS.UPGRADE,
      { target_level: request.targetLevel }
    );
    return mapMembershipInfo(response);
  }

  /** 修改密码 */
  async changePassword(payload: PasswordChangeRequest): Promise<void> {
    await httpClient.post(USER_ENDPOINTS.CHANGE_PASSWORD, {
      current_password: payload.currentPassword,
      new_password: payload.newPassword,
      confirm_password: payload.confirmPassword,
    });
  }

  /** 删除分析记录 */
  async deleteAnalysis(analysisId: string): Promise<void> {
    await httpClient.delete(`/api/v1/analyses/${analysisId}`);
  }

  /** 检查会员权限 */
  async checkFeatureAccess(feature: string): Promise<boolean> {
    try {
      const [usageStats, membershipInfo] = await Promise.all([
        this.getUsageStats(),
        this.getMembershipInfo(),
      ]);

      const normalizedFeature = feature.toLowerCase();

      if (normalizedFeature === 'analysis') {
        if (usageStats.currentMonthQuota === null) {
          return true;
        }
        const remaining = usageStats.remainingQuota ?? 0;
        return remaining > 0;
      }

      if (normalizedFeature === 'pdf-export') {
        return membershipInfo.features.canExportReport;
      }

      if (normalizedFeature === 'realtime-updates') {
        return membershipInfo.features.realtimeUpdates;
      }

      if (normalizedFeature === 'priority-analysis' || normalizedFeature === 'priority-support') {
        return membershipInfo.features.prioritySupport;
      }

      if (normalizedFeature === 'api-access' || normalizedFeature === 'custom-integration') {
        return membershipInfo.level === MembershipLevel.ENTERPRISE;
      }

      return true;
    } catch (error) {
      console.error('检查功能权限失败:', error);
      return false;
    }
  }
}

// 导出单例实例
export const userService = new UserService();
