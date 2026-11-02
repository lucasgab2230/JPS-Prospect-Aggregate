import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { DataSource } from '@/types';
import { get, post, put, del } from '@/utils/apiUtils';

// --- API Call Functions ---

async function fetchDataSourcesAPI(): Promise<{ status: string; data: DataSource[] }> {
  return get<{ status: string; data: DataSource[] }>('/api/data-sources/public');
}

async function createDataSourceAPI(newDataSource: Omit<DataSource, 'id'>): Promise<DataSource> {
  return post<DataSource>('/api/data-sources', newDataSource);
}

async function updateDataSourceAPI({ id, ...updatedData }: Partial<DataSource> & { id: DataSource['id'] }): Promise<DataSource> {
  return put<DataSource>(`/api/data-sources/${id}`, updatedData);
}

async function deleteDataSourceAPI(dataSourceId: DataSource['id']): Promise<void> {
  return del<void>(`/api/data-sources/${dataSourceId}`);
}

async function clearDataSourceDataAPI(dataSourceId: DataSource['id']): Promise<{ status: string; message: string; deleted_count: number }> {
  return post<{ status: string; message: string; deleted_count: number }>(`/api/data-sources/${dataSourceId}/clear-data`);
}

// --- React Query Hooks ---

const dataSourceQueryKeys = {
  all: () => ['dataSources'] as const,
  lists: () => [...dataSourceQueryKeys.all(), 'list'] as const,
  list: (filters: string) => [...dataSourceQueryKeys.lists(), { filters }] as const,
  details: () => [...dataSourceQueryKeys.all(), 'detail'] as const,
  detail: (id: DataSource['id']) => [...dataSourceQueryKeys.details(), id] as const,
};


export function useListDataSources() {
  return useQuery({
    queryKey: dataSourceQueryKeys.lists(),
    queryFn: fetchDataSourcesAPI,
    staleTime: 5 * 60 * 1000, // 5 minutes
    // Add other React Query options as needed, e.g., onSuccess, onError, refetchOnWindowFocus: false
  });
}

// Admin-only hook for full data source management
export function useListDataSourcesAdmin(options?: { refetchInterval?: number; refetchIntervalInBackground?: boolean; enabled?: boolean }) {
  return useQuery({
    queryKey: ['dataSources', 'admin'],
    queryFn: () => get<{ status: string; data: DataSource[] }>('/api/data-sources'),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: options?.refetchInterval,
    refetchIntervalInBackground: options?.refetchIntervalInBackground,
    enabled: options?.enabled !== false, // Default to true if not specified
  });
}

export function useCreateDataSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDataSourceAPI,
    onSuccess: () => {
      // Invalidate and refetch the list of data sources
      queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.lists() });
      // Optionally, update the cache directly if the API returns the created item
      // queryClient.setQueryData(dataSourceQueryKeys.list(), (oldData: DataSource[] | undefined) => [...(oldData || []), data]);
    },
    // Add other React Query options as needed, e.g., onError, onMutate
  });
}

export function useUpdateDataSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateDataSourceAPI,
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.detail(variables.id) });
      // Optionally, update the cache directly
      // queryClient.setQueryData(dataSourceQueryKeys.detail(variables.id), data);
      // queryClient.setQueryData(dataSourceQueryKeys.list(), (oldData: DataSource[] | undefined) =>
      //   oldData?.map(item => item.id === variables.id ? data : item) || []
      // );
    },
  });
}

export function useDeleteDataSource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteDataSourceAPI,
    onSuccess: () => {
      // Invalidate and refetch the list of data sources
      queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.lists() });
      // Optimistic update: Remove the item from the cache immediately
      // queryClient.setQueryData(dataSourceQueryKeys.list(), (oldData: DataSource[] | undefined) =>
      //   oldData?.filter(ds => ds.id !== dataSourceId) || []
      // );
    },
  });
}

export function useClearDataSourceData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: clearDataSourceDataAPI,
    onSuccess: () => {
      // Invalidate and refetch the list of data sources to update prospect counts
      queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.lists() });
      // Also invalidate the general dataSources query used in Advanced.tsx
      queryClient.invalidateQueries({ queryKey: ['dataSources'] });
    },
  });
}

// If you need a hook for fetching a single data source by ID:
// export function useDataSource(id: DataSource['id']) {
//   return useQuery({
//     queryKey: dataSourceQueryKeys.detail(id),
//     queryFn: () => fetchDataSourcesAPI().then(sources => sources.find(s => s.id === id)), // Highly inefficient, fetch by ID directly
//     enabled: !!id, // Only run query if ID is provided
//   });
// }
