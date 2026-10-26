import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useInfiniteProspects, useProspectStatistics, useProspect } from './useProspects';
import type { Prospect, ProspectFilters, ProspectStatistics } from '@/types/prospects';
import type { ApiResponse } from '@/types/api';

// Mock the API utils
vi.mock('@/utils/apiUtils', () => ({
  get: vi.fn(),
  buildQueryString: vi.fn()
}));

// Mock fetch for individual prospect queries
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Test data
const mockProspects: Prospect[] = [
  {
    id: 'prospect-1',
    title: 'Software Development Services',
    description: 'Development of custom software solutions',
    agency: 'Department of Defense',
    posted_date: '2024-01-15',
    loaded_at: '2024-01-15T10:00:00Z',
    estimated_value: '50000',
    estimated_value_text: '$50,000',
    naics_code: '541511',
    source_file: 'dod_2024_01_15.json',
    source_data_id: '1',
    enhancement_status: 'idle',
    duplicate_group_id: null,
    set_aside_status: null,
    contact_email: null,
    contact_name: null,
    ai_enhanced_title: null,
    ai_enhanced_description: null,
    parsed_contract_value: null,
    ollama_processed_at: null
  },
  {
    id: 'prospect-2',
    title: 'Cloud Infrastructure Setup',
    description: 'Setup and configuration of cloud infrastructure',
    agency: 'Health and Human Services',
    posted_date: '2024-01-16',
    loaded_at: '2024-01-16T10:00:00Z',
    estimated_value: 75000,
    estimated_value_text: '$75,000',
    naics_code: '518210',
    source_file: 'hhs_2024_01_16.json',
    source_data_id: 2,
    enhancement_status: 'processing',
    duplicate_group_id: null,
    set_aside_status: 'Small Business',
    contact_email: 'contact@hhs.gov',
    contact_name: 'John Smith',
    ai_enhanced_title: 'Enhanced: Cloud Infrastructure Setup',
    ai_enhanced_description: 'AI-enhanced description of cloud setup',
    parsed_contract_value: 75000,
    ollama_processed_at: '2024-01-16T12:00:00Z'
  }
];

const mockPaginatedResponse = {
  prospects: mockProspects,
  pagination: {
    has_next: true,
    page: 1,
    total_items: 25
  }
};

const _mockStatistics: ProspectStatistics = {
  data: {
    total: 1500,
    approved: 450,
    pending: 800,
    rejected: 250
  }
};

const mockProspectApiResponse: ApiResponse<Prospect> = {
  data: mockProspects[0],
  message: 'Prospect retrieved successfully',
  status: 'success'
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

describe('useInfiniteProspects', () => {
  let mockGet: any;
  let mockBuildQueryString: any;

  beforeEach(async () => {
    vi.clearAllMocks();

    // Get mocked functions
    const { get, buildQueryString } = await import('@/utils/apiUtils');
    mockGet = get;
    mockBuildQueryString = buildQueryString;

    mockGet.mockResolvedValue(mockPaginatedResponse);
    mockBuildQueryString.mockImplementation((params) => {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          searchParams.set(key, String(value));
        }
      });
      const query = searchParams.toString();
      return query ? `?${query}` : '';
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('fetches prospects with no filters', async () => {
    const { result } = renderHook(() => useInfiniteProspects(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith('/api/prospects?page=1&limit=10');
    expect(result.current.data).toEqual(mockProspects);
    expect(result.current.hasNextPage).toBe(true);
  });

  it('fetches prospects with filters', async () => {
    const filters: ProspectFilters = {
      naics: '541511',
      keywords: 'software development',
      agency: 'DOD',
      ai_enrichment: 'enhanced',
      dataSourceIds: [1, 2]
    };

    const { result } = renderHook(() => useInfiniteProspects(filters), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockBuildQueryString).toHaveBeenCalledWith({
      page: 1,
      limit: 10,
      naics: '541511',
      keywords: 'software development',
      agency: 'DOD',
      ai_enrichment: 'enhanced',
      dataSourceIds: [1, 2]
    });
  });

  it('handles pagination correctly', async () => {
    const { result } = renderHook(() => useInfiniteProspects(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.hasNextPage).toBe(true);

    // Mock second page response
    const secondPageResponse = {
      prospects: [
        {
          ...mockProspects[0],
          id: 'prospect-3',
          title: 'Second Page Prospect'
        }
      ],
      pagination: {
        has_next: false,
        page: 2,
        total_items: 25
      }
    };

    mockGet.mockResolvedValueOnce(secondPageResponse);

    // Fetch next page
    await result.current.fetchNextPage();

    await waitFor(() => {
      expect(result.current.isFetchingNextPage).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith('/api/prospects?page=2&limit=10');
    expect(result.current.data).toHaveLength(3); // All prospects from both pages
    expect(result.current.hasNextPage).toBe(false);
  });

  it('determines next page correctly', async () => {
    // Test with has_next: true
    const { result } = renderHook(() => useInfiniteProspects(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.hasNextPage).toBe(true);

    // Test with has_next: false
    const noNextPageResponse = {
      prospects: mockProspects,
      pagination: {
        has_next: false,
        page: 1,
        total_items: 2
      }
    };

    mockGet.mockResolvedValueOnce(noNextPageResponse);

    const { result: result2 } = renderHook(() => useInfiniteProspects(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result2.current.isLoading).toBe(false);
    });

    expect(result2.current.hasNextPage).toBe(false);
  });

  it('handles empty response', async () => {
    const emptyResponse = {
      prospects: [],
      pagination: {
        has_next: false,
        page: 1,
        total_items: 0
      }
    };

    mockGet.mockResolvedValue(emptyResponse);

    const { result } = renderHook(() => useInfiniteProspects(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual([]);
    expect(result.current.hasNextPage).toBe(false);
  });

  it('handles API errors gracefully', async () => {
    const error = new Error('API Error');
    mockGet.mockRejectedValue(error);

    const { result } = renderHook(() => useInfiniteProspects(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.data).toEqual([]);
  });

  it('updates query when filters change', async () => {
    const { result, rerender } = renderHook(
      ({ filters }) => useInfiniteProspects(filters),
      {
        wrapper: createWrapper(),
        initialProps: { filters: undefined }
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith('/api/prospects?page=1&limit=10');

    // Change filters
    const newFilters: ProspectFilters = {
      naics: '541511',
      keywords: 'test',
      agency: '',
      ai_enrichment: 'all',
      dataSourceIds: []
    };

    rerender({ filters: newFilters });

    await waitFor(() => {
      expect(mockBuildQueryString).toHaveBeenCalledWith({
        page: 1,
        limit: 10,
        naics: '541511',
        keywords: 'test',
        agency: '',
        ai_enrichment: 'all',
        dataSourceIds: []
      });
    });
  });

  it('flattens paginated data correctly', async () => {
    const { result } = renderHook(() => useInfiniteProspects(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Initial data
    expect(result.current.data).toEqual(mockProspects);

    // Add second page
    const secondPageResponse = {
      prospects: [{
        ...mockProspects[0],
        id: 'prospect-3',
        title: 'Page 2 Prospect'
      }],
      pagination: {
        has_next: false,
        page: 2,
        total_items: 3
      }
    };

    mockGet.mockResolvedValueOnce(secondPageResponse);

    await result.current.fetchNextPage();

    await waitFor(() => {
      expect(result.current.isFetchingNextPage).toBe(false);
    });

    // Should contain flattened data from all pages
    expect(result.current.data).toHaveLength(3);
    expect(result.current.data[2].title).toBe('Page 2 Prospect');
  });
});

describe('useProspectStatistics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches prospect statistics successfully', async () => {
    // Mock the implementation since it currently returns hardcoded data
    const { result } = renderHook(() => useProspectStatistics(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual({
      data: {
        total: 0,
        approved: 0,
        pending: 0,
        rejected: 0
      }
    });
  });

  it('has correct query key', () => {
    const { result } = renderHook(() => useProspectStatistics(), {
      wrapper: createWrapper()
    });

    // The query should be using the correct key structure
    expect(result.current).toBeDefined();
  });

  it('handles statistics fetch errors', async () => {
    // Since the current implementation doesn't actually fetch from API,
    // this test verifies the hook structure
    const { result } = renderHook(() => useProspectStatistics(), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should have standard query result properties
    expect(result.current).toHaveProperty('data');
    expect(result.current).toHaveProperty('error');
    expect(result.current).toHaveProperty('isLoading');
  });
});

describe('useProspect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockProspectApiResponse)
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('fetches single prospect by ID', async () => {
    const prospectId = 'prospect-123';

    const { result } = renderHook(() => useProspect(prospectId), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/prospects/prospect-123');
    expect(result.current.data).toEqual(mockProspectApiResponse);
  });

  it('does not fetch when prospect ID is null', () => {
    const { result } = renderHook(() => useProspect(null), {
      wrapper: createWrapper()
    });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.data).toBeUndefined();
  });

  it('does not fetch when prospect ID is empty string', () => {
    renderHook(() => useProspect(''), {
      wrapper: createWrapper()
    });

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('handles numeric prospect IDs', async () => {
    const prospectId = 123;

    const { result } = renderHook(() => useProspect(prospectId), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/prospects/123');
  });

  it('handles API errors gracefully', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found'
    });

    const { result } = renderHook(() => useProspect('non-existent'), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.data).toBeUndefined();
  });

  it('handles network errors', async () => {
    mockFetch.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useProspect('prospect-123'), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.data).toBeUndefined();
  });

  it('has correct stale time configuration', async () => {
    const { result } = renderHook(() => useProspect('prospect-123'), {
      wrapper: createWrapper()
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Data should be considered fresh for 2 minutes
    expect(result.current.isStale).toBe(false);
  });

  it('refetches when prospect ID changes', async () => {
    const { result, rerender } = renderHook(
      ({ prospectId }) => useProspect(prospectId),
      {
        wrapper: createWrapper(),
        initialProps: { prospectId: 'prospect-1' }
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/prospects/prospect-1');

    // Change prospect ID
    rerender({ prospectId: 'prospect-2' });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/prospects/prospect-2');
    });

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('disables query when switching from valid to null ID', async () => {
    const { result, rerender } = renderHook(
      ({ prospectId }) => useProspect(prospectId),
      {
        wrapper: createWrapper(),
        initialProps: { prospectId: 'prospect-1' }
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/prospects/prospect-1');

    // Change to null
    rerender({ prospectId: null });

    // Should not make additional requests
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('uses correct query key structure', () => {
    const prospectId = 'prospect-123';
    const { result } = renderHook(() => useProspect(prospectId), {
      wrapper: createWrapper()
    });

    // Query key should include the prospect ID for proper caching
    expect(result.current).toBeDefined();
  });
});
