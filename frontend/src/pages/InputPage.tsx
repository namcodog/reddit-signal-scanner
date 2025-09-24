import React, { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import NavigationBreadcrumb, { type StepKey } from '@/components/v0/NavigationBreadcrumb';
import ProductInputForm from '@/components/v0/ProductInputForm';
import InputValidator from '@/utils/validation';
import HttpClient from '@/utils/httpClient';
import logger from '@/utils/logger';

const MIN_DESCRIPTION_LENGTH = 10;
const MAX_DESCRIPTION_LENGTH = 2000;

const InputPage: React.FC = () => {
  const navigate = useNavigate();
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleStartAnalysis = useCallback(
    async (input: string) => {
      if (isSubmitting) {
        return;
      }

      const normalized = input.trim();
      const validation = InputValidator.validateProductDescription(normalized);
      if (!validation.valid) {
        setErrorMessage(validation.error ?? '请输入有效的产品描述');
        return;
      }

      const payload = {
        product_description: validation.sanitized ?? normalized,
        timestamp: Date.now(),
      };

      setIsSubmitting(true);
      setErrorMessage(null);

      try {
        const response = await HttpClient.post<{ task_id: string }>('/api/v1/analyze', payload);
        if (response.task_id) {
          navigate(`/analysis/${response.task_id}`);
        } else {
          throw new Error('服务器未返回任务 ID');
        }
      } catch (error) {
        logger.error('[InputPage] Start analysis failed', error as Error);
        const message =
          error instanceof Error ? error.message : '分析请求失败，请稍后再试';
        setErrorMessage(message);
      } finally {
        setIsSubmitting(false);
      }
    },
    [isSubmitting, navigate]
  );

  const handleBreadcrumbNavigate = (step: StepKey) => {
    if (step === 'input') {
      return;
    }
    // 其他步骤需要任务上下文，当前页无法跳转
  };

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-4xl space-y-8">
        <NavigationBreadcrumb currentStep="input" canNavigateBack={false} onNavigate={handleBreadcrumbNavigate} />

        <ProductInputForm
          onStartAnalysis={handleStartAnalysis}
          submitting={isSubmitting}
          value={description}
          onChange={setDescription}
          minLength={MIN_DESCRIPTION_LENGTH}
          maxLength={MAX_DESCRIPTION_LENGTH}
        />

        {errorMessage ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {errorMessage}
          </div>
        ) : null}
      </div>
    </AppShell>
  );
};

export default InputPage;
