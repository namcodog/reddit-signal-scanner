/**
 * 输入页面 - 基于v0设计的增强版本 + 响应式优化
 * 整合了v0界面设计的优秀特性，同时满足PRD-05要求
 * 
 * 主要改进：
 * - 字符限制从500提升到2000
 * - API端点适配到项目标准
 * - 保持v0设计的优秀用户体验
 * - 支持Mock数据开发模式
 * - 响应式设计和移动端优化
 * - 触摸手势支持和v0级别交互体验
 */

import React, { useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, LightbulbIcon } from 'lucide-react';
import InputValidator from '@/utils/validation';
import HttpClient from '@/utils/httpClient';
import configService from '@/services/config.service';
import { useDeviceDetection } from '@/hooks/useDeviceDetection';
import { useSwipeGesture } from '@/hooks/useSwipeGesture';
import ResponsiveLayout from '@/components/ResponsiveLayout';
import ResponsiveButton from '@/components/ResponsiveButton';
import logger from '@/utils/logger';

interface ProductExample {
  title: string;
  description: string;
}

const InputPageV0: React.FC = () => {
  const navigate = useNavigate();
  const [description, setDescription] = useState('');
  const [charCount, setCharCount] = useState(0);
  const [isValid, setIsValid] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string>('');
  
  // 响应式设计增强
  const { type, isTouchDevice } = useDeviceDetection();
  const containerRef = useRef<HTMLDivElement>(null);

  // PRD要求：字符限制调整为2000
  const MAX_CHARS = 2000;
  const MIN_CHARS = 10;

  // 示例产品描述
  const examples: ProductExample[] = [
    {
      title: 'SaaS工具',
      description: '一个面向远程团队的项目管理工具，集成Slack并自动跟踪任务时间。它使用AI来预测项目延期风险，并提供智能的资源分配建议。支持看板、甘特图和敏捷开发模式，帮助团队提高30%的交付效率。',
    },
    {
      title: '移动应用',
      description: '一个健身应用，根据可用设备和时间限制创建个性化锻炼计划。通过机器学习分析用户的运动模式，提供实时的姿势纠正建议。集成Apple Health和Google Fit，支持社交挑战和虚拟教练功能。',
    },
    {
      title: '电商平台',
      description: '一个专注于可持续时尚品牌的在线市场，重视透明度和道德制造。每个产品都配有完整的供应链追溯信息，碳足迹计算，以及材料可持续性评分。支持虚拟试穿和个性化推荐。',
    },
  ];

  // 处理输入变化
  const handleDescriptionChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value;
    const characters = text.length;

    setDescription(text);
    setCharCount(characters);
    setIsValid(characters >= MIN_CHARS && characters <= MAX_CHARS);
    
    // 清除之前的错误
    if (error) {
      setError('');
    }
  }, [error]);

  // 提交分析请求
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!isValid || !description.trim()) {
      setError('请输入有效的产品描述（10-2000字符）');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      // 使用项目标准的验证器
      const validation = InputValidator.validateProductDescription(description);
      if (!validation.valid) {
        setError(validation.error || '输入验证失败');
        setIsSubmitting(false);
        return;
      }

      // 调用后端API（支持Mock和真实API切换）
      const endpoint = configService.getAnalyzeEndpoint();
      const result = await HttpClient.post<{ task_id: string }>(
        endpoint,
        {
          description: validation.sanitized || description.trim(),
          urgent: false,
        }
      );
      
      // 开发时显示API模式
      if (process.env.NODE_ENV === 'development') {
        logger.info(`Using ${configService.isUsingMock() ? 'Mock' : 'Real'} API: ${endpoint}`);
      }

      const taskId = result.task_id;
      if (!taskId) {
        throw new Error('服务器未返回任务ID');
      }

      // 跳转到分析页面
      navigate(`/analysis/${taskId}`);
    } catch (error) {
      logger.error('Submit failed:', error as Error);
      const errorMessage = error instanceof Error 
        ? error.message 
        : '提交失败，请稍后重试';
      setError(errorMessage);
      setIsSubmitting(false);
    }
  };

  // 使用示例填充
  const handleExampleClick = (example: ProductExample) => {
    setDescription(example.description);
    setCharCount(example.description.length);
    setIsValid(example.description.length >= MIN_CHARS && example.description.length <= MAX_CHARS);
  };

  // 滑动手势支持（移动端页面切换）
  useSwipeGesture(containerRef, {
    onSwipeLeft: () => {
      // 可以实现页面预览等功能
      logger.debug('Swipe left detected');
    },
    config: {
      threshold: 100,
      preventScroll: false,
    }
  });

  return (
    <ResponsiveLayout
      ref={containerRef}
      variant={type === 'mobile' ? 'compact' : 'comfortable'}
      className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50"
    >
      <div className="container mx-auto space-y-4 sm:space-y-8">
        {/* v0风格的响应式头部 */}
        <div className="text-center space-y-2 sm:space-y-4">
          <div className="flex items-center justify-center mb-4">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
              <LightbulbIcon className="w-6 h-6 text-blue-600" />
            </div>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-gray-900">
            描述您的产品想法
          </h2>
          <p className="text-base sm:text-lg text-gray-600 max-w-2xl mx-auto px-4">
            详细告诉我们您的产品或服务。您描述得越具体，我们能提供的洞察就越好。
          </p>
        </div>

        {/* v0风格的响应式表单卡片 */}
        <div className="bg-white rounded-xl sm:rounded-2xl shadow-lg border-2 border-dashed border-gray-200 hover:border-blue-300 transition-colors p-4 sm:p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xl font-semibold text-gray-900 flex items-center space-x-2">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
                  </svg>
                  <span>产品描述</span>
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                  包括您的目标受众、核心功能以及您要解决的问题
                </p>
              </div>
              <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                isValid 
                  ? 'bg-green-100 text-green-700' 
                  : charCount > MAX_CHARS 
                    ? 'bg-red-100 text-red-700'
                    : 'bg-gray-100 text-gray-700'
              }`}>
                {charCount} 字
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <textarea
                  id="product-description"
                  data-testid="product-description-input"
                  value={description}
                  onChange={handleDescriptionChange}
                  disabled={isSubmitting}
                  className={`
                    w-full min-h-32 sm:min-h-40 p-3 sm:p-4
                    text-base border border-gray-300 rounded-lg 
                    bg-white text-gray-900 placeholder-gray-400
                    focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                    transition-all duration-200
                    ${isTouchDevice ? 'resize-none' : 'resize-y'}
                  `}
                  style={{
                    fontSize: isTouchDevice ? '16px' : undefined, // 防止iOS缩放
                  }}
                  placeholder="示例：一个帮助忙碌专业人士进行餐食准备的移动应用，根据饮食偏好、烹饪时间限制和当地杂货店供应情况生成个性化的每周餐食计划。该应用包括自动生成购物清单、分步烹饪指导以及与热门配送服务集成等功能..."
                  maxLength={MAX_CHARS + 100} // 允许一些缓冲
                  autoComplete="off"
                  autoCorrect="off"
                  spellCheck="false"
                />
                <div className="flex items-center justify-between text-sm text-gray-500 mt-2">
                  <span data-testid="character-count">
                    {charCount < MIN_CHARS
                      ? `还需要至少 ${MIN_CHARS - charCount} 个字`
                      : charCount > MAX_CHARS
                        ? `超出 ${charCount - MAX_CHARS} 个字`
                        : '字数适合分析'}
                  </span>
                  <span>建议 {MIN_CHARS}-{MAX_CHARS} 字</span>
                </div>
              </div>

              {error && (
                <div role="alert" className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p data-testid="error-message" className="text-red-700 text-sm">{error}</p>
                </div>
              )}

              {/* v0风格的响应式提交按钮 */}
              <ResponsiveButton
                data-testid="submit-button"
                type="submit"
                variant="default"
                size={type === 'mobile' ? 'lg' : 'md'}
                fullWidth={type === 'mobile'}
                loading={isSubmitting}
                disabled={isSubmitting}
                icon={<Zap className="w-4 h-4" />}
              >
                开始 5 分钟分析
              </ResponsiveButton>
            </form>
        </div>

        {/* v0风格的响应式示例网格 */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 text-center">需要灵感？试试这些示例：</h3>
          <div className={`
            grid gap-3 sm:gap-4
            ${type === 'mobile' 
              ? 'grid-cols-1' 
              : type === 'tablet' 
                ? 'grid-cols-2' 
                : 'grid-cols-3'
            }
          `}>
            {examples.map((example, index) => (
              <div
                key={index}
                className="bg-white rounded-lg border border-gray-200 hover:border-blue-300 hover:shadow-md transition-colors cursor-pointer p-4"
                onClick={() => handleExampleClick(example)}
              >
                <h4 className="font-medium text-blue-600 mb-2">{example.title}</h4>
                <p className="text-sm text-gray-600 line-clamp-3">
                  {example.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* v0风格的响应式流程时间轴 */}
        <div className="bg-white rounded-lg p-4 sm:p-6 border border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 text-center">接下来会发生什么？</h3>
          <div className={`
            grid gap-4 sm:gap-6
            ${type === 'mobile' ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-3'}
          `}>
            <div className="text-center space-y-2">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h4 className="font-medium text-gray-900">步骤 1：分析</h4>
              <p className="text-sm text-gray-600">我们扫描相关的 Reddit 社区，寻找关于您市场的讨论</p>
            </div>
            <div className="text-center space-y-2">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
                </svg>
              </div>
              <h4 className="font-medium text-gray-900">步骤 2：处理</h4>
              <p className="text-sm text-gray-600">AI 分析用户痛点、竞品提及和市场机会</p>
            </div>
            <div className="text-center space-y-2">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h4 className="font-medium text-gray-900">步骤 3：洞察</h4>
              <p className="text-sm text-gray-600">获得包含可操作商业洞察的综合报告</p>
            </div>
          </div>
        </div>
      </div>
    </ResponsiveLayout>
  );
};

export default InputPageV0;
