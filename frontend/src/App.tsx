/**
 * Reddit Signal Scanner - 主应用组件
 * 基于 Linus Torvalds 设计哲学：极简用户旅程
 * 
 * PRD05-06 更新：集成新路由导航系统
 * - 统一的路由管理和类型安全
 * - 优雅的面包屑导航
 * - 页面过渡动画
 * - 路由保护和权限控制
 *
 * @author Reddit Signal Scanner Team
 * @version 2.0.0 - PRD-05-06 路由导航系统
 */

import React from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import ErrorBoundary from '@/components/ErrorBoundary';
import { SecureAuthProvider } from '@/hooks/useAuth.secure';
import AppRouter from '@/router/AppRouter';
import PageTransition from '@/components/PageTransition';
import '@/styles/transitions.css';

/**
 * App主组件 - 集成新路由系统
 * 实现100%类型安全的导航体验
 */
const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <SecureAuthProvider>
        <Router>
          <PageTransition>
            <AppRouter />
          </PageTransition>
        </Router>
      </SecureAuthProvider>
    </ErrorBoundary>
  );
};

export default App;
