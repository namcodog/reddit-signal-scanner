import React from 'react';
import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAppState } from '@/hooks/useAppState';
import UserDropdown from '@/components/user/UserDropdown';
import AuthDialog from '@/components/auth/AuthDialog';

interface AppShellProps {
  children: React.ReactNode;
  actions?: React.ReactNode;
}

const AppShell: React.FC<AppShellProps> = ({ children, actions }) => {
  const [appState, appActions] = useAppState();
  const isAuthenticated = appState.auth.isAuthenticated;

  const handleLoginClick = () => {
    appActions.auth.openDialog('navigation', 'login');
  };

  const handleSignupClick = () => {
    appActions.auth.openDialog('navigation', 'signup');
  };

  const handleAuthDialogChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      appActions.auth.closeDialog();
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-card">
        <div className="container mx-auto flex items-center justify-between px-4 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Search className="h-5 w-5" />
            </div>
            <h1 className="text-xl font-bold text-foreground">Reddit 商业信号扫描器</h1>
          </div>
          <div className="flex items-center gap-4 text-sm">
            {actions}
            {isAuthenticated ? (
              <UserDropdown />
            ) : (
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleLoginClick}>
                  登录
                </Button>
                <Button size="sm" onClick={handleSignupClick}>
                  注册
                </Button>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-12 sm:px-6 lg:py-16">{children}</main>

      <AuthDialog
        open={appState.ui.authDialog.open}
        onOpenChange={handleAuthDialogChange}
        defaultTab={appState.ui.authDialog.defaultTab}
      />
    </div>
  );
};

export default AppShell;
