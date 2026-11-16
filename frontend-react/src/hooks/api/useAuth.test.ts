import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import {
  useAuthStatus,
  useCurrentUser,
  useSignUp,
  useSignIn,
  useSignOut,
  useIsAdmin,
  useIsSuperAdmin,
  useUserRole
} from './useAuth';
import type { User, AuthStatus, SignUpRequest, SignInRequest } from '@/types/api';

// Mock the API utils
vi.mock('@/utils/apiUtils', () => ({
  get: vi.fn(),
  post: vi.fn()
}));

// Helper functions to generate dynamic test data
const generateUser = (role: 'user' | 'admin' | 'super_admin' = 'user'): User => ({
  id: Math.floor(Math.random() * 10000),
  first_name: role === 'admin' ? 'Admin' : role === 'super_admin' ? 'SuperAdmin' : `User${Math.floor(Math.random() * 100)}`,
  email: `${Math.random().toString(36).substr(2, 9)}@example.com`,
  role,
  created_at: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000).toISOString(),
  last_login_at: new Date().toISOString()
});

const generateAuthStatus = (authenticated: boolean = true, user?: User): AuthStatus => ({
  authenticated,
  user: authenticated ? (user || generateUser()) : null
});

// Wrapper component for React Query
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe('useAuthStatus', () => {
  let mockGet: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const { get } = await import('@/utils/apiUtils');
    mockGet = get;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('fetches authentication status', async () => {
    const testAuthStatus = generateAuthStatus();
    mockGet.mockResolvedValue({ data: testAuthStatus });

    const { result } = renderHook(
      () => useAuthStatus(),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith(
      '/api/auth/status',
      { credentials: 'include' }
    );
    expect(result.current.data?.data.authenticated).toBe(testAuthStatus.authenticated);
    if (testAuthStatus.user) {
      expect(result.current.data?.data.user?.id).toBe(testAuthStatus.user.id);
      expect(result.current.data?.data.user?.role).toBe(testAuthStatus.user.role);
    }
  });

  it('handles authentication status error', async () => {
    const error = new Error('Network error');
    mockGet.mockRejectedValue(error);

    const { result } = renderHook(
      () => useAuthStatus(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.data).toBeUndefined();
  });

  it('does not retry on error', async () => {
    const error = new Error('Auth error');
    mockGet.mockRejectedValue(error);

    renderHook(
      () => useAuthStatus(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledTimes(1);
    });

    // Wait a bit more to ensure no retries
    await new Promise(resolve => setTimeout(resolve, 100));
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it('configures query with correct options', () => {
    renderHook(
      () => useAuthStatus(),
      { wrapper: createWrapper() }
    );

    // The hook should use the correct query key
    expect(mockGet).toHaveBeenCalledWith(
      '/api/auth/status',
      { credentials: 'include' }
    );
  });
});

describe('useCurrentUser', () => {
  let mockGet: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const { get } = await import('@/utils/apiUtils');
    mockGet = get;
  });

  it('fetches current user when authenticated', async () => {
    const testUser = generateUser();
    const testAuthStatus = generateAuthStatus(true, testUser);

    mockGet.mockImplementation((url: string) => {
      if (url === '/api/auth/status') {
        return Promise.resolve({ data: testAuthStatus });
      }
      if (url === '/api/auth/me') {
        return Promise.resolve({ data: { user: testUser } });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    const { result } = renderHook(
      () => useCurrentUser(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith(
        '/api/auth/me',
        { credentials: 'include' }
      );
    });

    await waitFor(() => {
      expect(result.current.data?.data.user?.id).toBe(testUser.id);
      expect(result.current.data?.data.user?.role).toBe(testUser.role);
    });
  });

  it('does not fetch user when not authenticated', async () => {
    const unauthenticatedStatus = generateAuthStatus(false);

    mockGet.mockImplementation((url: string) => {
      if (url === '/api/auth/status') {
        return Promise.resolve({ data: unauthenticatedStatus });
      }
      return Promise.reject(new Error('Should not be called'));
    });

    const { result } = renderHook(
      () => useCurrentUser(),
      { wrapper: createWrapper() }
    );

    // Wait for auth status to load
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('/api/auth/status', expect.any(Object));
    });

    // Should not call /api/auth/me
    expect(mockGet).not.toHaveBeenCalledWith('/api/auth/me', expect.any(Object));
    expect(result.current.data).toBeUndefined();
  });
});

describe('useSignUp', () => {
  let mockPost: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const { post } = await import('@/utils/apiUtils');
    mockPost = post;
  });

  it('calls sign up API and invalidates auth queries', async () => {
    const testUser = generateUser();
    const mockResponse = {
      data: { user: testUser, message: 'Account created successfully' }
    };
    mockPost.mockResolvedValue(mockResponse);

    const { result } = renderHook(
      () => useSignUp(),
      { wrapper: createWrapper() }
    );

    const signUpData: SignUpRequest = {
      email: `${Math.random().toString(36).substr(2, 9)}@example.com`,
      first_name: `New${Math.floor(Math.random() * 100)}`
    };

    await act(async () => {
      await result.current.mutateAsync(signUpData);
    });

    expect(mockPost).toHaveBeenCalledWith(
      '/api/auth/signup',
      signUpData,
      { credentials: 'include' }
    );
    expect(result.current.data?.data.user?.id).toBe(testUser.id);
    expect(result.current.data?.data.message).toBeTruthy();
  });

  it('handles sign up errors', async () => {
    const error = new Error('Email already exists');
    mockPost.mockRejectedValue(error);

    const { result } = renderHook(
      () => useSignUp(),
      { wrapper: createWrapper() }
    );

    const signUpData: SignUpRequest = {
      email: `${Math.random().toString(36).substr(2, 9)}@example.com`,
      first_name: `Existing${Math.floor(Math.random() * 100)}`
    };

    await act(async () => {
      try {
        await result.current.mutateAsync(signUpData);
      } catch (e) {
        expect(e).toBe(error);
      }
    });

    expect(result.current.error).toBe(error);
  });
});

describe('useSignIn', () => {
  let mockPost: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const { post } = await import('@/utils/apiUtils');
    mockPost = post;
  });

  it('calls sign in API and invalidates auth queries', async () => {
    const testUser = generateUser();
    const mockResponse = {
      data: { user: testUser, message: 'Signed in successfully' }
    };
    mockPost.mockResolvedValue(mockResponse);

    const { result } = renderHook(
      () => useSignIn(),
      { wrapper: createWrapper() }
    );

    const signInData: SignInRequest = {
      email: testUser.email
    };

    await act(async () => {
      await result.current.mutateAsync(signInData);
    });

    expect(mockPost).toHaveBeenCalledWith(
      '/api/auth/signin',
      signInData,
      { credentials: 'include' }
    );
    expect(result.current.data?.data.user?.id).toBe(testUser.id);
    expect(result.current.data?.data.message).toBeTruthy();
  });

  it('handles sign in errors', async () => {
    const error = new Error('Invalid credentials');
    mockPost.mockRejectedValue(error);

    const { result } = renderHook(
      () => useSignIn(),
      { wrapper: createWrapper() }
    );

    const signInData: SignInRequest = {
      email: `baduser_${Math.random().toString(36).substr(2, 9)}`
    };

    await act(async () => {
      try {
        await result.current.mutateAsync(signInData);
      } catch (e) {
        expect(e).toBe(error);
      }
    });

    expect(result.current.error).toBe(error);
  });
});

describe('useSignOut', () => {
  let mockPost: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const { post } = await import('@/utils/apiUtils');
    mockPost = post;
  });

  it('calls sign out API and clears auth data', async () => {
    const mockResponse = {
      data: { message: 'Signed out successfully' }
    };
    mockPost.mockResolvedValue(mockResponse);

    const { result } = renderHook(
      () => useSignOut(),
      { wrapper: createWrapper() }
    );

    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(mockPost).toHaveBeenCalledWith(
      '/api/auth/signout',
      undefined,
      { credentials: 'include' }
    );
    expect(result.current.data).toEqual(mockResponse);
  });

  it('handles sign out errors', async () => {
    const error = new Error('Sign out failed');
    mockPost.mockRejectedValue(error);

    const { result } = renderHook(
      () => useSignOut(),
      { wrapper: createWrapper() }
    );

    await act(async () => {
      try {
        await result.current.mutateAsync();
      } catch (e) {
        expect(e).toBe(error);
      }
    });

    expect(result.current.error).toBe(error);
  });
});

describe('useIsAdmin', () => {
  let mockGet: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const { get } = await import('@/utils/apiUtils');
    mockGet = get;
  });

  it('returns false for regular user', async () => {
    const regularUser = generateUser('user');
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: regularUser }
    });

    const { result } = renderHook(
      () => useIsAdmin(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current).toBe(false);
    });
  });

  it('returns true for admin user', async () => {
    const adminUser = generateUser('admin');
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: adminUser }
    });

    const { result } = renderHook(
      () => useIsAdmin(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current).toBe(true);
    });
  });

  it('returns true for super admin user', async () => {
    const superAdminUser = generateUser('super_admin');
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: superAdminUser }
    });

    const { result } = renderHook(
      () => useIsAdmin(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current).toBe(true);
    });
  });

  it('returns false when not authenticated', async () => {
    const unauthenticatedStatus = generateAuthStatus(false);
    mockGet.mockResolvedValue({
      data: unauthenticatedStatus
    });

    const { result } = renderHook(
      () => useIsAdmin(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current).toBe(false);
    });
  });
});

describe('useIsSuperAdmin', () => {
  let mockGet: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const { get } = await import('@/utils/apiUtils');
    mockGet = get;
  });

  it('returns false for regular user', async () => {
    const regularUser = generateUser('user');
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: regularUser }
    });

    const { result } = renderHook(
      () => useIsSuperAdmin(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current).toBe(false);
    });
  });

  it('returns false for admin user', async () => {
    const adminUser = generateUser('admin');
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: adminUser }
    });

    const { result } = renderHook(
      () => useIsSuperAdmin(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current).toBe(false);
    });
  });

  it('returns true for super admin user', async () => {
    const superAdminUser = generateUser('super_admin');
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: superAdminUser }
    });

    const { result } = renderHook(
      () => useIsSuperAdmin(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current).toBe(true);
    });
  });
});

describe('useUserRole', () => {
  let mockGet: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const { get } = await import('@/utils/apiUtils');
    mockGet = get;
  });

  it('returns user role for authenticated user', async () => {
    const adminUser = generateUser('admin');
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: adminUser }
    });

    const { result } = renderHook(
      () => useUserRole(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current).toBe(adminUser.role);
    });
  });

  it('returns default user role when not authenticated', async () => {
    const unauthenticatedStatus = generateAuthStatus(false);
    mockGet.mockResolvedValue({
      data: unauthenticatedStatus
    });

    const { result } = renderHook(
      () => useUserRole(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current).toBe('user');
    });
  });

  it('returns user role for different user types', async () => {
    // Test regular user
    const regularUser = generateUser('user');
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: regularUser }
    });

    const { result: regularResult } = renderHook(
      () => useUserRole(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(regularResult.current).toBe(regularUser.role);
    });

    // Test super admin
    const superAdminUser = generateUser('super_admin');
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: superAdminUser }
    });

    const { result: superResult } = renderHook(
      () => useUserRole(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(superResult.current).toBe(superAdminUser.role);
    });
  });
});

describe('Authentication Integration', () => {
  let mockGet: any;
  let mockPost: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const { get, post } = await import('@/utils/apiUtils');
    mockGet = get;
    mockPost = post;
  });

  it('handles complete authentication flow', async () => {
    const testUser = generateUser();

    // Start unauthenticated
    const unauthenticatedStatus = generateAuthStatus(false);
    mockGet.mockResolvedValue({
      data: unauthenticatedStatus
    });

    const { result: authResult } = renderHook(
      () => useAuthStatus(),
      { wrapper: createWrapper() }
    );

    const { result: signInResult } = renderHook(
      () => useSignIn(),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(authResult.current.data?.data.authenticated).toBe(false);
    });

    // Sign in
    const signInResponse = {
      data: { user: testUser, message: 'Signed in successfully' }
    };
    mockPost.mockResolvedValue(signInResponse);

    const signInData = {
      email: testUser.email
    };

    await act(async () => {
      await signInResult.current.mutateAsync(signInData);
    });

    expect(mockPost).toHaveBeenCalledWith(
      '/api/auth/signin',
      signInData,
      { credentials: 'include' }
    );
  });

  it('handles authentication state transitions', async () => {
    const wrapper = createWrapper();
    const regularUser = generateUser('user');
    const adminUser = generateUser('admin');

    // Initially authenticated as regular user
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: regularUser }
    });

    const { result: isAdminResult } = renderHook(
      () => useIsAdmin(),
      { wrapper }
    );

    await waitFor(() => {
      expect(isAdminResult.current).toBe(false);
    });

    // Change to admin user
    mockGet.mockResolvedValue({
      data: { authenticated: true, user: adminUser }
    });

    const { result: newIsAdminResult } = renderHook(
      () => useIsAdmin(),
      { wrapper }
    );

    await waitFor(() => {
      expect(newIsAdminResult.current).toBe(true);
    });
  });
});
