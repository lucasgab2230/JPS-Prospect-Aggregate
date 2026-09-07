import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { Prospect, ProspectFilters, ProspectStatistics } from '@/types/prospects';
import { ApiResponse } from '@/types/api';
import { get, buildQueryString } from '@/utils/apiUtils';

// --- API Call Functions ---

// Simulate a paginated API response structure
interface PaginatedProspectsResponse {
  data: Prospect[];
  nextCursor?: number | null;
  totalCount: number;
}

async function fetchProspectsAPI(
  { pageParam = 0, filters }: { pageParam?: number; filters?: ProspectFilters }
): Promise<PaginatedProspectsResponse> {
  // Fetching prospects with pagination

  const params: Record<string, string | number | boolean | Array<string | number>> = {
    page: pageParam + 1, // Backend is 1-indexed
    limit: 10,
    ...filters
  };

  // Backend uses 1-indexed pagination

  const url = `/api/prospects${buildQueryString(params)}`;
  const responseJson = await get<{
    prospects: Prospect[];
    pagination?: {
      has_next: boolean;
      page: number;
      total_items: number;
    };
  }>(url);

  // Transform backend response

  const transformedData = {
    data: responseJson.prospects || [],
    nextCursor: responseJson.pagination?.has_next ? responseJson.pagination.page : undefined,
    totalCount: responseJson.pagination?.total_items || 0,
  };
  // Return transformed data
  return transformedData;
}

async function fetchProspectStatisticsAPI(): Promise<ProspectStatistics> {
  // Fetching prospect statistics
  await new Promise(resolve => setTimeout(resolve, 300));
  return {
    data: {
        total: 0,
        approved: 0,
        pending: 0,
        rejected: 0,
    }
  };
}


// --- React Query Hooks ---

const prospectQueryKeys = {
  all: () => ['prospects'] as const,
  lists: () => [...prospectQueryKeys.all(), 'list'] as const,
  list: (filters?: ProspectFilters) => [...prospectQueryKeys.lists(), { filters }] as const, // Infinite query key usually includes filters
  statistics: () => [...prospectQueryKeys.all(), 'statistics'] as const,
  details: () => [...prospectQueryKeys.all(), 'detail'] as const, // For individual prospect details if needed
  detail: (id: Prospect['id']) => [...prospectQueryKeys.details(), id] as const, // For individual prospect details
};

export function useInfiniteProspects(filters?: ProspectFilters) {
  const result = useInfiniteQuery({
    queryKey: prospectQueryKeys.list(filters),
    queryFn: ({ pageParam = 0 }) => fetchProspectsAPI({ pageParam, filters }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      // lastPage.nextCursor is the 'page' number from the backend's pagination response for the *last fetched page*.
      // If it exists (meaning has_next was true), it means there's potentially another page.
      // react-query will pass this returned value as `pageParam` to `fetchProspectsAPI` for the next fetch.
      // The value itself should be the page number that was *just fetched* if a next page exists.
      // Calculate next page parameter
      return lastPage.nextCursor ? lastPage.nextCursor : undefined;
    },
  });

  // Flatten paginated data
  const flattenedData = result.data?.pages.flatMap(page => page.data) ?? [];
  // Return flattened data

  return {
    ...result,
    data: flattenedData, // Override data with the flattened array
    // fetchNextPage, hasNextPage, isFetchingNextPage are already part of result
  };
}

export function useProspectStatistics() {
  return useQuery({
    queryKey: prospectQueryKeys.statistics(),
    queryFn: fetchProspectStatisticsAPI,
    // Configure options like staleTime if needed
  });
}

// Hook to get a single prospect by ID
export function useProspect(prospectId: string | number | null) {
  return useQuery({
    queryKey: ['prospects', prospectId],
    queryFn: async () => {
      const response = await fetch(`/api/prospects/${prospectId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch prospect');
      }
      return response.json() as Promise<ApiResponse<Prospect>>;
    },
    enabled: !!prospectId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
