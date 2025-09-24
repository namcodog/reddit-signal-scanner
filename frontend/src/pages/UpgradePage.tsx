import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import { userService } from '@/services/user.service';
import {
  MembershipInfo,
  MembershipLevel,
  MembershipUpgradeRequest,
  MEMBERSHIP_DISPLAY,
  MEMBERSHIP_FEATURES
} from '@/types/user.types';

const UpgradePage: React.FC = () => {
  const navigate = useNavigate();
  const [membershipInfo, setMembershipInfo] = useState<MembershipInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<MembershipLevel | null>(null);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');
  const currentMembershipLevel = membershipInfo?.level ?? null;

useEffect(() => {
  loadMembershipInfo();
}, []);

useEffect(() => {
  if (membershipInfo && membershipInfo.upgradeOptions.length > 0) {
    setSelectedPlan(membershipInfo.upgradeOptions[0]);
  }
}, [membershipInfo]);

  const loadMembershipInfo = async () => {
    try {
      setLoading(true);
      setError(null);
      const info = await userService.getMembershipInfo();
      setMembershipInfo(info);
    } catch (err) {
      setError('加载会员信息失败');
      console.error('Failed to load membership info:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async () => {
    if (!selectedPlan || selectedPlan === currentMembershipLevel) return;

    try {
      setUpgrading(true);
      const request: MembershipUpgradeRequest = {
        targetLevel: selectedPlan,
      };

      await userService.upgradeMembership(request);

      // 升级成功，返回个人中心
      navigate('/profile', {
        state: { message: '会员升级成功！' }
      });
    } catch (err) {
      setError('升级失败，请重试');
      console.error('Failed to upgrade membership:', err);
    } finally {
      setUpgrading(false);
    }
  };

  const getPlanPricing = (level: MembershipLevel, cycle: 'monthly' | 'yearly') => {
    const basePrices = {
      [MembershipLevel.FREE]: 0,
      [MembershipLevel.PRO]: cycle === 'monthly' ? 99 : 999,
      [MembershipLevel.ENTERPRISE]: cycle === 'monthly' ? 299 : 2999,
    };
    return basePrices[level];
  };

  const getPlanSavings = (level: MembershipLevel) => {
    const monthlyPrice = getPlanPricing(level, 'monthly');
    const yearlyPrice = getPlanPricing(level, 'yearly');
    const monthlyCost = monthlyPrice * 12;
    return monthlyCost - yearlyPrice;
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
              onClick={loadMembershipInfo}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              重试
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!membershipInfo) {
    return null;
  }

  const currentLevel = membershipInfo.level;
  const upgradeableLevels = new Set<MembershipLevel>(membershipInfo.upgradeOptions);
  const planLevels = Object.values(MembershipLevel) as MembershipLevel[];

  return (
    <AppShell>
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 页面标题 */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">选择适合您的会员计划</h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            升级您的会员等级，解锁更多强大功能，享受更好的分析体验
          </p>
        </div>

        {/* 计费周期选择 */}
        <div className="flex justify-center mb-8">
          <div className="bg-gray-100 rounded-lg p-1 inline-flex">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={`px-6 py-2 rounded-md text-sm font-medium transition-colors ${
                billingCycle === 'monthly'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              按月付费
            </button>
            <button
              onClick={() => setBillingCycle('yearly')}
              className={`px-6 py-2 rounded-md text-sm font-medium transition-colors relative ${
                billingCycle === 'yearly'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              按年付费
              <span className="absolute -top-2 -right-2 bg-green-500 text-white text-xs px-1 rounded">
                省20%
              </span>
            </button>
          </div>
        </div>

        {/* 当前计划显示 */}
        <div className="mb-8 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-blue-900">
                当前计划: {MEMBERSHIP_DISPLAY[currentLevel].name}
              </h3>
              <p className="text-blue-700">
                {MEMBERSHIP_DISPLAY[currentLevel].description}
              </p>
            </div>
            <span
              className="inline-flex items-center px-4 py-2 rounded-full text-sm font-medium"
              style={{
                backgroundColor: MEMBERSHIP_DISPLAY[currentLevel].color,
                color: 'white'
              }}
            >
              {MEMBERSHIP_DISPLAY[currentLevel].badge}
            </span>
          </div>
        </div>

        {/* 计划卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
          {planLevels.map((level) => {
            const display = MEMBERSHIP_DISPLAY[level];
            const features = MEMBERSHIP_FEATURES[level];
            const price = getPlanPricing(level, billingCycle);
            const savings = billingCycle === 'yearly' ? getPlanSavings(level) : 0;
            const isCurrentPlan = level === currentLevel;
            const isAvailable = isCurrentPlan || upgradeableLevels.has(level);
            const isSelected = selectedPlan === level;

            return (
              <div
                key={level}
                className={`relative bg-white rounded-2xl shadow-lg border-2 transition-all duration-200 ${
                  isSelected
                    ? 'border-blue-500 shadow-xl'
                    : isCurrentPlan
                    ? 'border-gray-300 opacity-50'
                    : 'border-gray-200 hover:border-gray-300'
                } ${level === MembershipLevel.PRO ? 'transform scale-105' : ''}`}
              >
                {level === MembershipLevel.PRO && (
                  <div className="absolute -top-4 left-1/2 transform -translate-x-1/2">
                    <span className="bg-blue-500 text-white px-4 py-1 rounded-full text-sm font-medium">
                      最受欢迎
                    </span>
                  </div>
                )}

                <div className="p-8">
                  {/* 计划标题 */}
                  <div className="text-center mb-6">
                    <h3 className="text-2xl font-bold text-gray-900 mb-2">
                      {display.name}
                    </h3>
                    <p className="text-gray-600">{display.description}</p>
                  </div>

                  {/* 价格 */}
                  <div className="text-center mb-6">
                    <div className="flex items-baseline justify-center">
                      <span className="text-5xl font-bold text-gray-900">
                        ¥{price}
                      </span>
                      {price > 0 && (
                        <span className="text-gray-500 ml-1">
                          /{billingCycle === 'monthly' ? '月' : '年'}
                        </span>
                      )}
                    </div>
                    {billingCycle === 'yearly' && savings > 0 && (
                      <p className="text-green-600 text-sm mt-2">
                        相比按月付费节省 ¥{savings}
                      </p>
                    )}
                  </div>

                  {/* 功能列表 */}
                  <div className="space-y-4 mb-8">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-700">月度分析配额</span>
                      <span className="font-semibold text-gray-900">
                        {features.monthlyQuota === null ? '无限制' : `${features.monthlyQuota} 次`}
                      </span>
                    </div>

                    {features.features.map((feature, index) => (
                      <div key={index} className="flex items-center space-x-3">
                        <svg className="w-5 h-5 text-green-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                        <span className="text-gray-700">{feature}</span>
                      </div>
                    ))}

                    <div className="flex items-center space-x-3">
                      <svg className={`w-5 h-5 flex-shrink-0 ${features.canExportPdf ? 'text-green-500' : 'text-gray-300'}`} fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      <span className={features.canExportPdf ? 'text-gray-700' : 'text-gray-400'}>
                        PDF报告导出
                      </span>
                    </div>

                    <div className="flex items-center space-x-3">
                      <svg className={`w-5 h-5 flex-shrink-0 ${features.hasRealtimeUpdates ? 'text-green-500' : 'text-gray-300'}`} fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      <span className={features.hasRealtimeUpdates ? 'text-gray-700' : 'text-gray-400'}>
                        实时进度更新
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-gray-700">分析优先级</span>
                      <span className={`font-semibold ${
                        features.priority === 'highest' ? 'text-purple-600' :
                        features.priority === 'high' ? 'text-blue-600' :
                        'text-gray-600'
                      }`}>
                        {features.priority === 'highest' ? '最高' :
                         features.priority === 'high' ? '高' : '标准'}
                      </span>
                    </div>
                  </div>

                  {/* 选择按钮 */}
                  <div className="text-center">
                    {isCurrentPlan ? (
                      <div className="py-3 px-4 bg-gray-100 text-gray-500 rounded-lg font-medium">
                        当前计划
                      </div>
                    ) : isAvailable ? (
                      <button
                        onClick={() => setSelectedPlan(level)}
                        disabled={upgrading}
                        className={`w-full py-3 px-4 rounded-lg font-medium transition-colors ${
                          isSelected
                            ? 'bg-blue-600 text-white hover:bg-blue-700'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        {isSelected ? '已选择' : '选择此计划'}
                      </button>
                    ) : (
                      <div className="py-3 px-4 bg-gray-100 text-gray-500 rounded-lg font-medium">
                        不可升级
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* 确认升级按钮 */}
        {selectedPlan && (
          <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg p-4">
            <div className="max-w-4xl mx-auto flex items-center justify-between">
              <div className="text-left">
                <h3 className="font-semibold text-gray-900">
                  升级到 {MEMBERSHIP_DISPLAY[selectedPlan].name}
                </h3>
                <p className="text-gray-600">
                  ¥{getPlanPricing(selectedPlan, billingCycle)} / {billingCycle === 'monthly' ? '月' : '年'}
                </p>
              </div>
              <div className="flex space-x-4">
                <button
                  onClick={() => setSelectedPlan(null)}
                  className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  onClick={handleUpgrade}
                  disabled={upgrading}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {upgrading ? '升级中...' : '确认升级'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 常见问题 */}
        <div className="mt-16 bg-gray-50 rounded-2xl p-8">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">常见问题</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <h3 className="font-semibold text-gray-900 mb-2">升级后何时生效？</h3>
              <p className="text-gray-600">
                升级后立即生效，您可以马上享受新等级的所有功能和配额。
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-gray-900 mb-2">可以随时取消吗？</h3>
              <p className="text-gray-600">
                可以随时取消，取消后当前计费周期结束时会自动降级。
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-gray-900 mb-2">支持哪些支付方式？</h3>
              <p className="text-gray-600">
                支持支付宝、微信支付、银行卡等多种支付方式。
              </p>
            </div>

            <div>
              <h3 className="font-semibold text-gray-900 mb-2">配额如何计算？</h3>
              <p className="text-gray-600">
                每次成功完成的分析计入配额，失败的分析不计入。配额每月1号重置。
              </p>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
};

export default UpgradePage;
