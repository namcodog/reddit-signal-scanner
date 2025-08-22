/**
 * Reddit Signal Scanner - 主应用组件
 * 基于 Linus Torvalds 设计哲学：极简用户旅程
 *
 * TODO: 需要prd05-01完成后实现具体内容
 */

import React from "react";

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <header className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Reddit Signal Scanner
          </h1>
          <p className="text-xl text-gray-600">
            30秒输入，5分钟分析，找到你的目标客户在Reddit上的真实声音
          </p>
        </header>

        <main className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg shadow-lg p-6">
            <p className="text-center text-gray-500">应用正在开发中...</p>
          </div>
        </main>
      </div>
    </div>
  );
};

export default App;
