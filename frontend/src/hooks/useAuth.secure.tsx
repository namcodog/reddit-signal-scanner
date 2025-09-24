import React from 'react';
import { useAuth } from './useAuth';

interface SecureAuthProviderProps {
  children: React.ReactNode;
}

export const SecureAuthProvider: React.FC<SecureAuthProviderProps> = ({ children }) => {
  return <>{children}</>;
};

export const useSecureAuth = useAuth;

export default SecureAuthProvider;
