import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSecureAuth } from '@/hooks/useSecureAuth';
import { useAppState } from '@/hooks/useAppState';
import AppShell from '@/components/layout/AppShell';
import AuthService from '@/services/auth.service';

const EMAIL_EXTRACTION_REGEX = /[A-Za-z0-9._%+\-']+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;

const sanitizeEmail = (rawEmail: string): string => {
  const normalized = rawEmail.trim().toLowerCase();
  const match = normalized.match(EMAIL_EXTRACTION_REGEX);
  return match ? match[0] : normalized;
};

interface VerificationResult {
  email: string;
  verified: boolean;
  message: string;
}

type VerificationStatus = 'loading' | 'success' | 'already' | 'error' | 'missing';

const VerifyEmailPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const { resendVerificationEmail } = useSecureAuth();
  const [, appActions] = useAppState();

  const [status, setStatus] = useState<VerificationStatus>('loading');
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resendEmail, setResendEmail] = useState('');
  const [resendFeedback, setResendFeedback] = useState<string | null>(null);
  const [isResending, setIsResending] = useState(false);

  useEffect(() => {
    if (!token) {
      setStatus('missing');
      setErrorMessage('验证链接缺少 token 参数，请从邮件重新进入。');
      return;
    }

    const verify = async (): Promise<void> => {
      try {
        const response = await AuthService.verifyEmail(token);
        setResult(response);
        setStatus(response.verified ? 'success' : 'error');
      } catch (error) {
        const message =
          (error as { message?: string }).message || '验证链接无效或已过期';
        setErrorMessage(message);
        setStatus('error');
      }
    };

    void verify();
  }, [token]);

  const handleResend = async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setResendFeedback(null);
    setErrorMessage(null);

    const sanitized = sanitizeEmail(resendEmail);

    if (!sanitized) {
      setResendFeedback('请输入需要重新发送的邮箱地址');
      return;
    }

    setIsResending(true);
    try {
      await resendVerificationEmail(sanitized);
      setResendFeedback('验证邮件已重新发送，请查收邮箱');
    } catch (error) {
      const message =
        (error as { message?: string }).message || '重新发送失败，请稍后重试';
      setResendFeedback(message);
    } finally {
      setIsResending(false);
    }
  };

  const renderContent = (): React.ReactNode => {
    if (status === 'loading') {
      return (
        <div className="flex flex-col items-center justify-center space-y-4 py-12">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
          <p className="text-slate-500">正在验证邮箱，请稍候...</p>
        </div>
      );
    }

    if (status === 'success' && result) {
      return (
        <div className="text-center space-y-4">
          <h2 className="text-2xl font-semibold text-emerald-600">邮箱验证成功</h2>
          <p className="text-slate-600">
            {result.message}
            <br />
            现在可以使用账号 <span className="font-medium">{result.email}</span> 登录系统。
          </p>
          <button
            type="button"
            onClick={() => appActions.auth.openDialog('navigation', 'login')}
            className="mt-4 inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700"
          >
            去登录
          </button>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <div className="text-center space-y-3">
          <h2 className="text-2xl font-semibold text-red-600">邮箱验证失败</h2>
          <p className="text-slate-600">
            {errorMessage || '链接无效或已过期，请重新发送验证邮件'}
          </p>
          <p className="text-sm text-slate-500">
            如果你已经验证成功，也可以直接{' '}
            <button
              type="button"
              onClick={() => appActions.auth.openDialog('navigation', 'login')}
              className="text-indigo-600 hover:text-indigo-500 underline"
            >
              前往登录
            </button>
          </p>
        </div>

        <form className="space-y-4" onSubmit={handleResend}>
          <label className="block text-sm font-medium text-slate-700">
            重新发送验证邮件
          </label>
          <input
            type="email"
            value={resendEmail}
            onChange={event => setResendEmail(event.target.value)}
            className="block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            placeholder="you@example.com"
          />
          <button
            type="submit"
            disabled={isResending}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-white font-medium hover:bg-indigo-700 transition disabled:bg-indigo-300"
          >
            {isResending ? '发送中...' : '发送验证邮件'}
          </button>
          {resendFeedback ? (
            <p className="text-sm text-slate-500 text-center">{resendFeedback}</p>
          ) : null}
        </form>
      </div>
    );
  };

  return (
    <AppShell>
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-full max-w-lg bg-white shadow-xl rounded-xl p-8 space-y-6">
          <div className="text-center">
            <h1 className="text-3xl font-semibold text-slate-900">邮箱验证</h1>
            <p className="mt-2 text-sm text-slate-500">
              为了保障安全，首次注册需要完成邮箱验证
            </p>
          </div>
          {renderContent()}
        </div>
      </div>
    </AppShell>
  );
};

export default VerifyEmailPage;
