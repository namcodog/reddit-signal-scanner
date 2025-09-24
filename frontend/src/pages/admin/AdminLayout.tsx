import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { ROUTES } from '@/types/router.types';
import { useAdminSession } from '@/hooks/useAdminSession';

const navItems: Array<{ label: string; to: string; key: string }> = [
  { label: '仪表盘', to: ROUTES.ADMIN_DASHBOARD, key: 'dashboard' },
  { label: '社区验收', to: ROUTES.ADMIN_COMMUNITIES, key: 'communities' },
  { label: '算法验收', to: ROUTES.ADMIN_ANALYSIS, key: 'analysis' },
  { label: '用户反馈', to: ROUTES.ADMIN_FEEDBACK, key: 'feedback' },
  { label: '用户列表', to: ROUTES.ADMIN_USERS, key: 'users' },
  { label: '任务监控', to: ROUTES.ADMIN_MONITOR, key: 'monitor' },
  { label: '内容审核', to: ROUTES.ADMIN_MODERATION, key: 'moderation' },
  { label: '统计中心', to: ROUTES.ADMIN_STATS, key: 'stats' },
];

const AdminLayout: React.FC = () => {
  const { session } = useAdminSession();

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="flex items-center justify-between border-b bg-white px-6 py-4 shadow-sm">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Reddit Signal Scanner · Admin</h1>
          <p className="text-sm text-gray-500">联调大冒险，管理员专属后台</p>
        </div>
        {session ? (
          <div className="text-right text-sm text-gray-600">
            <div>{session.email ?? session.user_id}</div>
            <div className="text-xs uppercase tracking-wide">角色：{session.roles.join(', ') || '未知'}</div>
          </div>
        ) : null}
      </header>

      <div className="flex">
        <nav className="w-56 border-r bg-white px-4 py-6">
          <ul className="space-y-2 text-sm">
            {navItems.map(item => (
              <li key={item.key}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `block rounded px-3 py-2 font-medium transition-colors ${
                      isActive ? 'bg-blue-600 text-white' : 'text-gray-700 hover:bg-gray-100'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <main className="flex-1 bg-gray-50 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;
