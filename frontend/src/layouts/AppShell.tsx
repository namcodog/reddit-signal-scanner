import React from 'react';
import { Search } from 'lucide-react';
import { useSecureAuth } from '@/hooks/useSecureAuth';
import { Button } from '@/components/ui/button';

type AppShellProps = {
  children: React.ReactNode;
  extra?: React.ReactNode;
};

const AppShell: React.FC<AppShellProps> = ({ children, extra }) => {
  const { user, isAuthenticated, logout } = useSecureAuth();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <Search className="w-5 h-5 text-primary-foreground" />
            </div>
            <h1 className="text-xl font-bold">Reddit 商业信号扫描器</h1>
          </div>
          <div className="flex items-center space-x-3">
            {extra}
            {isAuthenticated && user ? (
              <>
                <span className="text-sm text-muted-foreground">欢迎，{user.email}</span>
                <Button variant="outline" size="sm" onClick={() => void logout()}>
                  退出登录
                </Button>
              </>
            ) : (
              <>
                <Button variant="outline" size="sm">登录</Button>
                <Button size="sm">注册</Button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        {children}
      </main>
    </div>
  );
};

export default AppShell;
