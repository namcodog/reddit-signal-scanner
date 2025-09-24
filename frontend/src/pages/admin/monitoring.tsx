import { useEffect, useState } from 'react';
import { getAdminSystemMetrics, type AdminSystemMetrics } from '../../services/adminApi';
import { showToast } from '../../utils/toast';

export default function AdminMonitoringPage() {
  const [metrics, setMetrics] = useState<AdminSystemMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadMetrics(): Promise<void> {
    setLoading(true);
    try {
      const res = await getAdminSystemMetrics();
      setMetrics(res.data);
      setLoading(false);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '未知错误';
      setError(message);
      setLoading(false);
      showToast(`加载系统指标失败：${message}`, 'error');
    }
  }

  useEffect(() => {
    void loadMetrics();
  }, []);

  if (loading) {
    return <div>系统指标加载中...</div>;
  }

  if (error) {
    return (
      <div>
        系统指标加载失败：{error}
        <button onClick={() => void loadMetrics()} style={{ marginLeft: 12 }}>重试</button>
      </div>
    );
  }

  if (!metrics) {
    return <div>暂无指标数据</div>;
  }

  const { queue, durations } = metrics;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-gray-900">系统指标</h2>
        <div className="space-x-3 text-sm text-gray-600">
          <span>统计时间：{new Date(metrics.generated_at).toLocaleString()}</span>
          <button onClick={() => void loadMetrics()} className="rounded bg-blue-600 px-3 py-1 text-white">刷新</button>
        </div>
      </div>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">待处理</div>
          <div className="text-2xl font-bold text-gray-900">{queue.pending}</div>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">处理中</div>
          <div className="text-2xl font-bold text-gray-900">{queue.processing}</div>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">近1小时完成</div>
          <div className="text-2xl font-bold text-gray-900">{queue.completed_last_hour}</div>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">近1小时失败</div>
          <div className="text-2xl font-bold text-gray-900">{queue.failed_last_hour}</div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">平均耗时</div>
          <div className="text-2xl font-bold text-gray-900">{durations.average.toFixed(1)}s</div>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">P50 耗时</div>
          <div className="text-2xl font-bold text-gray-900">{durations.p50.toFixed(1)}s</div>
        </div>
        <div className="rounded-lg bg-white p-4 shadow">
          <div className="text-sm text-gray-500">P95 耗时</div>
          <div className="text-2xl font-bold text-gray-900">{durations.p95.toFixed(1)}s</div>
        </div>
      </section>
    </div>
  );
}
