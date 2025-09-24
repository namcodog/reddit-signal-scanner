import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import { userService } from '@/services/user.service';
import {
  UserProfile,
  UserUsageStats,
  MembershipInfo,
  UserHistoryItem,
  MembershipLevel,
  MEMBERSHIP_DISPLAY,
  MEMBERSHIP_FEATURES
} from '@/types/user.types';

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [usageStats, setUsageStats] = useState<UserUsageStats | null>(null);
  const [membershipInfo, setMembershipInfo] = useState<MembershipInfo | null>(null);
  const [recentHistory, setRecentHistory] = useState<UserHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadUserData();
  }, []);

  const loadUserData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [profileData, statsData, membershipData, historyData] = await Promise.all([
        userService.getProfile(),
        userService.getUsageStats(),
        userService.getMembershipInfo(),
        userService.getHistory(1, 5)
      ]);

      setProfile(profileData);
      setUsageStats(statsData);
      setMembershipInfo(membershipData);
      setRecentHistory(historyData.items);
    } catch (err) {
      setError('加载用户数据失败');
      console.error('Failed to load user data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = () => {
    navigate('/upgrade');
  };

  const handleViewAllHistory = () => {
    navigate('/history');
  };

  if (loading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">加载中...</p>
          </div>
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <p className="text-red-600 mb-4">{error}</p>
            <button
              onClick={loadUserData}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              重试
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!profile || !usageStats || !membershipInfo) {
    return null;
  }

  const membershipDisplay = MEMBERSHIP_DISPLAY[profile.membershipLevel];
  const fallbackFeatures = MEMBERSHIP_FEATURES[profile.membershipLevel];
  const quotaCap = usageStats.currentMonthQuota ?? membershipInfo.quota ?? fallbackFeatures.monthlyQuota;
  const quotaUsage = quotaCap === null || quotaCap === 0
    ? 0
    : (usageStats.currentMonthTotal / quotaCap) * 100;
  const remainingQuota = usageStats.remainingQuota ?? (quotaCap === null ? null : Math.max(quotaCap - usageStats.currentMonthTotal, 0));
  const featureList = fallbackFeatures.features;

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* 页面标题 */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">个人中心</h1>
          <p className="text-gray-600 mt-2">管理您的账户信息和使用统计</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* 左侧主要内容 */}
          <div className="lg:col-span-2 space-y-6">
            {/* 个人信息卡片 */}
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-gray-900">个人信息</h2>
                <button className="text-sm text-blue-600 hover:text-blue-700">
                  编辑
                </button>
              </div>

              <div className="space-y-4">
                <div className="flex items-center space-x-4">
                  <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center">
                    <span className="text-xl font-semibold text-blue-600">
                      {profile.email.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">{profile.email}</h3>
                    <div className="flex items-center space-x-2 mt-1">
                      <span
                        className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                        style={{
                          backgroundColor: `${membershipDisplay.color}20`,
                          color: membershipDisplay.color
                        }}
                      >
                        {membershipDisplay.badge}
                      </span>
                      {profile.emailVerified && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          已验证
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 border-t">
                  <div>
                    <p className="text-sm font-medium text-gray-500">注册时间</p>
                    <p className="text-sm text-gray-900">
                      {new Date(profile.createdAt).toLocaleDateString('zh-CN')}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-500">最后更新</p>
                    <p className="text-sm text-gray-900">
                      {new Date(profile.updatedAt).toLocaleDateString('zh-CN')}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* 使用统计卡片 */}
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-6">使用统计</h2>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-600">{usageStats.totalTasks}</div>
                  <div className="text-sm text-gray-500">总分析次数</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-green-600">{usageStats.completedTasks}</div>
                  <div className="text-sm text-gray-500">成功完成</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-red-600">{usageStats.failedTasks}</div>
                  <div className="text-sm text-gray-500">失败次数</div>
                </div>
              </div>

              {/* 配额使用情况 */}
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">本月使用配额</span>
                  <span className="text-sm text-gray-500">
                    {usageStats.currentMonthTotal} / {quotaCap === null ? '无限制' : quotaCap}
                  </span>
                </div>
                {quotaCap !== null && (
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(quotaUsage, 100)}%` }}
                    ></div>
                  </div>
                )}
                <p className="text-xs text-gray-500 mt-2">
                  {remainingQuota === null
                    ? '本月配额无限制'
                    : `剩余额度约 ${remainingQuota} 次`}
                </p>
                {usageStats.lastActivityAt && (
                  <p className="text-xs text-gray-400 mt-1">
                    最近活动：{new Date(usageStats.lastActivityAt).toLocaleString('zh-CN')}
                  </p>
                )}
              </div>
            </div>

            {/* 最近分析历史 */}
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-gray-900">最近分析</h2>
                <button
                  onClick={handleViewAllHistory}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  查看全部
                </button>
              </div>

              {recentHistory.length > 0 ? (
                <div className="space-y-4">
                  {recentHistory.map((item) => (
                    <div key={item.taskId} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex-1">
                        <h3 className="font-medium text-gray-900 line-clamp-1">
                          {item.description || '未填写描述的任务'}
                        </h3>
                        <p className="text-sm text-gray-500 mt-1">
                          {new Date(item.createdAt).toLocaleDateString('zh-CN')}
                        </p>
                      </div>
                      <div className="flex items-center space-x-3">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          item.status === 'completed' ? 'bg-green-100 text-green-800' :
                          item.status === 'failed' ? 'bg-red-100 text-red-800' :
                          item.status === 'processing' ? 'bg-blue-100 text-blue-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {item.statusLabel}
                        </span>
                        {item.status === 'completed' && (
                          <button
                            onClick={() => navigate(`/report/${item.taskId}`)}
                            className="text-sm text-blue-600 hover:text-blue-700"
                          >
                            查看报告
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-gray-500">暂无分析记录</p>
                  <button
                    onClick={() => navigate('/')}
                    className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    开始第一次分析
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* 右侧会员信息 */}
          <div className="space-y-6">
            {/* 会员等级卡片 */}
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">会员等级</h2>

              <div
                className="rounded-lg p-4 mb-4"
                style={{ backgroundColor: `${membershipDisplay.color}10` }}
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-semibold" style={{ color: membershipDisplay.color }}>
                    {membershipDisplay.name}
                  </h3>
                  <span
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium"
                    style={{
                      backgroundColor: membershipDisplay.color,
                      color: 'white'
                    }}
                  >
                    {membershipDisplay.badge}
                  </span>
                </div>
                <p className="text-sm text-gray-600 mb-4">{membershipDisplay.description}</p>

                <div className="space-y-2">
                  {featureList.map((feature, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      <span className="text-sm text-gray-700">{feature}</span>
                    </div>
                  ))}
                </div>
              </div>

              {profile.membershipLevel !== MembershipLevel.ENTERPRISE && membershipInfo.upgradeOptions.length > 0 && (
                <button
                  onClick={handleUpgrade}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                >
                  升级会员
                </button>
              )}
            </div>

            {/* 快捷操作 */}
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">快捷操作</h2>

              <div className="space-y-3">
                <button
                  onClick={() => navigate('/settings')}
                  className="w-full text-left px-4 py-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div className="font-medium text-gray-900">账户设置</div>
                  <div className="text-sm text-gray-500">修改密码、安全设置</div>
                </button>

                <button
                  onClick={handleViewAllHistory}
                  className="w-full text-left px-4 py-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div className="font-medium text-gray-900">分析历史</div>
                  <div className="text-sm text-gray-500">查看所有分析记录</div>
                </button>

                <button
                  onClick={() => navigate('/billing')}
                  className="w-full text-left px-4 py-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div className="font-medium text-gray-900">账单管理</div>
                  <div className="text-sm text-gray-500">查看账单、支付记录</div>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
};

export default ProfilePage;
