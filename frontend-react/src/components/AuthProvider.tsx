import { createContext, useContext, ReactNode } from 'react';
import { useAuthStatus } from '../hooks/api';
import { User } from '../types/api';

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: Error | null;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const { data, isLoading, error } = useAuthStatus();

  const value: AuthContextValue = {
    user: data?.data?.user || null,
    isAuthenticated: data?.data?.authenticated || false,
    isLoading,
    error: error as Error | null,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
