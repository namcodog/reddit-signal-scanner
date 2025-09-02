/**
 * 分析报告页面 - 结构化洞察展示
 * 基于 Linus 简洁原则：清晰易懂的价值输出
 */

import React from 'react';
import { useParams } from 'react-router-dom';

/**
 * 分析报告展示页面
 * 显示结构化的Reddit信号分析结果
 */
const ReportPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">分析报告</h1>
          <p className="text-gray-600">任务ID: {taskId || '未知'}</p>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8">
          <div className="text-center text-gray-500 py-12">
            <div className="text-6xl mb-4">📊</div>
            <h2 className="text-xl font-semibold mb-2">报告页面开发中</h2>
            <p className="mb-4">将在PRD-05-05任务中实现完整的数据可视化功能</p>
            <div className="text-sm text-gray-400">
              包含：执行摘要、痛点分析、竞品情报、机会矩阵
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportPage;
