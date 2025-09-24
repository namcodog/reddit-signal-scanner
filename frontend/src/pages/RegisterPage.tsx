import React, { useMemo, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/types/router.types';
import { useSecureAuth } from '@/hooks/useSecureAuth';

const EMAIL_EXTRACTION_REGEX = /[A-Za-z0-9._%+\-']+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
const EMAIL_VALIDATION_REGEX = /^(?=.{5,320}$)[A-Za-z0-9._%+\-']+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

const sanitizeEmail = (rawEmail: string): string => {
  const normalized = rawEmail.trim().toLowerCase();
  const match = normalized.match(EMAIL_EXTRACTION_REGEX);
  return match ? match[0] : normalized;
};

interface PasswordRequirement {
  label: string;
  satisfied: boolean;
}

// 弱密码模式检查（与后端保持一致）
const checkWeakPatterns = (password: string): boolean => {
  const weakPatterns = ['123456', 'password', 'qwerty', 'abc123'];
  const passwordLower = password.toLowerCase();
  return !weakPatterns.some(pattern => passwordLower.includes(pattern));
};

const buildPasswordRequirements = (password: string): PasswordRequirement[] => [
  { label: '至少8个字符', satisfied: password.length >= 8 },
  { label: '包含大写字母', satisfied: /[A-Z]/.test(password) },
  { label: '包含小写字母', satisfied: /[a-z]/.test(password) },
  { label: '包含数字', satisfied: /[0-9]/.test(password) },
  { label: '包含特殊字符', satisfied: /[!@#$%^&*()_+\-=[\]{};:'",.<>?/|\\`~]/.test(password) },
  { label: '不包含弱密码模式', satisfied: checkWeakPatterns(password) },
];

const getStrengthLabel = (requirements: PasswordRequirement[]): string => {
  const satisfiedCount = requirements.filter(requirement => requirement.satisfied).length;
  const totalRequirements = requirements.length; // 现在是6个要求

  if (satisfiedCount <= 2) return '强度：弱';
  if (satisfiedCount === 3 || satisfiedCount === 4) return '强度：中';
  if (satisfiedCount === totalRequirements) return '强度：强';
  return '强度：中'; // 5个满足但不是全部
};

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const { register, getAuthError, isAuthenticated, isLoading } = useSecureAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [errorMessages, setErrorMessages] = useState<string[]>([]);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const requirements = useMemo(() => buildPasswordRequirements(password), [password]);
  const passwordStrengthLabel = useMemo(() => getStrengthLabel(requirements), [requirements]);
  const sanitizedEmail = useMemo(() => sanitizeEmail(email), [email]);

  if (isAuthenticated) {
    return <Navigate to={ROUTES.INPUT} replace />;
  }

  const validateForm = (): string[] => {
    const problems: string[] = [];

    if (!EMAIL_VALIDATION_REGEX.test(sanitizedEmail)) {
      problems.push('请输入合法的邮箱地址');
    }

    if (password !== confirmPassword) {
      problems.push('两次输入的密码不一致');
    }

    if (requirements.some(requirement => !requirement.satisfied)) {
      problems.push('密码强度不足，请满足全部安全要求');
    }

    if (!acceptTerms) {
      problems.push('请阅读并同意《用户协议》');
    }

    if (!acceptPrivacy) {
      problems.push('请阅读并同意《隐私政策》');
    }

    return problems;
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setErrorMessages([]);
    setInfoMessage(null);

    const problems = validateForm();
    if (problems.length > 0) {
      setErrorMessages(problems);
      return;
    }

    setIsSubmitting(true);
    try {
      await register(
        {
          email: sanitizedEmail,
          password,
          confirmPassword,
          acceptTerms,
          acceptPrivacy,
        },
        { rememberMe }
      );

      setInfoMessage('注册成功，验证邮件已发送，正在跳转仪表盘...');
      navigate(ROUTES.INPUT, { replace: true });
    } catch (error) {
      const authError = getAuthError(error as Error);
      setErrorMessages([authError.message]);
    } finally {
      setIsSubmitting(false);
    }
  };

  const showSanitizedHint = sanitizedEmail !== email.trim().toLowerCase();

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-xl bg-white shadow-xl rounded-xl p-8">
        <h1 className="text-2xl font-semibold text-slate-900 text-center">
          创建你的 Reddit Signal Scanner 账号
        </h1>
        <p className="mt-2 text-sm text-slate-500 text-center">
          一次注册，畅享全链路分析、报告与实时通知
        </p>

        {errorMessages.length > 0 ? (
          <div className="mt-6 space-y-2">
            {errorMessages.map(message => (
              <div
                key={message}
                className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {message}
              </div>
            ))}
          </div>
        ) : null}

        {infoMessage ? (
          <div className="mt-6 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {infoMessage}
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
            {showSanitizedHint ? (
              <p className="mt-1 text-xs text-amber-600">
                系统将自动校正为 <span className="font-medium">{sanitizedEmail}</span>
              </p>
            ) : null}
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700">
              密码
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="如：MySecure@Pass2024!"
            />
            <p className="mt-1 text-xs text-slate-500">{passwordStrengthLabel}</p>
            <ul className="mt-2 space-y-1 text-xs text-slate-500">
              {requirements.map(requirement => (
                <li key={requirement.label} className="flex items-center">
                  <span
                    className={`mr-2 h-2 w-2 rounded-full ${
                      requirement.satisfied ? 'bg-emerald-500' : 'bg-slate-300'
                    }`}
                  ></span>
                  <span
                    className={requirement.satisfied ? 'text-emerald-600' : undefined}
                  >
                    {requirement.label}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-700">
              确认密码
            </label>
            <input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={event => setConfirmPassword(event.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="请再次输入密码"
            />
          </div>

          <div className="space-y-2 text-sm text-slate-600">
            <label className="flex items-start">
              <input
                type="checkbox"
                className="mt-1 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                checked={acceptTerms}
                onChange={event => setAcceptTerms(event.target.checked)}
              />
              <span className="ml-3">
                我已阅读并同意
                <button type="button" className="ml-1 text-indigo-600 hover:text-indigo-500">
                  《用户协议》
                </button>
              </span>
            </label>
            <label className="flex items-start">
              <input
                type="checkbox"
                className="mt-1 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                checked={acceptPrivacy}
                onChange={event => setAcceptPrivacy(event.target.checked)}
              />
              <span className="ml-3">
                我已阅读并同意
                <button type="button" className="ml-1 text-indigo-600 hover:text-indigo-500">
                  《隐私政策》
                </button>
              </span>
            </label>
            <label className="inline-flex items-center text-sm text-slate-600">
              <input
                type="checkbox"
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                checked={rememberMe}
                onChange={event => setRememberMe(event.target.checked)}
              />
              <span className="ml-2">记住我（本机保持登录状态）</span>
            </label>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || isLoading}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-white font-medium hover:bg-indigo-700 transition disabled:bg-indigo-300"
          >
            {isSubmitting ? '注册中...' : '注册'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          已有账号？
          <Link to={ROUTES.LOGIN} className="ml-1 font-medium text-indigo-600 hover:text-indigo-500">
            直接登录
          </Link>
        </p>
      </div>
    </div>
  );
};

export default RegisterPage;
