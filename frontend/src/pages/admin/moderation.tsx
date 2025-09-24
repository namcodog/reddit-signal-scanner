import { useEffect, useState } from 'react';
import {
  getAdminDashboardOverview,
  moderateTask,
  type AdminRecentTask,
} from '../../services/adminApi';
import { useAdminSession } from '../../hooks/useAdminSession';
import { showToast } from '../../utils/toast';

export default function AdminModerationPage() {
  const [tasks, setTasks] = useState<AdminRecentTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { roles } = useAdminSession();
  const canModerate = roles.includes('operations');

  async function loadTasks(): Promise<void> {
    setLoading(true);
    try {
      const res = await getAdminDashboardOverview({ task_limit: 30 });
      setTasks(res.data.recent_tasks);
      setLoading(false);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '未知错误';
      setError(message);
      setLoading(false);
      showToast(`加载任务列表失败：${message}`, 'error');
    }
  }

  useEffect(() => {
    void loadTasks();
  }, []);

  async function onModerate(task: AdminRecentTask, action: 'reject' | 'delete'): Promise<void> {
    if (!canModerate) {
      showToast('缺少运营权限，无法执行审核操作', 'error');
      return;
    }

    const reason = window.prompt(`请输入对任务 ${task.task_id} 的审核说明`, '');
    setLoading(true);
    try {
      const res = await moderateTask(task.task_id, { action, reason: reason || undefined });
      setTasks(prev =>
        prev.map(item =>
          item.task_id === task.task_id
            ? { ...item, status: res.data.new_status }
            : item
        )
      );
      setLoading(false);
      showToast('审核操作成功', 'success');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '未知错误';
      setLoading(false);
      showToast(`审核失败：${message}`, 'error');
    }
  }

  if (loading) {
    return <div>任务加载中...</div>;
  }

  if (error) {
    return (
      <div>
        任务列表加载失败：{error}
        <button onClick={() => void loadTasks()} style={{ marginLeft: 12 }}>重试</button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-gray-900">内容审核</h2>
        <div className="space-x-3 text-sm text-gray-600">
          {!canModerate && <span>只读模式（缺少运营权限）</span>}
          <button onClick={() => void loadTasks()} className="rounded bg-blue-600 px-3 py-1 text-white">刷新</button>
        </div>
      </div>

      <table className="min-w-full divide-y divide-gray-200 bg-white">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">任务</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {tasks.map(task => (
            <tr key={task.task_id}>
              <td className="px-4 py-2 text-sm text-blue-600">{task.task_id}</td>
              <td className="px-4 py-2 text-sm text-gray-900">{task.user_email}</td>
              <td className="px-4 py-2 text-sm text-gray-900">{task.status}</td>
              <td className="px-4 py-2 text-sm text-gray-900 space-x-2">
                <button
                  disabled={!canModerate}
                  onClick={() => void onModerate(task, 'reject')}
                  className="rounded bg-yellow-500 px-3 py-1 text-white disabled:opacity-50"
                >
                  拒绝
                </button>
                <button
                  disabled={!canModerate}
                  onClick={() => void onModerate(task, 'delete')}
                  className="rounded bg-red-600 px-3 py-1 text-white disabled:opacity-50"
                >
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
