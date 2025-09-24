import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { ROUTES } from '@/types/router.types';
import { useSecureAuth } from '@/hooks/useSecureAuth';
import { useAdminSession } from '@/hooks/useAdminSession';
import type { AdminRole } from '@/services/adminApi';

interface AdminRouteProps {
  children: React.ReactNode;
  requiredRole?: AdminRole;
}

const AdminRoute: React.FC<AdminRouteProps> = ({ children, requiredRole }) => {
  const location = useLocation();
  const { isAuthenticated, isLoading: authLoading } = useSecureAuth();
  const { loading, session, error, roles } = useAdminSession();

  if (authLoading || loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-center text-gray-600">管理员身份验证中...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // 重定向到首页，让AppShell处理认证对话框
    return <Navigate to={ROUTES.INPUT} state={{ from: location }} replace />;
  }

  if (error) {
    const message = error.message ?? 'unknown error';
    if (message.includes('HTTP 401') || message.includes('HTTP 403')) {
      // 重定向到首页，让AppShell处理认证对话框
      return <Navigate to={ROUTES.INPUT} state={{ from: location }} replace />;
    }
    return (
      <div className="p-8 text-center text-red-600">
        管理后台加载失败：{message}
      </div>
    );
  }

  if (!session) {
    return (
      <div className="p-8 text-center text-red-600">
        未获取到管理员会话，请刷新后重试。
      </div>
    );
  }

  if (requiredRole && !roles.includes(requiredRole)) {
    return (
      <div className="p-8 text-center text-red-600">
        当前账号缺少 {requiredRole} 权限，无法访问此页面。
      </div>
    );
  }

  return <>{children}</>;
};

export default AdminRoute;
