import { useContext } from 'react';
import { AuthProvider } from './simpleAuthContext';
import type { AuthContextType } from '@/types/auth.simple';

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthProvider.Context);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default useAuth;
