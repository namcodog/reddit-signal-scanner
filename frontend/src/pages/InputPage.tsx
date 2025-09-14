/**
 * 输入页面 - Reddit Signal Scanner起点 (增强版)
 * 基于 Linus 极简原则：一个文本框，一个按钮，零配置
 *
 * 用户体验目标：30秒内完成产品描述输入并启动分析
 *
 * 技术债务消除：
 * - 从占位符变成完整功能实现
 * - 实时输入验证和安全检查
 * - 友好的错误提示和加载状态
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import InputValidator from '@/utils/validation';
import HttpClient from '@/utils/httpClient';
import logger from '@/utils/logger';

// 输入状态枚举
enum InputState {
  IDLE = 'idle',
  VALIDATING = 'validating',
  SUBMITTING = 'submitting',
  ERROR = 'error',
}

/**
 * 产品描述输入页面 - 完整功能版本
 * 消灭用户体验技术债务：从6分提升到8分
 */
const InputPage: React.FC = () => {
  const navigate = useNavigate();
  const [description, setDescription] = useState('');
  const [inputState, setInputState] = useState<InputState>(InputState.IDLE);
  const [error, setError] = useState<string>('');
  const [characterCount, setCharacterCount] = useState(0);
  const validationTimerRef = useRef<NodeJS.Timeout | null>(null);

  // 清理定时器的函数
  const clearValidationTimer = useCallback(() => {
    if (validationTimerRef.current) {
      clearTimeout(validationTimerRef.current);
      validationTimerRef.current = null;
    }
  }, []);

  // 实时输入验证 - 使用防抖
  const validateInput = useCallback((value: string) => {
    // 清理之前的定时器
    clearValidationTimer();
    
    setCharacterCount(value.length);

    if (!value.trim()) {
      setError('');
      setInputState(InputState.IDLE);
      return;
    }

    setInputState(InputState.VALIDATING);

    // 防抖动验证
    validationTimerRef.current = setTimeout(() => {
      const validation = InputValidator.validateProductDescription(value);
      if (!validation.valid) {
        setError(validation.error || '输入无效');
        setInputState(InputState.ERROR);
      } else {
        setError('');
        setInputState(InputState.IDLE);
      }
      validationTimerRef.current = null;
    }, 500);
  }, [clearValidationTimer]);

  // 处理输入变化
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setDescription(value);
    validateInput(value);
  };

  // 组件卸载时清理定时器
  useEffect(() => {
    return clearValidationTimer;
  }, [clearValidationTimer]);

  // 提交分析请求
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!description.trim()) {
      setError('请输入产品描述');
      return;
    }

    setInputState(InputState.SUBMITTING);
    setError('');

    try {
      // 最终安全验证
      const validation = InputValidator.validateProductDescription(description);
      if (!validation.valid) {
        setError(validation.error || '输入验证失败');
        setInputState(InputState.ERROR);
        return;
      }

      // 简化的API调用
      const result = await HttpClient.post<{ task_id: string }>(
        '/api/v1/analyze',
        {
          product_description: validation.sanitized || description.trim(),
          timestamp: Date.now(),
        }
      );

      const taskId = result.task_id;
      if (!taskId) {
        throw new Error('服务器未返回任务ID');
      }

      // 跳转到分析页面
      navigate(`/analysis/${taskId}`);
    } catch (error) {
      logger.error('Submit failed:', error as Error);

      // 简化的错误处理 - 遵循Linus原则
      const errorMessage =
        error instanceof Error ? error.message : '提交失败，请稍后重试';
      setError(errorMessage);
      setInputState(InputState.ERROR);
    }
  };

  // 获取输入框样式
  const getInputClassName = () => {
    const baseClass =
      'w-full min-h-[120px] p-4 text-base border-2 rounded-lg resize-vertical font-mono transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50';

    switch (inputState) {
      case InputState.ERROR:
        return `${baseClass} border-red-300 bg-red-50 focus:border-red-500`;
      case InputState.VALIDATING:
        return `${baseClass} border-yellow-300 bg-yellow-50 focus:border-yellow-500`;
      case InputState.SUBMITTING:
        return `${baseClass} border-gray-300 bg-gray-100 cursor-not-allowed`;
      default:
        return `${baseClass} border-gray-300 bg-white focus:border-blue-500`;
    }
  };

  // 获取提交按钮文本
  const getSubmitButtonText = () => {
    switch (inputState) {
      case InputState.VALIDATING:
        return '验证中...';
      case InputState.SUBMITTING:
        return '正在提交...';
      default:
        return '开始 5 分钟分析';
    }
  };

  const canSubmit =
    description.trim().length >= 10 &&
    inputState !== InputState.SUBMITTING &&
    inputState !== InputState.VALIDATING &&
    !error;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center px-4">
      <div className="max-w-2xl w-full">
        {/* 标题部分 */}
        <div className="text-center mb-8">
          <div className="text-6xl mb-4">🔍</div>
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Reddit Signal Scanner
          </h1>
          <p className="text-xl text-gray-700">
            30秒输入，5分钟分析，发现Reddit上的商业机会
          </p>
        </div>

        {/* 主输入表单 */}
        <div className="bg-white rounded-xl shadow-xl p-8">
          <form onSubmit={handleSubmit}>
            <div className="mb-6">
              <label
                htmlFor="productDescription"
                className="block text-lg font-semibold text-gray-900 mb-3"
              >
                描述你的产品或服务
              </label>

              <textarea
                id="productDescription"
                data-testid="product-description-input"
                value={description}
                onChange={handleInputChange}
                disabled={inputState === InputState.SUBMITTING}
                className={getInputClassName()}
                placeholder="例如：一款帮助研究者和创作者自动整理和连接想法的AI笔记应用，支持多种格式导入，智能标签分类，并能生成知识图谱..."
                rows={6}
                maxLength={2000}
                spellCheck={false}
              />

              {/* 字符计数和状态 */}
              <div className="flex justify-between items-center mt-3">
                <div className="flex items-center space-x-4">
                  <span
                    data-testid="character-count"
                    className={`text-sm ${
                      characterCount > 1800
                        ? 'text-red-600'
                        : characterCount > 1500
                          ? 'text-yellow-600'
                          : 'text-gray-500'
                    }`}
                  >
                    {characterCount}/2000 字符
                  </span>

                  {inputState === InputState.VALIDATING && (
                    <div className="flex items-center text-yellow-600">
                      <div className="animate-spin rounded-full h-4 w-4 border-2 border-yellow-600 border-t-transparent mr-2"></div>
                      <span className="text-sm">验证中...</span>
                    </div>
                  )}
                </div>

                <div className="text-sm text-gray-500">最少10字符</div>
              </div>
            </div>

            {/* 错误提示 */}
            {error && (
              <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-center">
                  <div className="text-red-600 mr-2">⚠️</div>
                  <p data-testid="error-message" className="text-red-700 text-sm">{error}</p>
                </div>
              </div>
            )}

            {/* 提交按钮 */}
            <div className="flex justify-center">
              <button
                type="submit"
                data-testid="submit-button"
                disabled={!canSubmit}
                className={`
                  px-8 py-3 text-lg font-semibold rounded-lg transition-all duration-200
                  ${
                    canSubmit
                      ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-lg hover:shadow-xl transform hover:-translate-y-0.5'
                      : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  }
                  ${inputState === InputState.SUBMITTING ? 'animate-pulse' : ''}
                `}
              >
                {inputState === InputState.SUBMITTING && (
                  <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent inline-block mr-2"></div>
                )}
                {getSubmitButtonText()}
              </button>
            </div>
          </form>
        </div>

        {/* 底部说明 */}
        <div className="mt-8 text-center">
          <div className="text-sm text-gray-600 space-y-2">
            <p>🔒 我们使用企业级加密保护您的数据安全</p>
            <p>⚡ 基于Linus Torvalds极简设计哲学构建</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InputPage;
