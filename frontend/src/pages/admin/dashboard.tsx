import { useEffect, useState } from 'react';
import {
  getAdminDashboardOverview,
  type AdminDashboardOverview,
  type AdminRecentTask,
  type AdminUserSummary,
} from '../../services/adminApi';
import { showToast } from '../../utils/toast';

interface LoadingState {
  loading: boolean;
  error?: string;
}

const statusLabels: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  completed: '已完成',
  failed: '已失败',
  dead_letter: '死信',
};

function formatDuration(seconds?: number | null): string {
  if (!seconds && seconds !== 0) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const rem = Math.round(seconds % 60);
  return `${minutes}m ${rem}s`;
}

export default function AdminDashboardPage() {
  const [state, setState] = useState<LoadingState>({ loading: true });
  const [data, setData] = useState<AdminDashboardOverview | null>(null);
  const [traceId, setTraceId] = useState<string | undefined>(undefined);

  async function loadOverview(): Promise<void> {
    setState({ loading: true });
    try {
      const res = await getAdminDashboardOverview();
      setData(res.data);
      setTraceId(res.trace_id);
      setState({ loading: false });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '未知错误';
      setState({ loading: false, error: message });
      showToast(`加载仪表盘失败：${message}`, 'error');
    }
  }

  useEffect(() => {
    void loadOverview();
  }, []);

  if (state.loading) {
    return <div>仪表盘加载中...</div>;
  }

  if (state.error) {
    return (
      <div>
        仪表盘加载失败：{state.error}
        <button onClick={() => void loadOverview()} style={{ marginLeft: 12 }}>重试</button>
      </div>
    );
  }

  if (!data) {
    return <div>暂无数据</div>;
  }

  const renderUsers = (users: AdminUserSummary[]): JSX.Element => (
    <table className="min-w-full divide-y divide-gray-200 bg-white">
      <thead className="bg-gray-50">
        <tr>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">会员</th>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">总任务</th>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">进行中</th>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">失败</th>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">最近活动</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-200">
        {users.map(user => (
          <tr key={user.user_id}>
            <td className="px-4 py-2 text-sm text-gray-900">{user.email}</td>
            <td className="px-4 py-2 text-sm text-gray-600 uppercase">{user.membership_level}</td>
            <td className="px-4 py-2 text-sm text-gray-900">{user.total_tasks}</td>
            <td className="px-4 py-2 text-sm text-gray-900">{user.active_tasks}</td>
            <td className="px-4 py-2 text-sm text-gray-900">{user.failed_tasks}</td>
            <td className="px-4 py-2 text-sm text-gray-600">{user.last_activity_at ? new Date(user.last_activity_at).toLocaleString() : '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  const renderTasks = (tasks: AdminRecentTask[]): JSX.Element => (
    <table className="min-w-full divide-y divide-gray-200 bg-white">
      <thead className="bg-gray-50">
        <tr>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">任务ID</th>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">创建时间</th>
          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">耗时</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-200">
        {tasks.map(task => (
          <tr key={task.task_id}>
            <td className="px-4 py-2 text-sm text-blue-600">{task.task_id}</td>
            <td className="px-4 py-2 text-sm text-gray-900">{task.user_email}</td>
            <td className="px-4 py-2 text-sm text-gray-900">{statusLabels[task.status] ?? task.status}</td>
            <td className="px-4 py-2 text-sm text-gray-600">{new Date(task.created_at).toLocaleString()}</td>
            <td className="px-4 py-2 text-sm text-gray-600">{formatDuration(task.duration_seconds)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  const { status_counts: counts } = data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-gray-900">管理员仪表盘</h2>
        <div className="space-x-3 text-sm text-gray-500">
          {traceId ? <span>trace_id: {traceId}</span> : null}
          <button onClick={() => void loadOverview()} className="rounded bg-blue-600 px-3 py-1 text-white">刷新</button>
        </div>
      </div>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-5">
        {Object.entries(counts).map(([key, value]) => (
          <div key={key} className="rounded-lg bg-white p-4 shadow">
            <div className="text-sm text-gray-500">{statusLabels[key] ?? key}</div>
            <div className="text-2xl font-bold text-gray-900">{value}</div>
          </div>
        ))}
      </section>

      <section>
        <h3 className="mb-2 text-lg font-semibold text-gray-900">用户概览</h3>
        {renderUsers(data.users)}
      </section>

      <section>
        <h3 className="mb-2 text-lg font-semibold text-gray-900">最新任务</h3>
        {renderTasks(data.recent_tasks)}
      </section>
    </div>
  );
}
