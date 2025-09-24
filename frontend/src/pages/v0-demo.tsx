/**
 * V0界面1:1还原演示页面
 *
 * 这个页面展示了完全还原的Reddit V0界面效果
 * 使用真实API适配器，但保持设计版的视觉效果
 *
 * 访问地址: http://localhost:3008/v0-demo
 */

import React from 'react';
import RedditScannerPageV2 from '@/components/v0/RedditScannerPageV2';

const V0DemoPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-background">
      <RedditScannerPageV2 />
    </div>
  );
};

export default V0DemoPage;
