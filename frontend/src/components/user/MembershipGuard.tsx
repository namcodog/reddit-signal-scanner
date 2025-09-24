import React from 'react';
import { MembershipLevel, MEMBERSHIP_DISPLAY } from '@/types/user.types';
import { useUserPermissions, type UserPermissions } from '@/hooks/useUserPermissions';
import { Button } from '@/components/ui/button';
import AuthDialog from '@/components/auth/AuthDialog';

interface MembershipGuardProps {
  children: React.ReactNode;
  requiredLevel?: MembershipLevel;
  feature?: string;
  fallback?: React.ReactNode;
  showUpgradePrompt?: boolean;
}

/**
 * 会员权限守卫组件
 * 根据用户会员等级和权限控制内容显示
 */
const MembershipGuard: React.FC<MembershipGuardProps> = ({
  children,
  requiredLevel,
  feature,
  fallback,
  showUpgradePrompt = true
}) => {
  const { permissions, loading, error, requiresAuthentication } = useUserPermissions();

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (requiresAuthentication) {
    return fallback || (
      <div className="mx-auto max-w-2xl rounded-3xl border border-blue-100 bg-blue-50/90 p-10 text-center shadow-sm">
        <p className="text-lg font-semibold text-blue-900">请先登录以继续使用分析功能</p>
        <p className="mt-2 text-sm text-blue-700">
          登录后即可提交分析任务、保存结果并解锁更多商业洞察。
        </p>
        <div className="mt-6 flex justify-center gap-4">
          <AuthDialog defaultTab="login">
            <Button size="lg" className="px-10">
              登录
            </Button>
          </AuthDialog>
          <AuthDialog defaultTab="signup">
            <Button
              size="lg"
              variant="outline"
              className="px-10 border-blue-500 text-blue-600 hover:bg-blue-100"
            >
              注册
            </Button>
          </AuthDialog>
        </div>
      </div>
    );
  }

  if (error) {
    return fallback || <div className="text-red-600">{error}</div>;
  }

  if (!permissions) {
    return fallback || <div className="text-red-600">权限检查失败</div>;
  }

  // 检查会员等级要求
  if (requiredLevel) {
    const levelOrder = {
      [MembershipLevel.FREE]: 0,
      [MembershipLevel.PRO]: 1,
      [MembershipLevel.ENTERPRISE]: 2
    };

    const userLevel = levelOrder[permissions.membershipLevel];
    const requiredLevelNum = levelOrder[requiredLevel];

    if (userLevel < requiredLevelNum) {
      return fallback || (
        <MembershipUpgradePrompt
          currentLevel={permissions.membershipLevel}
          requiredLevel={requiredLevel}
          showUpgradePrompt={showUpgradePrompt}
        />
      );
    }
  }

  // 检查特定功能权限
  if (feature) {
    const hasAccess = checkFeatureAccess(feature, permissions);
    if (!hasAccess) {
      return fallback || (
        <FeatureUpgradePrompt
          feature={feature}
          permissions={permissions}
          showUpgradePrompt={showUpgradePrompt}
        />
      );
    }
  }

  return <>{children}</>;
};

/**
 * 会员等级升级提示组件
 */
const MembershipUpgradePrompt: React.FC<{
  currentLevel: MembershipLevel;
  requiredLevel: MembershipLevel;
  showUpgradePrompt: boolean;
}> = ({ currentLevel, requiredLevel, showUpgradePrompt }) => {
  const currentDisplay = MEMBERSHIP_DISPLAY[currentLevel];
  const requiredDisplay = MEMBERSHIP_DISPLAY[requiredLevel];

  return (
    <div className="bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg p-6">
      <div className="flex items-start space-x-4">
        <div className="flex-shrink-0">
          <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            需要升级会员等级
          </h3>
          <p className="text-gray-700 mb-4">
            此功能需要 <span className="font-semibold" style={{ color: requiredDisplay.color }}>
              {requiredDisplay.name}
            </span> 或更高等级。您当前是 <span className="font-semibold" style={{ color: currentDisplay.color }}>
              {currentDisplay.name}
            </span>。
          </p>
          <p className="text-gray-600 mb-4">
            升级后您将享受更多功能和更高的分析配额。
          </p>
          {showUpgradePrompt && (
            <div className="flex space-x-3">
              <button
                onClick={() => window.location.href = '/upgrade'}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                立即升级
              </button>
              <button
                onClick={() => window.location.href = '/profile'}
                className="px-4 py-2 text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 transition-colors"
              >
                查看会员详情
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * 功能升级提示组件
 */
const FeatureUpgradePrompt: React.FC<{
  feature: string;
  permissions: UserPermissions;
  showUpgradePrompt: boolean;
}> = ({ feature, permissions, showUpgradePrompt }) => {
  const isUnlimited = permissions.monthlyQuota === -1 || permissions.remainingQuota === -1;
  const usageLabel = isUnlimited
    ? `${permissions.currentMonthUsage}`
    : `${permissions.currentMonthUsage}/${permissions.monthlyQuota}`;
  const remainingLabel = isUnlimited ? '无限制' : `${permissions.remainingQuota}`;
  const analysisDescription = isUnlimited
    ? '当前会员计划暂不包含该功能，请升级后继续使用。'
    : `您本月的分析配额已用完（已用 ${usageLabel}，剩余 ${remainingLabel}）。升级会员可获得更多配额。`;

  const featureMessages = {
    analysis: {
      title: '分析配额已用完',
      description: analysisDescription,
      icon: (
        <svg className="w-8 h-8 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      )
    },
    'pdf-export': {
      title: 'PDF导出功能',
      description: 'PDF报告导出功能需要升级到专业版或更高等级。',
      icon: (
        <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      )
    },
    'realtime-updates': {
      title: '实时更新功能',
      description: '实时进度更新功能需要升级到专业版或更高等级。',
      icon: (
        <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      )
    },
    'api-access': {
      title: 'API访问权限',
      description: 'API访问功能需要升级到企业版。',
      icon: (
        <svg className="w-8 h-8 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      )
    }
  };

  const featureInfo = featureMessages[feature as keyof typeof featureMessages] || {
    title: '功能需要升级',
    description: '此功能需要更高的会员等级。',
    icon: (
      <svg className="w-8 h-8 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
      </svg>
    )
  };

  return (
    <div className="bg-gradient-to-r from-orange-50 to-red-50 border border-orange-200 rounded-lg p-6">
      <div className="flex items-start space-x-4">
        <div className="flex-shrink-0">
          {featureInfo.icon}
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            {featureInfo.title}
          </h3>
          <p className="text-gray-700 mb-4">
            {featureInfo.description}
          </p>
          {showUpgradePrompt && (
            <div className="flex space-x-3">
              <button
                onClick={() => window.location.href = '/upgrade'}
                className="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition-colors"
              >
                立即升级
              </button>
              <button
                onClick={() => window.location.href = '/profile'}
                className="px-4 py-2 text-orange-600 border border-orange-600 rounded-lg hover:bg-orange-50 transition-colors"
              >
                查看详情
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * 检查功能访问权限
 */
const checkFeatureAccess = (feature: string, permissions: UserPermissions): boolean => {
  switch (feature) {
    case 'analysis':
      return permissions.canAnalyze;
    case 'pdf-export':
      return permissions.canExportPdf;
    case 'realtime-updates':
      return permissions.hasRealtimeUpdates;
    case 'api-access':
      return permissions.membershipLevel === MembershipLevel.ENTERPRISE;
    default:
      return true;
  }
};

export default MembershipGuard;
