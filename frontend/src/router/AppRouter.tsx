/**
 * 应用路由配置 - 基于v0设计理念
 * 核心：URL驱动的无状态设计
 */

import React, { Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import { ROUTES } from '@/types/router.types';
import LoadingFallback from '@/components/LoadingFallback';
import Navigation from '@/components/Navigation';
import ProtectedRoute from './ProtectedRoute';

// 懒加载页面组件
const InputPage = React.lazy(() => import('@/pages/InputPage'));  // 修复：使用包含"Reddit Signal Scanner"文本的正确组件
const WaitingPage = React.lazy(() => import('@/pages/WaitingPage'));
const ReportPage = React.lazy(() => import('@/pages/ReportPageV0'));
const NotFoundPage = React.lazy(() => import('@/pages/NotFoundPage'));

const AppRouter: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* 全局导航组件 */}
      <Navigation />
      
      {/* 路由内容区 */}
      <Suspense fallback={<LoadingFallback />}>
        <Routes>
          {/* 输入页 - 公开访问 */}
          <Route path={ROUTES.INPUT} element={<InputPage />} />
          
          {/* 分析页 - 需要有效的taskId */}
          <Route 
            path={ROUTES.ANALYSIS} 
            element={
              <ProtectedRoute requireTaskId>
                <WaitingPage />
              </ProtectedRoute>
            } 
          />
          
          {/* 报告页 - 需要有效的taskId和完成状态 */}
          <Route 
            path={ROUTES.REPORT} 
            element={
              <ProtectedRoute requireTaskId requireCompleted>
                <ReportPage />
              </ProtectedRoute>
            } 
          />
          
          {/* 404处理 */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </div>
  );
};

export default AppRouter;