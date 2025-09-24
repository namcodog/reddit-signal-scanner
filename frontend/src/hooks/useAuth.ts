import { useContext } from 'react';
import { AuthProvider } from './authContext';
import type { AuthContextType } from '@/types/auth.types';

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthProvider.Context);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default useAuth;
