import React, { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

type AuthDialogTab = 'login' | 'signup';

interface AuthDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultTab?: AuthDialogTab;
  onLogin?: (payload: { email: string; password: string }) => Promise<void> | void;
  onSignup?: (payload: { name: string; email: string; password: string }) => Promise<void> | void;
}

const initialLoginState = { email: '', password: '' };
const initialSignupState = { name: '', email: '', password: '' };

const AuthDialog: React.FC<AuthDialogProps> = ({
  open,
  onOpenChange,
  defaultTab = 'login',
  onLogin,
  onSignup,
}) => {
  const [activeTab, setActiveTab] = useState<AuthDialogTab>(defaultTab);
  const [loginForm, setLoginForm] = useState(initialLoginState);
  const [signupForm, setSignupForm] = useState(initialSignupState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setLoginForm(initialLoginState);
      setSignupForm(initialSignupState);
      setIsSubmitting(false);
      setErrorMessage(null);
      return;
    }

    setActiveTab(defaultTab);
    setErrorMessage(null);
  }, [open, defaultTab]);

  const dialogTitle = useMemo(() => {
    return activeTab === 'login' ? '账户登录' : '创建账户';
  }, [activeTab]);

  const dialogDescription = useMemo(() => {
    return activeTab === 'login'
      ? '登录以保存分析记录、跨设备同步并访问高级功能'
      : '注册新账户以解锁完整分析体验';
  }, [activeTab]);

  const handleClose = (nextOpen: boolean) => {
    onOpenChange(nextOpen);
  };

  const handleSubmitError = (error: unknown, fallback: string) => {
    if (error instanceof Error && error.message) {
      setErrorMessage(error.message);
      return;
    }
    setErrorMessage(fallback);
  };

  const handleLoginSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      if (onLogin) {
        await onLogin(loginForm);
      }
      handleClose(false);
    } catch (error) {
      handleSubmitError(error, '登录失败，请稍后重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSignupSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isSubmitting) {
      return;
    }
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      if (onSignup) {
        await onSignup(signupForm);
      }
      handleClose(false);
    } catch (error) {
      handleSubmitError(error, '注册失败，请稍后重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{dialogTitle}</DialogTitle>
          <DialogDescription>{dialogDescription}</DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as AuthDialogTab)} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="login">登录</TabsTrigger>
            <TabsTrigger value="signup">注册</TabsTrigger>
          </TabsList>

          <TabsContent value="login">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">欢迎回来</CardTitle>
                <CardDescription>使用企业邮箱登录，保存分析进度</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="space-y-4" onSubmit={handleLoginSubmit}>
                  <div className="space-y-2">
                    <Label htmlFor="login-email">邮箱</Label>
                    <Input
                      id="login-email"
                      type="email"
                      inputMode="email"
                      autoComplete="email"
                      placeholder="name@company.com"
                      value={loginForm.email}
                      onChange={(event) =>
                        setLoginForm((prev) => ({ ...prev, email: event.target.value.trim() }))
                      }
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="login-password">密码</Label>
                    <Input
                      id="login-password"
                      type="password"
                      autoComplete="current-password"
                      placeholder="请输入密码"
                      value={loginForm.password}
                      onChange={(event) =>
                        setLoginForm((prev) => ({ ...prev, password: event.target.value }))
                      }
                      required
                      minLength={6}
                    />
                  </div>

                  {errorMessage && activeTab === 'login' ? (
                    <p className="text-sm text-destructive">{errorMessage}</p>
                  ) : null}

                  <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting ? '正在登录…' : '登录'}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="signup">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">快速创建账户</CardTitle>
                <CardDescription>注册后可同步分析记录并解锁团队协作</CardDescription>
              </CardHeader>
              <CardContent>
                <form className="space-y-4" onSubmit={handleSignupSubmit}>
                  <div className="space-y-2">
                    <Label htmlFor="signup-name">姓名</Label>
                    <Input
                      id="signup-name"
                      type="text"
                      autoComplete="name"
                      placeholder="您的姓名"
                      value={signupForm.name}
                      onChange={(event) =>
                        setSignupForm((prev) => ({ ...prev, name: event.target.value }))
                      }
                      required
                      maxLength={40}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-email">邮箱</Label>
                    <Input
                      id="signup-email"
                      type="email"
                      inputMode="email"
                      autoComplete="email"
                      placeholder="name@company.com"
                      value={signupForm.email}
                      onChange={(event) =>
                        setSignupForm((prev) => ({ ...prev, email: event.target.value.trim() }))
                      }
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="signup-password">密码</Label>
                    <Input
                      id="signup-password"
                      type="password"
                      autoComplete="new-password"
                      placeholder="至少 8 位字符，建议包含字母与数字"
                      value={signupForm.password}
                      onChange={(event) =>
                        setSignupForm((prev) => ({ ...prev, password: event.target.value }))
                      }
                      required
                      minLength={8}
                    />
                  </div>

                  {errorMessage && activeTab === 'signup' ? (
                    <p className="text-sm text-destructive">{errorMessage}</p>
                  ) : null}

                  <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting ? '正在注册…' : '注册并开始分析'}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};

export default AuthDialog;
