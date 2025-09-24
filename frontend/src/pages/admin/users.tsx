import { useEffect, useMemo, useState } from 'react';
import { getAdminDashboardOverview, type AdminUserSummary } from '../../services/adminApi';
import { showToast } from '../../utils/toast';

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  async function loadUsers(): Promise<void> {
    setLoading(true);
    try {
      const res = await getAdminDashboardOverview({ user_limit: 50, task_limit: 5 });
      setUsers(res.data.users);
      setLoading(false);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '未知错误';
      setError(message);
      setLoading(false);
      showToast(`加载用户列表失败：${message}`, 'error');
    }
  }

  useEffect(() => {
    void loadUsers();
  }, []);

  const filteredUsers = useMemo(() => {
    if (!query) return users;
    const q = query.toLowerCase();
    return users.filter(user => user.email.toLowerCase().includes(q));
  }, [users, query]);

  if (loading) {
    return <div>用户列表加载中...</div>;
  }

  if (error) {
    return (
      <div>
        用户列表加载失败：{error}
        <button onClick={() => void loadUsers()} style={{ marginLeft: 12 }}>重试</button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold text-gray-900">用户列表</h2>
        <div className="space-x-3">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="按邮箱搜索"
            className="rounded border border-gray-300 px-3 py-1 text-sm"
          />
          <button onClick={() => void loadUsers()} className="rounded bg-blue-600 px-3 py-1 text-sm text-white">刷新</button>
        </div>
      </div>

      <table className="min-w-full divide-y divide-gray-200 bg-white">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">用户</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">会员等级</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">总任务</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">进行中</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">失败</th>
            <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">最近活动</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200">
          {filteredUsers.map(user => (
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
    </div>
  );
}
