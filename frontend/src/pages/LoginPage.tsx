import React, { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/types/router.types';
import { useSecureAuth } from '@/hooks/useSecureAuth';

const emailPattern = /^(?=.{5,320}$)[A-Za-z0-9._%+\-']+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login, getAuthError, isAuthenticated, isLoading } = useSecureAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to={ROUTES.INPUT} replace />;
  }

  const validateForm = (): string | null => {
    if (!emailPattern.test(email.trim().toLowerCase())) {
      return '请输入合法的邮箱地址';
    }

    if (password.length === 0) {
      return '请输入密码';
    }

    return null;
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setErrorMessage(null);

    const validationError = validateForm();
    if (validationError) {
      setErrorMessage(validationError);
      return;
    }

    setIsSubmitting(true);
    try {
      await login(email.trim().toLowerCase(), password, { rememberMe });
      navigate(ROUTES.INPUT, { replace: true });
    } catch (error) {
      const authError = getAuthError(error as Error);
      setErrorMessage(authError.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md bg-white shadow-xl rounded-xl p-8">
        <h1 className="text-2xl font-semibold text-slate-900 text-center">
          欢迎回来 · Reddit Signal Scanner
        </h1>
        <p className="mt-2 text-sm text-slate-500 text-center">
          进入控制台，继续追踪 Reddit 的商业信号
        </p>

        {errorMessage ? (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {errorMessage}
          </div>
        ) : null}

        <form className="mt-6 space-y-5" onSubmit={handleSubmit} noValidate>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700">
              邮箱
            </label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={event => setEmail(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              密码
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="请输入密码"
            />
          </div>

          <div className="flex items-center justify-between">
            <label className="inline-flex items-center text-sm text-slate-600">
              <input
                type="checkbox"
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                checked={rememberMe}
                onChange={event => setRememberMe(event.target.checked)}
              />
              <span className="ml-2">记住我</span>
            </label>
            <span className="text-sm text-slate-400">忘记密码？请联系管理员</span>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || isLoading}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-white font-medium hover:bg-indigo-700 transition disabled:bg-indigo-300"
          >
            {isSubmitting ? '登录中...' : '登录'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          还没有账号？
          <Link to={ROUTES.REGISTER} className="ml-1 font-medium text-indigo-600 hover:text-indigo-500">
            立即注册
          </Link>
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
