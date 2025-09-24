import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useSecureAuth } from '@/hooks/useSecureAuth';
import type { RegisterRequest } from '@/types/auth.types';
import { X } from 'lucide-react';

type AuthTab = 'login' | 'signup';

interface SignupFormState {
  email: string;
  password: string;
  confirmPassword: string;
  acceptTerms: boolean;
  acceptPrivacy: boolean;
}

// 弱密码模式检查（与后端保持一致）
function checkWeakPatterns(password: string): boolean {
  const weakPatterns = ['123456', 'password', 'qwerty', 'abc123'];
  const passwordLower = password.toLowerCase();
  return weakPatterns.some(pattern => passwordLower.includes(pattern));
}

const PASSWORD_RULES: Array<{ test: (value: string) => boolean; message: string }> = [
  { test: value => value.length >= 8, message: '密码长度至少 8 个字符' },
  { test: value => /[A-Z]/.test(value), message: '必须包含至少一个大写字母' },
  { test: value => /[a-z]/.test(value), message: '必须包含至少一个小写字母' },
  { test: value => /[0-9]/.test(value), message: '必须包含至少一个数字' },
  { test: value => /[!@#$%^&*()_+\-=[\]{};:'",.<>/?|`~]/.test(value), message: '必须包含至少一个特殊字符' },
  { test: value => !checkWeakPatterns(value), message: '不能包含弱密码模式（如 password、123456 等）' },
];

interface AuthDialogProps {
  children?: React.ReactElement;
  defaultTab?: AuthTab;
  onSuccess?: () => void;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

const buildRegisterPayload = (form: SignupFormState): RegisterRequest => ({
  email: form.email.trim(),
  password: form.password,
  confirmPassword: form.confirmPassword,
  acceptTerms: form.acceptTerms,
  acceptPrivacy: form.acceptPrivacy,
});

const AuthDialog: React.FC<AuthDialogProps> = ({
  children,
  defaultTab = 'login',
  onSuccess,
  open,
  onOpenChange,
}) => {
  const { login, register, getAuthError } = useSecureAuth();
  const [internalOpen, setInternalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<AuthTab>(defaultTab);
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [signupForm, setSignupForm] = useState<SignupFormState>({
    email: '',
    password: '',
    confirmPassword: '',
    acceptTerms: false,
    acceptPrivacy: false,
  });
  const [loginError, setLoginError] = useState<string | null>(null);
  const [signupError, setSignupError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<AuthTab | null>(null);

  const isControlled = open !== undefined;
  const isOpen = isControlled ? Boolean(open) : internalOpen;

  const resetState = () => {
    setLoginError(null);
    setSignupError(null);
    setSubmitting(null);
    setLoginForm({ email: '', password: '' });
    setSignupForm({
      email: '',
      password: '',
      confirmPassword: '',
      acceptTerms: false,
      acceptPrivacy: false,
    });
    setActiveTab(defaultTab);
  };

  const updateSignupForm = (patch: Partial<SignupFormState>) => {
    setSignupForm(prev => ({ ...prev, ...patch }));
    setSignupError(null);
  };

  const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting('login');
    setLoginError(null);
    try {
      await login(loginForm.email.trim(), loginForm.password);
      if (isControlled) {
        onOpenChange?.(false);
      } else {
        setInternalOpen(false);
      }
      onSuccess?.();
      resetState();
    } catch (error) {
      const authError = getAuthError(error as Error);
      setLoginError(authError.message);
    } finally {
      setSubmitting(null);
    }
  };

  const handleSignup = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting('signup');
    setSignupError(null);

    const validationError = validateSignupForm(signupForm);
    if (validationError) {
      setSignupError(validationError);
      setSubmitting(null);
      return;
    }

    try {
      const payload = buildRegisterPayload(signupForm);
      await register(payload);
      if (isControlled) {
        onOpenChange?.(false);
      } else {
        setInternalOpen(false);
      }
      onSuccess?.();
      resetState();
    } catch (error) {
      const authError = getAuthError(error as Error);
      setSignupError(authError.message);
    } finally {
      setSubmitting(null);
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!isControlled) {
      setInternalOpen(open);
    }
    onOpenChange?.(open);
    if (!open) {
      resetState();
    }
  };

  useEffect(() => {
    if (isOpen) {
      setActiveTab(defaultTab);
    }
  }, [defaultTab, isOpen]);

  const validateSignupForm = (form: SignupFormState): string | null => {
    if (!form.email.trim()) {
      return '请输入邮箱地址';
    }

    const emailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
    if (!emailPattern.test(form.email.trim())) {
      return '邮箱格式不正确';
    }

    for (const rule of PASSWORD_RULES) {
      if (!rule.test(form.password)) {
        return rule.message;
      }
    }

    if (form.password !== form.confirmPassword) {
      return '两次输入的密码不一致';
    }

    if (!form.acceptTerms || !form.acceptPrivacy) {
      return '请先阅读并同意用户协议与隐私政策';
    }

    return null;
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      {children ? <DialogTrigger asChild>{children}</DialogTrigger> : null}
      <DialogContent className="sm:max-w-[420px] rounded-2xl p-0 overflow-hidden shadow-xl">
        <div className="relative px-6 pt-6">
          <button
            type="button"
            className="absolute right-0 top-0 inline-flex size-8 items-center justify-center rounded-full bg-secondary/40 text-secondary-foreground transition hover:bg-secondary/60"
            aria-label="关闭"
            onClick={() => handleOpenChange(false)}
          >
            <X className="size-4" />
          </button>
          <DialogHeader className="mb-4 space-y-2 text-left">
            <DialogTitle className="text-2xl font-semibold">账户登录</DialogTitle>
            <DialogDescription className="text-base text-muted-foreground">
              登录或注册以保存您的分析结果并访问高级功能
            </DialogDescription>
          </DialogHeader>
        </div>

        <div className="px-6 pb-6">
          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as AuthTab)} className="w-full">
            <TabsList className="grid w-full grid-cols-2 rounded-full bg-muted p-1">
              <TabsTrigger className="rounded-full" value="login">登录</TabsTrigger>
              <TabsTrigger className="rounded-full" value="signup">注册</TabsTrigger>
            </TabsList>

            <TabsContent value="login" className="mt-4">
              <Card className="border-none shadow-none">
                <CardHeader className="px-0 pb-2">
                  <CardTitle>登录账户</CardTitle>
                  <CardDescription>输入您的邮箱和密码继续</CardDescription>
                </CardHeader>
                <CardContent className="px-0">
                  <form onSubmit={handleLogin} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="dialog-login-email">邮箱</Label>
                      <Input
                        id="dialog-login-email"
                        type="email"
                        value={loginForm.email}
                        onChange={(event) => {
                          setLoginError(null);
                          setLoginForm((prev) => ({ ...prev, email: event.target.value }));
                        }}
                        placeholder="your@email.com"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="dialog-login-password">密码</Label>
                      <Input
                        id="dialog-login-password"
                        type="password"
                        value={loginForm.password}
                        onChange={(event) => {
                          setLoginError(null);
                          setLoginForm((prev) => ({ ...prev, password: event.target.value }));
                        }}
                        required
                      />
                    </div>
                    {loginError ? (
                      <p className="text-sm text-destructive">{loginError}</p>
                    ) : null}
                    <Button type="submit" className="w-full" disabled={submitting === 'login'}>
                      {submitting === 'login' ? '登录中…' : '登录'}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="signup" className="mt-4">
              <Card className="border-none shadow-none">
                <CardHeader className="px-0 pb-2">
                  <CardTitle>创建账户</CardTitle>
                  <CardDescription>注册即可体验完整功能</CardDescription>
                </CardHeader>
                <CardContent className="px-0">
                  <form onSubmit={handleSignup} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="dialog-signup-email">邮箱</Label>
                      <Input
                        id="dialog-signup-email"
                        type="email"
                        value={signupForm.email}
                        onChange={(event) => updateSignupForm({ email: event.target.value })}
                        placeholder="your@email.com"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="dialog-signup-password">密码</Label>
                      <Input
                        id="dialog-signup-password"
                        type="password"
                        value={signupForm.password}
                        onChange={(event) => updateSignupForm({ password: event.target.value })}
                        placeholder="至少 8 位字符"
                        minLength={8}
                        required
                      />
                      <p className="text-xs text-muted-foreground">
                        必须包含大写字母、小写字母、数字和特殊字符，不能包含弱密码模式
                      </p>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="dialog-signup-confirm-password">确认密码</Label>
                      <Input
                        id="dialog-signup-confirm-password"
                        type="password"
                        value={signupForm.confirmPassword}
                        onChange={(event) => updateSignupForm({ confirmPassword: event.target.value })}
                        placeholder="再次输入密码"
                        required
                      />
                    </div>
                    <div className="space-y-3">
                      <label className="flex items-start space-x-2 text-sm">
                        <input
                          type="checkbox"
                          checked={signupForm.acceptTerms}
                          onChange={(event) => updateSignupForm({ acceptTerms: event.target.checked })}
                          className="mt-0.5 rounded border-gray-300"
                          required
                        />
                        <span>我已阅读并同意《用户协议》</span>
                      </label>
                      <label className="flex items-start space-x-2 text-sm">
                        <input
                          type="checkbox"
                          checked={signupForm.acceptPrivacy}
                          onChange={(event) => updateSignupForm({ acceptPrivacy: event.target.checked })}
                          className="mt-0.5 rounded border-gray-300"
                          required
                        />
                        <span>我已阅读并同意《隐私政策》</span>
                      </label>
                    </div>
                    {signupError ? (
                      <p className="text-sm text-destructive">{signupError}</p>
                    ) : null}
                    <Button type="submit" className="w-full" disabled={submitting === 'signup'}>
                      {submitting === 'signup' ? '注册中…' : '注册'}
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default AuthDialog;
