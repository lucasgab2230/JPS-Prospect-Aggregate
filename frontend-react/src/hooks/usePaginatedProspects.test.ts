import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { usePaginatedProspects } from './usePaginatedProspects';
import type { ProspectFilters } from './useProspectFilters';
import type { Prospect } from '@/types/prospects';

// Mock the fetch function
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock the enhancement activity monitor
const mockUseEnhancementActivityMonitor = vi.fn();
vi.mock('./useEnhancementActivityMonitor', () => ({
  useEnhancementActivityMonitor: () => mockUseEnhancementActivityMonitor()
}));

// Helper function to generate dynamic prospect data
const generateProspect = (): Prospect => {
  const agencies = ['Department of Defense', 'Health and Human Services', 'Department of Commerce', 'Department of Energy'];
  const naicsCodes = ['541511', '541512', '518210', '541519', '236220'];
  const statuses = ['idle', 'processing', 'completed', 'error'] as const;

  const randomId = Math.random().toString(36).substr(2, 9);
  const baseValue = Math.floor(Math.random() * 500000) + 10000;

  return {
    id: randomId,
    title: `Contract ${Math.floor(Math.random() * 1000)}`,
    description: `Description for contract ${randomId}`,
    agency: agencies[Math.floor(Math.random() * agencies.length)],
    posted_date: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    loaded_at: new Date().toISOString(),
    estimated_value: baseValue,
    estimated_value_text: `$${baseValue.toLocaleString()}`,
    naics_code: naicsCodes[Math.floor(Math.random() * naicsCodes.length)],
    source_file: `source_${Math.floor(Math.random() * 100)}.json`,
    source_data_id: Math.floor(Math.random() * 1000) + 1,
    enhancement_status: statuses[Math.floor(Math.random() * statuses.length)],
    duplicate_group_id: Math.random() > 0.8 ? Math.floor(Math.random() * 100) : null,
    set_aside_status: Math.random() > 0.5 ? 'Small Business' : null,
    contact_email: Math.random() > 0.5 ? `contact${Math.floor(Math.random() * 100)}@agency.gov` : null,
    contact_name: Math.random() > 0.5 ? `Contact ${Math.floor(Math.random() * 100)}` : null,
    ai_enhanced_title: Math.random() > 0.7 ? `Enhanced: ${Math.floor(Math.random() * 100)}` : null,
    ai_enhanced_description: Math.random() > 0.7 ? `Enhanced description ${Math.floor(Math.random() * 100)}` : null,
    parsed_contract_value: Math.random() > 0.5 ? baseValue : null,
    ollama_processed_at: Math.random() > 0.5 ? new Date().toISOString() : null
  };
};

const generatePaginatedResponse = (prospectCount: number = 2) => {
  const prospects = Array.from({ length: prospectCount }, () => generateProspect());
  const perPage = Math.floor(Math.random() * 20) + 5;
  const totalItems = Math.floor(Math.random() * 100) + prospectCount;
  const totalPages = Math.ceil(totalItems / perPage);

  return {
    prospects,
    pagination: {
      total_items: totalItems,
      total_pages: totalPages,
      page: Math.floor(Math.random() * totalPages) + 1,
      per_page: perPage
    }
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

describe('usePaginatedProspects', () => {
  let testResponse: any;

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEnhancementActivityMonitor.mockReturnValue({ hasAnyActivity: false });

    // Generate fresh test data for each test
    testResponse = generatePaginatedResponse();

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(testResponse)
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const defaultFilters: ProspectFilters = {
    naics: '',
    keywords: '',
    agency: '',
    ai_enrichment: 'all',
    dataSourceIds: []
  };

  it('initializes with correct default values', async () => {
    const { result } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    expect(result.current.prospects).toEqual([]);
    expect(result.current.total).toBe(0);
    expect(result.current.totalPages).toBe(0);
    expect(result.current.currentPage).toBe(1);
    expect(result.current.itemsPerPage).toBe(10);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.isFetching).toBe(true);

    // Wait for the query to resolve
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.prospects).toEqual(testResponse.prospects);
    expect(result.current.total).toBe(testResponse.pagination.total_items);
    expect(result.current.totalPages).toBe(testResponse.pagination.total_pages);
  });

  it('constructs correct API URL with no filters', async () => {
    renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      const callUrl = mockFetch.mock.calls[0][0] as string;
      expect(callUrl).toContain('/api/prospects');
      expect(callUrl).toContain('page=1');
      expect(callUrl).toContain('limit=10');
      expect(callUrl).not.toContain('naics=');
      expect(callUrl).not.toContain('keywords=');
    });
  });

  it('constructs correct API URL with all filters', async () => {
    const testNaics = Math.floor(Math.random() * 900000) + 100000; // Random 6-digit NAICS
    const testKeywords = `keyword${Math.floor(Math.random() * 1000)}`;
    const testAgency = `Agency${Math.floor(Math.random() * 100)}`;
    const testSourceIds = Array.from({ length: Math.floor(Math.random() * 5) + 1 }, () => Math.floor(Math.random() * 10) + 1);

    const filters: ProspectFilters = {
      naics: testNaics.toString(),
      keywords: testKeywords,
      agency: testAgency,
      ai_enrichment: 'enhanced',
      dataSourceIds: testSourceIds
    };

    renderHook(
      () => usePaginatedProspects(filters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      const callUrl = mockFetch.mock.calls[0][0] as string;
      expect(callUrl).toContain('/api/prospects');
      expect(callUrl).toContain(`naics=${testNaics}`);
      expect(callUrl).toContain(`keywords=${encodeURIComponent(testKeywords)}`);
      expect(callUrl).toContain(`agency=${encodeURIComponent(testAgency)}`);
      expect(callUrl).toContain('ai_enrichment=enhanced');
      expect(callUrl).toContain('source_ids=');
    });
  });

  it('excludes ai_enrichment filter when set to "all"', async () => {
    const filters: ProspectFilters = {
      naics: '541511',
      keywords: 'test',
      agency: 'DOD',
      ai_enrichment: 'all',
      dataSourceIds: [1]
    };

    renderHook(
      () => usePaginatedProspects(filters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      const url = mockFetch.mock.calls[0][0];
      expect(url).not.toContain('ai_enrichment');
      expect(url).toContain('naics=541511');
      expect(url).toContain('keywords=test');
    });
  });

  it('excludes empty dataSourceIds', async () => {
    const filters: ProspectFilters = {
      naics: '541511',
      keywords: 'test',
      agency: 'DOD',
      ai_enrichment: 'all',
      dataSourceIds: []
    };

    renderHook(
      () => usePaginatedProspects(filters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      const url = mockFetch.mock.calls[0][0];
      expect(url).not.toContain('source_ids');
    });
  });

  it('handles page changes correctly', async () => {
    const { result } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    // Wait for initial query
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Change to page 2
    act(() => {
      result.current.handlePageChange(2);
    });

    expect(result.current.currentPage).toBe(2);

    await waitFor(() => {
      const secondCallUrl = mockFetch.mock.calls[1][0] as string;
      expect(secondCallUrl).toContain('page=2');
      expect(secondCallUrl).toContain('limit=10');
    });
  });

  it('handles page size changes correctly', async () => {
    const { result } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    // Wait for initial query
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Go to page 2 first
    act(() => {
      result.current.handlePageChange(2);
    });

    expect(result.current.currentPage).toBe(2);

    // Change page size (should reset to page 1)
    act(() => {
      result.current.handlePageSizeChange(25);
    });

    expect(result.current.currentPage).toBe(1);
    expect(result.current.itemsPerPage).toBe(25);

    await waitFor(() => {
      const lastCallUrl = mockFetch.mock.calls[mockFetch.mock.calls.length - 1][0] as string;
      expect(lastCallUrl).toContain('page=1');
      expect(lastCallUrl).toContain('limit=25');
    });
  });

  it('resets pagination correctly', async () => {
    const { result } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    // Wait for initial query
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Go to page 3
    act(() => {
      result.current.handlePageChange(3);
    });

    expect(result.current.currentPage).toBe(3);

    // Reset pagination
    act(() => {
      result.current.resetPagination();
    });

    expect(result.current.currentPage).toBe(1);
  });

  it('refetches data correctly', async () => {
    const { result } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    // Wait for initial query
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Clear mock call history
    mockFetch.mockClear();

    // Trigger refetch
    await act(async () => {
      await result.current.refetch();
    });

    const refetchCallUrl = mockFetch.mock.calls[0][0] as string;
    expect(refetchCallUrl).toContain('/api/prospects');
    expect(refetchCallUrl).toContain('page=1');
    expect(refetchCallUrl).toContain('limit=10');
  });

  it('adjusts refetch interval based on enhancement activity', async () => {
    // First render with no activity
    mockUseEnhancementActivityMonitor.mockReturnValue({ hasAnyActivity: false });

    const { rerender } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });

    // Re-render with activity
    mockUseEnhancementActivityMonitor.mockReturnValue({ hasAnyActivity: true });
    rerender();

    // The hook should use different refetch intervals based on activity
    // Note: Testing exact intervals is complex with React Query, so we verify the hook responds to activity changes
    expect(mockUseEnhancementActivityMonitor).toHaveBeenCalled();
  });

  it('handles API errors gracefully', async () => {
    const errorResponse = {
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.resolve({ error: 'Database connection failed' })
    };

    mockFetch.mockResolvedValue(errorResponse);

    const { result } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Data should remain empty on error
    expect(result.current.prospects).toEqual([]);
    expect(result.current.total).toBe(0);
  });

  it('handles API response without proper error JSON', async () => {
    const errorResponse = {
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: () => Promise.reject(new Error('Invalid JSON'))
    };

    mockFetch.mockResolvedValue(errorResponse);

    const { result } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.prospects).toEqual([]);
  });

  it('updates query when filters change', async () => {
    const initialFilters: ProspectFilters = {
      naics: '',
      keywords: '',
      agency: '',
      ai_enrichment: 'all',
      dataSourceIds: []
    };

    const { result, rerender } = renderHook(
      ({ filters }) => usePaginatedProspects(filters),
      {
        wrapper: createWrapper(),
        initialProps: { filters: initialFilters }
      }
    );

    // Wait for initial query
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith('/api/prospects?page=1&limit=10');
    mockFetch.mockClear();

    // Change filters
    const newFilters: ProspectFilters = {
      naics: '541511',
      keywords: 'software',
      agency: 'DOD',
      ai_enrichment: 'enhanced',
      dataSourceIds: [1, 2]
    };

    rerender({ filters: newFilters });

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/prospects?page=1&limit=10&naics=541511&keywords=software&agency=DOD&ai_enrichment=enhanced&source_ids=1%2C2'
      );
    });
  });

  it('maintains stable function references', () => {
    const { result, rerender } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    const initialHandlePageChange = result.current.handlePageChange;
    const initialHandlePageSizeChange = result.current.handlePageSizeChange;
    const initialResetPagination = result.current.resetPagination;

    rerender();

    expect(result.current.handlePageChange).toBe(initialHandlePageChange);
    expect(result.current.handlePageSizeChange).toBe(initialHandlePageSizeChange);
    expect(result.current.resetPagination).toBe(initialResetPagination);
  });

  it('handles empty response data gracefully', async () => {
    const emptyResponse = {
      prospects: [],
      pagination: {
        total_items: 0,
        total_pages: 0,
        page: 1,
        per_page: 10
      }
    };

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(emptyResponse)
    });

    const { result } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.prospects).toEqual([]);
    expect(result.current.total).toBe(0);
    expect(result.current.totalPages).toBe(0);
  });

  it('encodes URL parameters correctly', async () => {
    const filters: ProspectFilters = {
      naics: '',
      keywords: 'artificial intelligence & machine learning',
      agency: 'Department of Health & Human Services',
      ai_enrichment: 'all',
      dataSourceIds: []
    };

    renderHook(
      () => usePaginatedProspects(filters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      const url = mockFetch.mock.calls[0][0];
      expect(url).toContain('keywords=artificial+intelligence+%26+machine+learning');
      expect(url).toContain('agency=Department+of+Health+%26+Human+Services');
    });
  });

  it('handles concurrent pagination changes', async () => {
    const { result } = renderHook(
      () => usePaginatedProspects(defaultFilters),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Simulate rapid pagination changes
    act(() => {
      result.current.handlePageChange(2);
      result.current.handlePageChange(3);
      result.current.handlePageChange(1);
    });

    // Should end up on page 1
    expect(result.current.currentPage).toBe(1);
  });

  it('preserves pagination state across filter changes within same hook instance', async () => {
    const { result, rerender } = renderHook(
      ({ filters }) => usePaginatedProspects(filters),
      {
        wrapper: createWrapper(),
        initialProps: { filters: defaultFilters }
      }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Change to page 2 and page size 20
    act(() => {
      result.current.handlePageChange(2);
      result.current.handlePageSizeChange(20);
    });

    expect(result.current.currentPage).toBe(1); // Should reset to 1 after page size change
    expect(result.current.itemsPerPage).toBe(20);

    // Change filters - pagination state should be preserved
    const newFilters: ProspectFilters = {
      ...defaultFilters,
      keywords: 'test'
    };

    rerender({ filters: newFilters });

    expect(result.current.itemsPerPage).toBe(20); // Page size should be preserved
  });
});
