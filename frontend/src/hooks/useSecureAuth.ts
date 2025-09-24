import { useContext } from 'react';
import { SecureAuthProvider } from './useAuth.secure';
import type { AuthContextType } from '@/types/auth.types';

export const useSecureAuth = (): AuthContextType => {
  const context = useContext(SecureAuthProvider.Context);

  if (!context) {
    throw new Error('useSecureAuth must be used within a SecureAuthProvider');
  }

  return context;
};

export default useSecureAuth;
