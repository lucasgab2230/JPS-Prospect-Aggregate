import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import {
  useProspectDecisions,
  useMyDecisions,
  useDecisionStats,
  useCreateDecision,
  useDeleteDecision
} from './useDecisions';
import type {
  ApiResponse,
  GoNoGoDecision,
  DecisionStats,
  CreateDecisionRequest,
  PaginationMeta
} from '@/types/api';

// Mock the API utils
vi.mock('@/utils/apiUtils', () => ({
  get: vi.fn(),
  post: vi.fn(),
  del: vi.fn(),
  buildQueryString: vi.fn()
}));

// Helper functions to generate dynamic test data
const generateUser = () => ({
  id: Math.floor(Math.random() * 10000),
  username: `user_${Math.random().toString(36).substr(2, 9)}`,
  first_name: `User${Math.floor(Math.random() * 100)}`,
  last_name: `Last${Math.floor(Math.random() * 100)}`,
  email: `${Math.random().toString(36).substr(2, 9)}@example.com`,
  role: Math.random() > 0.5 ? 'user' : 'admin',
  created_at: new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000).toISOString(),
  updated_at: new Date().toISOString()
});

const generateDecision = (): GoNoGoDecision => {
  const decisions = ['go', 'no-go'] as const;
  const reasons = ['Good fit for our services', 'Not aligned with strategy', 'Excellent opportunity', 'Budget constraints', 'Timeline mismatch'];

  return {
    id: Math.floor(Math.random() * 10000),
    prospect_id: `prospect-${Math.random().toString(36).substr(2, 9)}`,
    user_id: Math.floor(Math.random() * 100),
    decision: decisions[Math.floor(Math.random() * decisions.length)],
    reason: reasons[Math.floor(Math.random() * reasons.length)],
    decision_date: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
    created_at: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date().toISOString(),
    user: generateUser()
  };
};

const generateDecisionStats = (): DecisionStats => {
  const totalDecisions = Math.floor(Math.random() * 500) + 50;
  const goDecisions = Math.floor(Math.random() * totalDecisions);
  const noGoDecisions = totalDecisions - goDecisions;
  const userCount = Math.floor(Math.random() * 10) + 2;

  const decisionsByUser = Array.from({ length: userCount }, () => ({
    user_id: Math.floor(Math.random() * 1000),
    username: `user_${Math.random().toString(36).substr(2, 6)}`,
    decision_count: Math.floor(Math.random() * 50) + 1
  }));

  const recentDecisions = Array.from({ length: Math.min(5, totalDecisions) }, () => generateDecision());

  return {
    total_decisions: totalDecisions,
    go_decisions: goDecisions,
    no_go_decisions: noGoDecisions,
    decisions_by_user: decisionsByUser,
    recent_decisions: recentDecisions
  };
};

const generatePaginationMeta = (): PaginationMeta => {
  const totalItems = Math.floor(Math.random() * 1000) + 50;
  const perPage = Math.floor(Math.random() * 50) + 10;
  const totalPages = Math.ceil(totalItems / perPage);
  const currentPage = Math.floor(Math.random() * totalPages) + 1;

  return {
    page: currentPage,
    per_page: perPage,
    total_items: totalItems,
    total_pages: totalPages,
    has_next: currentPage < totalPages,
    has_prev: currentPage > 1
  };
};

const generateCreateDecisionRequest = (): CreateDecisionRequest => {
  const decisions = ['go', 'no-go'] as const;
  const reasons = ['Excellent opportunity for growth', 'Strategic alignment', 'Budget constraints', 'Timeline concerns', 'Resource availability'];

  return {
    prospect_id: `prospect-${Math.random().toString(36).substr(2, 9)}`,
    decision: decisions[Math.floor(Math.random() * decisions.length)],
    reason: reasons[Math.floor(Math.random() * reasons.length)]
  };
};

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

describe('useProspectDecisions', () => {
  let mockGet: any;
  let testDecision: GoNoGoDecision;
  let testProspectId: string;

  beforeEach(async () => {
    vi.clearAllMocks();

    // Generate fresh test data
    testDecision = generateDecision();
    testProspectId = `prospect-${Math.random().toString(36).substr(2, 9)}`;

    // Get mocked functions
    const { get } = await import('@/utils/apiUtils');
    mockGet = get;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('fetches decisions for a specific prospect', async () => {
    const decisions = [testDecision, generateDecision()];
    const mockResponse: ApiResponse<{ prospect_id: string; decisions: GoNoGoDecision[]; total_decisions: number }> = {
      data: {
        prospect_id: testProspectId,
        decisions,
        total_decisions: decisions.length
      },
      message: 'Decisions retrieved successfully',
      status: 'success'
    };

    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useProspectDecisions(testProspectId), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith(
      '/api/decisions/prospect-123',
      { credentials: 'include' }
    );
    expect(result.current.data).toEqual(mockResponse);
    expect(result.current.error).toBeNull();
  });

  it('does not fetch when prospect ID is null', () => {
    const { result } = renderHook(() => useProspectDecisions(null), {
      wrapper: createWrapper()
    });

    expect(mockGet).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  it('handles API errors gracefully', async () => {
    const error = new Error('API Error');
    mockGet.mockRejectedValue(error);

    const { result } = renderHook(() => useProspectDecisions('prospect-123'), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.data).toBeUndefined();
  });

  it('retries failed requests only once', async () => {
    mockGet.mockRejectedValueOnce(new Error('Network error'))
          .mockRejectedValueOnce(new Error('Still failing'))
          .mockResolvedValue({ data: { decisions: [] } });

    const { result } = renderHook(() => useProspectDecisions('prospect-123'), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should retry only once (total 2 calls)
    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(result.current.error).toBeTruthy();
  });

  it('has correct stale time configuration', async () => {
    const mockResponse = {
      data: { prospect_id: 'prospect-123', decisions: [], total_decisions: 0 }
    };
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useProspectDecisions('prospect-123'), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Data should be considered fresh for 1 minute
    expect(result.current.isStale).toBe(false);
  });
});

describe('useMyDecisions', () => {
  let mockGet: any;
  let mockBuildQueryString: any;

  beforeEach(async () => {
    vi.clearAllMocks();

    // Get mocked functions
    const { get, buildQueryString } = await import('@/utils/apiUtils');
    mockGet = get;
    mockBuildQueryString = buildQueryString;

    mockBuildQueryString.mockImplementation((params) => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        searchParams.set(key, String(value));
      });
      const query = searchParams.toString();
      return query ? `?${query}` : '';
    });
  });

  it('fetches current user decisions with default pagination', async () => {
    const testDecision = generateDecision();
    const testPagination = generatePaginationMeta();
    const mockResponse: ApiResponse<{ decisions: GoNoGoDecision[]; pagination: PaginationMeta }> = {
      data: {
        decisions: [testDecision],
        pagination: testPagination
      },
      message: 'User decisions retrieved successfully',
      status: 'success'
    };

    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useMyDecisions(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockBuildQueryString).toHaveBeenCalledWith({ page: 1, per_page: 50 });
    expect(mockGet).toHaveBeenCalledWith(
      '/api/decisions/my?page=1&per_page=50',
      { credentials: 'include' }
    );
    expect(result.current.data).toEqual(mockResponse);
  });

  it('fetches user decisions with custom pagination', async () => {
    const testDecision = generateDecision();
    const testPagination = generatePaginationMeta();
    const mockResponse = {
      data: { decisions: [testDecision], pagination: testPagination }
    };
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useMyDecisions(2, 25), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockBuildQueryString).toHaveBeenCalledWith({ page: 2, per_page: 25 });
    expect(mockGet).toHaveBeenCalledWith(
      '/api/decisions/my?page=2&per_page=25',
      { credentials: 'include' }
    );
  });

  it('has longer stale time than prospect decisions', async () => {
    const testPagination = generatePaginationMeta();
    const mockResponse = {
      data: { decisions: [], pagination: testPagination }
    };
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useMyDecisions(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have 2 minute stale time
    expect(result.current.isStale).toBe(false);
  });

  it('updates query when pagination parameters change', async () => {
    const testPagination = generatePaginationMeta();
    const mockResponse = {
      data: { decisions: [], pagination: testPagination }
    };
    mockGet.mockResolvedValue(mockResponse);

    const { result, rerender } = renderHook(
      ({ page, perPage }) => useMyDecisions(page, perPage),
      {
        wrapper: createWrapper(),
        initialProps: { page: 1, perPage: 50 }
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledTimes(1);

    // Change pagination
    rerender({ page: 2, perPage: 25 });

    await waitFor(() => {
      expect(mockBuildQueryString).toHaveBeenCalledWith({ page: 2, per_page: 25 });
    });
  });
});

describe('useDecisionStats', () => {
  let mockGet: any;

  beforeEach(async () => {
    vi.clearAllMocks();

    // Get mocked functions
    const { get } = await import('@/utils/apiUtils');
    mockGet = get;
  });

  it('fetches decision statistics', async () => {
    const testStats = generateDecisionStats();
    const mockResponse: ApiResponse<DecisionStats> = {
      data: testStats,
      message: 'Statistics retrieved successfully',
      status: 'success'
    };

    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useDecisionStats(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith(
      '/api/decisions/stats',
      { credentials: 'include' }
    );
    expect(result.current.data).toEqual(mockResponse);
  });

  it('has longest stale time for caching', async () => {
    const testStats = generateDecisionStats();
    const mockResponse = {
      data: testStats
    };
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useDecisionStats(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have 5 minute stale time
    expect(result.current.isStale).toBe(false);
  });

  it('handles empty statistics gracefully', async () => {
    const emptyStats: DecisionStats = {
      total_decisions: 0,
      go_decisions: 0,
      no_go_decisions: 0,
      decisions_by_user: [],
      recent_decisions: []
    };

    const mockResponse = { data: emptyStats };
    mockGet.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useDecisionStats(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data?.data).toEqual(emptyStats);
  });
});

describe('useCreateDecision', () => {
  let queryClient: QueryClient;
  let mockPost: any;

  beforeEach(async () => {
    vi.clearAllMocks();

    // Get mocked functions
    const { post } = await import('@/utils/apiUtils');
    mockPost = post;

    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    });

    // Spy on invalidateQueries
    vi.spyOn(queryClient, 'invalidateQueries');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const createWrapperWithClient = () => {
    return ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
  };

  it('creates decision successfully', async () => {
    const testDecision = generateDecision();
    const testRequest = generateCreateDecisionRequest();
    const mockResponse: ApiResponse<{ decision: GoNoGoDecision; message: string }> = {
      data: {
        decision: testDecision,
        message: 'Decision created successfully'
      },
      message: 'Decision created successfully',
      status: 'success'
    };

    mockPost.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useCreateDecision(), {
      wrapper: createWrapperWithClient()
    });

    let response: typeof mockResponse;
    await act(async () => {
      response = await result.current.mutateAsync(testRequest);
    });

    expect(mockPost).toHaveBeenCalledWith(
      '/api/decisions/',
      testRequest,
      { credentials: 'include' }
    );
    expect(response!).toEqual(mockResponse);
  });

  it('invalidates related queries on success', async () => {
    const testDecision = generateDecision();
    const testRequest = generateCreateDecisionRequest();
    const mockResponse = {
      data: { decision: testDecision, message: 'Success' }
    };
    mockPost.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useCreateDecision(), {
      wrapper: createWrapperWithClient()
    });

    await act(async () => {
      await result.current.mutateAsync(testRequest);
    });

    // Should invalidate prospect-specific decisions
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['decisions', 'prospect', testRequest.prospect_id]
    });

    // Should invalidate user's decisions
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['decisions', 'my']
    });

    // Should invalidate stats
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['decisions', 'stats']
    });

    // Should invalidate admin queries
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['admin']
    });
  });

  it('handles creation errors gracefully', async () => {
    const testRequest = generateCreateDecisionRequest();
    const error = new Error('Validation failed');
    mockPost.mockRejectedValue(error);

    const { result } = renderHook(() => useCreateDecision(), {
      wrapper: createWrapperWithClient()
    });

    let thrownError: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync(testRequest);
      } catch (e) {
        thrownError = e as Error;
      }
    });

    expect(thrownError).toBe(error);
    expect(result.current.error).toBe(error);

    // Should not invalidate queries on error
    expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
  });

  it('handles different decision types', async () => {
    const testDecision = generateDecision();
    const noGoRequest: CreateDecisionRequest = {
      prospect_id: `prospect-${Math.random().toString(36).substr(2, 9)}`,
      decision: 'no-go',
      reason: 'Not aligned with our strategy'
    };

    const mockResponse = {
      data: {
        decision: { ...testDecision, decision: 'no-go', prospect_id: noGoRequest.prospect_id },
        message: 'No-go decision recorded'
      }
    };
    mockPost.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useCreateDecision(), {
      wrapper: createWrapperWithClient()
    });

    await act(async () => {
      await result.current.mutateAsync(noGoRequest);
    });

    expect(mockPost).toHaveBeenCalledWith(
      '/api/decisions/',
      noGoRequest,
      { credentials: 'include' }
    );

    // Should invalidate the correct prospect's decisions
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['decisions', 'prospect', noGoRequest.prospect_id]
    });
  });

  it('provides mutation state correctly', () => {
    const { result } = renderHook(() => useCreateDecision(), {
      wrapper: createWrapperWithClient()
    });

    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.data).toBeUndefined();
    expect(typeof result.current.mutate).toBe('function');
    expect(typeof result.current.mutateAsync).toBe('function');
  });
});

describe('useDeleteDecision', () => {
  let queryClient: QueryClient;
  let mockDel: any;

  beforeEach(async () => {
    vi.clearAllMocks();

    // Get mocked functions
    const { del } = await import('@/utils/apiUtils');
    mockDel = del;

    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    });

    vi.spyOn(queryClient, 'invalidateQueries');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const createWrapperWithClient = () => {
    return ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: queryClient }, children);
  };

  it('deletes decision successfully', async () => {
    const mockResponse: ApiResponse<{ message: string }> = {
      data: { message: 'Decision deleted successfully' },
      message: 'Decision deleted successfully',
      status: 'success'
    };

    mockDel.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useDeleteDecision(), {
      wrapper: createWrapperWithClient()
    });

    let response: typeof mockResponse;
    await act(async () => {
      response = await result.current.mutateAsync(1);
    });

    expect(mockDel).toHaveBeenCalledWith(
      '/api/decisions/1',
      { credentials: 'include' }
    );
    expect(response!).toEqual(mockResponse);
  });

  it('invalidates all decision queries on success', async () => {
    const mockResponse = {
      data: { message: 'Deleted successfully' }
    };
    mockDel.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useDeleteDecision(), {
      wrapper: createWrapperWithClient()
    });

    await act(async () => {
      await result.current.mutateAsync(1);
    });

    // Should invalidate all decision-related queries
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['decisions']
    });

    // Should invalidate admin queries
    expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['admin']
    });
  });

  it('handles deletion errors gracefully', async () => {
    const error = new Error('Decision not found');
    mockDel.mockRejectedValue(error);

    const { result } = renderHook(() => useDeleteDecision(), {
      wrapper: createWrapperWithClient()
    });

    let thrownError: Error | undefined;
    await act(async () => {
      try {
        await result.current.mutateAsync(999);
      } catch (e) {
        thrownError = e as Error;
      }
    });

    expect(thrownError).toBe(error);
    expect(result.current.error).toBe(error);

    // Should not invalidate queries on error
    expect(queryClient.invalidateQueries).not.toHaveBeenCalled();
  });

  it('handles multiple concurrent deletions', async () => {
    const mockResponse = {
      data: { message: 'Deleted successfully' }
    };
    mockDel.mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useDeleteDecision(), {
      wrapper: createWrapperWithClient()
    });

    // Delete multiple decisions concurrently
    await act(async () => {
      await Promise.all([
        result.current.mutateAsync(1),
        result.current.mutateAsync(2),
        result.current.mutateAsync(3)
      ]);
    });

    expect(mockDel).toHaveBeenCalledTimes(3);
    expect(mockDel).toHaveBeenCalledWith('/api/decisions/1', { credentials: 'include' });
    expect(mockDel).toHaveBeenCalledWith('/api/decisions/2', { credentials: 'include' });
    expect(mockDel).toHaveBeenCalledWith('/api/decisions/3', { credentials: 'include' });
  });

  it('provides correct mutation state', () => {
    const { result } = renderHook(() => useDeleteDecision(), {
      wrapper: createWrapperWithClient()
    });

    expect(result.current.isPending).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.data).toBeUndefined();
    expect(typeof result.current.mutate).toBe('function');
    expect(typeof result.current.mutateAsync).toBe('function');
  });
});
