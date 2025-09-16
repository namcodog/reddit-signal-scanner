/**
 * 路由保护组件 - 权限和状态验证
 */

import React, { useEffect, useState } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import { ROUTES } from '@/types/router.types';
import { validateTaskId } from '@/services/api.client';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireTaskId?: boolean;
  requireCompleted?: boolean;
  requireAuth?: boolean;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requireTaskId = false,
  requireCompleted: _requireCompleted = false, // 预留：后续用于检查任务完成状态
  requireAuth: _requireAuth = false,           // 预留：后续用于身份验证
}) => {
  const { taskId } = useParams<{ taskId: string }>();
  const [isValid, setIsValid] = useState<boolean | null>(null);
  
  useEffect(() => {
    const checkValidity = async (): Promise<void> => {
      if (!requireTaskId) {
        setIsValid(true);
        return;
      }
      
      if (!taskId) {
        setIsValid(false);
        return;
      }
      
      try {
        const valid = await validateTaskId(taskId);
        setIsValid(valid);
      } catch {
        setIsValid(false);
      }
    };
    
    checkValidity();
  }, [taskId, requireTaskId]);
  
  // 加载中
  if (isValid === null) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">验证中...</p>
        </div>
      </div>
    );
  }
  
  // 无效任务ID
  if (!isValid) {
    return <Navigate to={ROUTES.INPUT} replace />;
  }
  
  return <>{children}</>;
};

export default ProtectedRoute;