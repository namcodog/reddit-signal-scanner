/**
 * 404错误页面 - 优雅的错误处理
 * 基于 Linus 实用主义：简单直接的错误恢复
 */

import React from 'react';
import { Link } from 'react-router-dom';

/**
 * 404页面未找到组件
 * 为用户提供清晰的导航选项
 */
const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="text-center">
        <div className="text-9xl font-bold text-gray-400 mb-4">404</div>

        <h1 className="text-2xl font-bold text-gray-900 mb-4">页面未找到</h1>

        <p className="text-gray-600 mb-8 max-w-md">
          抱歉，您要访问的页面不存在。可能是链接错误或页面已被移动。
        </p>

        <div className="space-x-4">
          <Link
            to="/"
            className="inline-flex items-center px-4 py-2 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            返回首页
          </Link>

          <button
            onClick={() => window.history.back()}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-base font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            返回上页
          </button>
        </div>

        <div className="mt-12 text-sm text-gray-500">
          <p>Reddit Signal Scanner</p>
          <p>基于 Linus Torvalds 设计哲学</p>
        </div>
      </div>
    </div>
  );
};

export default NotFoundPage;
