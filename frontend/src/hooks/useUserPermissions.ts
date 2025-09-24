import { useState, useEffect, useCallback } from 'react';
import { userService } from '@/services/user.service';
import { useSecureAuth } from '@/hooks/useSecureAuth';
import {
  MembershipLevel,
  MEMBERSHIP_FEATURES
} from '@/types/user.types';

export interface UserPermissions {
  canAnalyze: boolean;
  canExportPdf: boolean;
  hasRealtimeUpdates: boolean;
  remainingQuota: number;
  isQuotaExhausted: boolean;
  membershipLevel: MembershipLevel;
  needsUpgrade: boolean;
  currentMonthUsage: number;
  monthlyQuota: number;
}

export interface UseUserPermissionsReturn {
  permissions: UserPermissions | null;
  loading: boolean;
  error: string | null;
  requiresAuthentication: boolean;
  refresh: () => Promise<void>;
  checkFeatureAccess: (feature: string) => Promise<boolean>;
  showUpgradePrompt: (feature: string) => void;
}

/**
 * 用户权限管理Hook
 * 处理会员等级、配额限制、功能权限等
 */
export const useUserPermissions = (): UseUserPermissionsReturn => {
  const [permissions, setPermissions] = useState<UserPermissions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requiresAuth, setRequiresAuth] = useState<boolean>(false);
  const { isAuthenticated } = useSecureAuth();

  const loadPermissions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      if (!isAuthenticated) {
        setRequiresAuth(true);
        setPermissions(null);
        return;
      }

      setRequiresAuth(false);

      const [usageStats, membershipInfo] = await Promise.all([
        userService.getUsageStats(),
        userService.getMembershipInfo()
      ]);

      const membershipLevel = membershipInfo.level;
      const fallbackFeatures = MEMBERSHIP_FEATURES[membershipLevel];
      const featureFlags = membershipInfo.features;

      const quotaLimit = usageStats.currentMonthQuota ?? membershipInfo.quota ?? fallbackFeatures.monthlyQuota;
      const isUnlimited = quotaLimit === null;
      const computedRemaining = usageStats.remainingQuota ?? (isUnlimited ? null : Math.max((quotaLimit ?? 0) - usageStats.currentMonthTotal, 0));
      const normalizedRemaining = isUnlimited ? -1 : Math.max(computedRemaining ?? 0, 0);
      const isQuotaExhausted = !isUnlimited && normalizedRemaining <= 0;

      const userPermissions: UserPermissions = {
        canAnalyze: isUnlimited || normalizedRemaining > 0,
        canExportPdf: featureFlags.canExportReport,
        hasRealtimeUpdates: featureFlags.realtimeUpdates,
        remainingQuota: normalizedRemaining,
        isQuotaExhausted,
        membershipLevel,
        needsUpgrade: membershipInfo.upgradeOptions.length > 0 && (
          isQuotaExhausted ||
          membershipLevel === MembershipLevel.FREE
        ),
        currentMonthUsage: usageStats.currentMonthTotal,
        monthlyQuota: isUnlimited ? -1 : quotaLimit ?? -1,
      };

      setPermissions(userPermissions);
    } catch (err) {
      const message = err instanceof Error ? err.message : '获取用户权限失败';
      if (message.includes('401')) {
        setRequiresAuth(true);
        setPermissions(null);
        setError(null);
      } else {
        setError('获取用户权限失败');
        console.error('Failed to load user permissions:', err);
      }
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    loadPermissions();
  }, [loadPermissions]);

  const refresh = useCallback(async () => {
    await loadPermissions();
  }, [loadPermissions]);

  const checkFeatureAccess = useCallback(async (feature: string): Promise<boolean> => {
    try {
      if (!isAuthenticated) {
        return false;
      }
      return await userService.checkFeatureAccess(feature);
    } catch (err) {
      console.error('Failed to check feature access:', err);
      return false;
    }
  }, [isAuthenticated]);

  const showUpgradePrompt = useCallback((feature: string) => {
    const messages = {
      analysis: '您的分析配额已用完',
      'pdf-export': 'PDF导出功能需要升级到专业版',
      'realtime-updates': '实时更新功能需要升级到专业版',
      'priority-analysis': '高优先级分析需要升级到专业版',
      'api-access': 'API访问需要升级到企业版',
      'custom-integration': '自定义集成需要升级到企业版'
    };

    const message = messages[feature as keyof typeof messages] || '该功能需要升级会员';

    if (confirm(`${message}，是否立即升级？`)) {
      // 跳转到升级页面
      window.location.href = '/upgrade';
    }
  }, []);

  return {
    permissions,
    loading,
    error,
    requiresAuthentication: requiresAuth,
    refresh,
    checkFeatureAccess,
    showUpgradePrompt
  };
};

/**
 * 简化版权限检查Hook - 仅检查特定功能
 */
export const useFeatureAccess = (feature: string) => {
  const [hasAccess, setHasAccess] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAccess = async () => {
      try {
        setLoading(true);
        const access = await userService.checkFeatureAccess(feature);
        setHasAccess(access);
      } catch (err) {
        console.error('Failed to check feature access:', err);
        setHasAccess(false);
      } finally {
        setLoading(false);
      }
    };

    checkAccess();
  }, [feature]);

  return { hasAccess, loading };
};

/**
 * 配额监控Hook - 实时监控用户配额使用情况
 */
export const useQuotaMonitor = () => {
  const [quotaInfo, setQuotaInfo] = useState<{
    current: number;
    limit: number;
    percentage: number;
    isNearLimit: boolean;
    isExhausted: boolean;
  } | null>(null);

  const [loading, setLoading] = useState(true);

  const refreshQuota = useCallback(async () => {
    try {
      setLoading(true);
      const [stats, membershipInfo] = await Promise.all([
        userService.getUsageStats(),
        userService.getMembershipInfo()
      ]);

      const fallback = MEMBERSHIP_FEATURES[membershipInfo.level];
      const limitValue = stats.currentMonthQuota ?? membershipInfo.quota ?? fallback.monthlyQuota;
      const current = stats.currentMonthTotal;

      if (limitValue === null) {
        setQuotaInfo({
          current,
          limit: -1,
          percentage: 0,
          isNearLimit: false,
          isExhausted: false
        });
      } else {
        const limit = Math.max(limitValue, 1);
        const percentage = Math.min((current / limit) * 100, 100);
        const remaining = stats.remainingQuota ?? Math.max(limit - current, 0);
        setQuotaInfo({
          current,
          limit,
          percentage,
          isNearLimit: percentage >= 80,
          isExhausted: remaining <= 0
        });
      }
    } catch (err) {
      console.error('Failed to refresh quota:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshQuota();
  }, [refreshQuota]);

  return {
    quotaInfo,
    loading,
    refreshQuota
  };
};
