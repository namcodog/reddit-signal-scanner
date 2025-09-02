/**
 * Reddit Signal Scanner - 主应用组件
 * 基于 Linus Torvalds 设计哲学：极简用户旅程
 * 
 * 架构设计：三页面SPA
 * - 输入页 (/) : 30秒完成产品描述输入
 * - 进度页 (/analysis/:taskId) : 5分钟等待，SSE实时反馈
 * - 报告页 (/report/:taskId) : 一目了然的结构化洞察
 * 
 * @author Reddit Signal Scanner Team
 * @version 1.0.0 - PRD-05基础架构实现
 */

import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import ErrorBoundary from "@/components/ErrorBoundary";
import { SecureAuthProvider } from "@/hooks/useAuth.secure";

// 占位组件，将在后续PRD任务中实现
const InputPage = React.lazy(() => import("@/pages/InputPage"));
const AnalysisPage = React.lazy(() => import("@/pages/AnalysisPage"));  
const ReportPage = React.lazy(() => import("@/pages/ReportPage"));
const NotFoundPage = React.lazy(() => import("@/pages/NotFoundPage"));

/**
 * App主组件
 * 实现URL驱动的无状态设计，支持页面刷新后状态恢复
 */
const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <SecureAuthProvider>
        <Router>
          <div className="min-h-screen bg-gray-50">
            <React.Suspense
              fallback={
                <div className="flex items-center justify-center min-h-screen">
                  <div className="text-lg text-gray-600">加载中...</div>
                </div>
              }
            >
              <Routes>
                {/* 输入页：产品描述输入，30秒完成 */}
                <Route path="/" element={<InputPage />} />
                
                {/* 进度页：SSE实时进度推送，5分钟等待 */}
                <Route path="/analysis/:taskId" element={<AnalysisPage />} />
                
                {/* 报告页：结构化分析结果展示 */}
                <Route path="/report/:taskId" element={<ReportPage />} />
                
                {/* 404错误页面 */}
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </React.Suspense>
          </div>
        </Router>
      </SecureAuthProvider>
    </ErrorBoundary>
  );
};

export default App;
