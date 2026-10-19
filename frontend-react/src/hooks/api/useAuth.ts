import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { get, post } from '@/utils/apiUtils';
import {
  ApiResponse,
  User,
  AuthStatus,
  SignUpRequest,
  SignInRequest
} from '../../types/api';

const API_BASE = '/api/auth';

// Auth API functions
const authApi = {
  signUp: async (data: SignUpRequest): Promise<ApiResponse<{ user: User; message: string }>> => {
    return await post<ApiResponse<{ user: User; message: string }>>(
      `${API_BASE}/signup`,
      data,
      { credentials: 'include' }
    );
  },

  signIn: async (data: SignInRequest): Promise<ApiResponse<{ user: User; message: string }>> => {
    return await post<ApiResponse<{ user: User; message: string }>>(
      `${API_BASE}/signin`,
      data,
      { credentials: 'include' }
    );
  },

  signOut: async (): Promise<ApiResponse<{ message: string }>> => {
    return await post<ApiResponse<{ message: string }>>(
      `${API_BASE}/signout`,
      undefined,
      { credentials: 'include' }
    );
  },

  getStatus: async (): Promise<ApiResponse<AuthStatus>> => {
    return await get<ApiResponse<AuthStatus>>(
      `${API_BASE}/status`,
      { credentials: 'include' }
    );
  },

  getCurrentUser: async (): Promise<ApiResponse<{ user: User }>> => {
    return await get<ApiResponse<{ user: User }>>(
      `${API_BASE}/me`,
      { credentials: 'include' }
    );
  },
};

// Hook to get authentication status
export const useAuthStatus = () => {
  return useQuery({
    queryKey: ['auth', 'status'],
    queryFn: authApi.getStatus,
    retry: false,
    staleTime: 0, // Always fresh
    gcTime: 0, // Never cache
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
    structuralSharing: false, // Ensure new object references trigger re-renders
  });
};

// Hook to get current user
export const useCurrentUser = () => {
  const { data: authStatus } = useAuthStatus();

  return useQuery({
    queryKey: ['auth', 'user'],
    queryFn: authApi.getCurrentUser,
    enabled: authStatus?.data?.authenticated === true,
    retry: false,
  });
};

// Hook for sign up
export const useSignUp = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.signUp,
    onSuccess: () => {
      // Invalidate auth queries to refetch status
      queryClient.invalidateQueries({ queryKey: ['auth'] });
    },
  });
};

// Hook for sign in
export const useSignIn = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.signIn,
    onSuccess: () => {
      // Invalidate auth queries to refetch status
      queryClient.invalidateQueries({ queryKey: ['auth'] });
    },
  });
};

// Hook for sign out
export const useSignOut = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: authApi.signOut,
    onSuccess: () => {
      // Immediately set auth status to false
      queryClient.setQueryData(['auth', 'status'], {
        data: {
          authenticated: false,
          user: null
        }
      });

      // Invalidate all queries to force refetch
      queryClient.invalidateQueries();

      // Clear all other cached data after a small delay
      setTimeout(() => {
        queryClient.removeQueries({
          predicate: (query) => query.queryKey[0] !== 'auth'
        });
      }, 100);
    },
  });
};

// Helper function to check if user is admin
export const useIsAdmin = () => {
  const { data: authStatus } = useAuthStatus();
  const userRole = authStatus?.data?.user?.role;
  return userRole === 'admin' || userRole === 'super_admin';
};

export const useIsSuperAdmin = () => {
  const { data: authStatus } = useAuthStatus();
  return authStatus?.data?.user?.role === 'super_admin';
};

// Helper function to get user role
export const useUserRole = () => {
  const { data: authStatus } = useAuthStatus();
  return authStatus?.data?.user?.role || 'user';
};
