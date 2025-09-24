import { useEffect, useState } from 'react';
import {
  getBehaviorSummary,
  getUsageStats,
  getErrorSummary,
  getPerformanceMetrics,
  type BehaviorSummary,
  type UsageStats,
  type ErrorLogSummary,
  type PerformanceMetrics,
} from '../../services/adminApi';
import { showToast } from '../../utils/toast';

interface StatsState {
  behavior: BehaviorSummary | null;
  usage: UsageStats | null;
  errors: ErrorLogSummary | null;
  performance: PerformanceMetrics | null;
}

export default function AdminStatsPage() {
  const [state, setState] = useState<StatsState>({
    behavior: null,
    usage: null,
    errors: null,
    performance: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadStats(): Promise<void> {
    setLoading(true);
    try {
      const [behaviorRes, usageRes, errorRes, performanceRes] = await Promise.all([
        getBehaviorSummary(),
        getUsageStats(),
        getErrorSummary(),
        getPerformanceMetrics(),
      ]);
      setState({
        behavior: behaviorRes.data,
        usage: usageRes.data,
        errors: errorRes.data,
        performance: performanceRes.data,
      });
      setLoading(false);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '未知错误';
      setError(message);
      setLoading(false);
      showToast(`加载统计数据失败：${message}`, 'error');
    }
  }

  useEffect(() => {
    void loadStats();
  }, []);

  if (loading) {
    return <div>统计数据加载中...</div>;
  }

  if (error) {
    return (
      <div>
        统计数据加载失败：{error}
        <button onClick={() => void loadStats()} style={{ marginLeft: 12 }}>重试</button>
      </div>
    );
  }

  const { behavior, usage, errors, performance } = state;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-gray-900">统计中心</h2>
        <button onClick={() => void loadStats()} className="rounded bg-blue-600 px-3 py-1 text-white">刷新</button>
      </div>

      {behavior && (
        <section className="rounded-lg bg-white p-4 shadow">
          <h3 className="mb-3 text-lg font-semibold text-gray-900">用户行为埋点汇总</h3>
          <div className="text-sm text-gray-600">总事件：{behavior.total_events}</div>
          <ul className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
            {Object.entries(behavior.by_type).map(([type, count]) => (
              <li key={type} className="flex justify-between rounded border border-gray-100 px-3 py-2">
                <span className="capitalize text-gray-700">{type}</span>
                <span className="font-semibold text-gray-900">{count}</span>
              </li>
            ))}
          </ul>
          {behavior.top_reasons.length > 0 && (
            <div className="mt-4">
              <div className="text-sm font-medium text-gray-700">Top原因</div>
              <ul className="mt-1 space-y-1 text-sm text-gray-600">
                {behavior.top_reasons.map(item => (
                  <li key={item.reason} className="flex justify-between">
                    <span>{item.reason}</span>
                    <span>{item.count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {usage && (
        <section className="rounded-lg bg-white p-4 shadow">
          <h3 className="mb-3 text-lg font-semibold text-gray-900">使用统计报表</h3>
          <div className="text-sm text-gray-600">近7天任务：{usage.weekly_tasks} · 活跃用户：{usage.weekly_active_users}</div>
          <table className="mt-3 min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">日期</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">任务数</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">活跃用户</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {usage.daily.map(point => (
                <tr key={point.bucket}>
                  <td className="px-3 py-2 text-sm text-gray-700">{point.bucket}</td>
                  <td className="px-3 py-2 text-sm text-gray-900">{point.tasks_created}</td>
                  <td className="px-3 py-2 text-sm text-gray-900">{point.active_users}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {errors && (
        <section className="rounded-lg bg-white p-4 shadow">
          <h3 className="mb-3 text-lg font-semibold text-gray-900">错误日志聚合</h3>
          <div className="text-sm text-gray-600">失败任务总计：{errors.total_failed}</div>
          <ul className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
            {errors.categories.map(cat => (
              <li key={cat.category} className="rounded border border-gray-100 px-3 py-2 text-sm text-gray-700">
                {cat.category}: {cat.count}
              </li>
            ))}
          </ul>
          <div className="mt-3 text-sm text-gray-600">最近错误</div>
          <ul className="mt-1 space-y-2 text-sm text-gray-600">
            {errors.recent.map(item => (
              <li key={item.task_id} className="rounded border border-gray-100 px-3 py-2">
                <div className="font-semibold text-gray-900">{item.task_id}</div>
                <div>{item.error_message ?? '无错误信息'}</div>
                <div className="text-xs text-gray-500">{item.happened_at ? new Date(item.happened_at).toLocaleString() : ''}</div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {performance && (
        <section className="rounded-lg bg-white p-4 shadow">
          <h3 className="mb-3 text-lg font-semibold text-gray-900">性能监控数据</h3>
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">时间</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">平均耗时(s)</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">P95(s)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {performance.samples.map(sample => (
                <tr key={sample.timestamp}>
                  <td className="px-3 py-2 text-sm text-gray-700">{new Date(sample.timestamp).toLocaleString()}</td>
                  <td className="px-3 py-2 text-sm text-gray-900">{sample.avg_duration.toFixed(1)}</td>
                  <td className="px-3 py-2 text-sm text-gray-900">{sample.p95_duration.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
