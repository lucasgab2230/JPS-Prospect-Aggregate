import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { get, post, buildQueryString } from '@/utils/apiUtils';
import { LLMParsedResult } from '@/types';

/**
 * Unified queue management service that consolidates all queue-related operations
 * and monitoring into a single interface
 */

// Queue item types
export interface QueueItem {
  id: string;
  type: 'individual' | 'bulk';
  priority: number;
  prospect_id?: number;
  prospect_count: number;
  enhancement_type: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: {
    processed: number;
    total: number;
    enhancements?: string[];
  };
  error_message?: string;
}

// Queue status overview
export interface QueueStatus {
  worker_running: boolean;
  current_item?: string;
  queue_size: number;
  pending_items: QueueItem[];
  recent_completed: Array<{
    id: string;
    type: 'individual' | 'bulk';
    prospect_id?: number;
    status: string;
    completed_at?: string;
    error_message?: string;
  }>;
}

// Iterative enhancement progress
export interface IterativeProgress {
  status: 'idle' | 'processing' | 'completed' | 'stopped' | 'stopping' | 'error';
  current_type: 'all' | 'values' | 'naics' | 'titles' | null;
  processed: number;
  total: number;
  percentage: number;
  current_prospect: {
    id: number;
    title: string;
  } | null;
  started_at: string | null;
  errors: Array<{
    prospect_id: number;
    error?: string;
    timestamp: string;
  }>;
  error_message?: string;
}

// AI enrichment status
export interface AIEnrichmentStatus {
  total_prospects: number;
  processed_prospects: number;
  naics_coverage: {
    original: number;
    llm_inferred: number;
    total_percentage: number;
  };
  value_parsing: {
    parsed_count: number;
    total_percentage: number;
  };
  set_aside_standardization: {
    standardized_count: number;
    total_percentage: number;
  };
  title_enhancement: {
    enhanced_count: number;
    total_percentage: number;
  };
  last_processed: string | null;
  model_version: string | null;
}

// LLM output log entry
export interface LLMOutput {
  id: number;
  timestamp: string;
  prospect_id: string;
  prospect_title: string | null;
  enhancement_type: 'values' | 'naics' | 'titles' | 'set_asides';
  prompt: string;
  response: string;
  parsed_result: LLMParsedResult;
  success: boolean;
  error_message: string | null;
  processing_time: number | null;
}

// Query keys
const queryKeys = {
  queueStatus: ['enhancement-queue-status'] as const,
  queueItem: (id: string) => ['queue-item-status', id] as const,
  iterativeProgress: ['iterative-progress'] as const,
  enrichmentStatus: ['ai-enrichment-status'] as const,
  llmOutputs: (type?: string) => ['llm-outputs', type] as const,
};

/**
 * Main queue service hook that provides all queue-related functionality
 */
export function useEnhancementQueueService(options?: {
  llmOutputsLimit?: number;
  llmOutputsType?: 'all' | 'values' | 'naics' | 'titles' | 'set_asides';
}) {
  const queryClient = useQueryClient();
  const { llmOutputsLimit = 50, llmOutputsType = 'all' } = options || {};

  // Queue status monitoring
  const queueStatus = useQuery<QueueStatus>({
    queryKey: queryKeys.queueStatus,
    queryFn: () => get<QueueStatus>('/api/llm/queue/status'),
    refetchInterval: 1000,
    staleTime: 500,
    refetchOnWindowFocus: true
  });

  // Iterative enhancement progress
  const iterativeProgress = useQuery<IterativeProgress>({
    queryKey: queryKeys.iterativeProgress,
    queryFn: () => get<IterativeProgress>('/api/llm/iterative/progress'),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === 'processing' ? 1000 : 5000;
    },
  });

  // AI enrichment status
  const enrichmentStatus = useQuery<AIEnrichmentStatus>({
    queryKey: queryKeys.enrichmentStatus,
    queryFn: () => get<AIEnrichmentStatus>('/api/llm/status'),
    refetchInterval: 30000, // Every 30 seconds
  });

  // LLM output logs
  const llmOutputs = useQuery<LLMOutput[]>({
    queryKey: queryKeys.llmOutputs(llmOutputsType),
    queryFn: async () => {
      const queryParams = buildQueryString({
        limit: llmOutputsLimit,
        enhancement_type: llmOutputsType
      });
      return await get<LLMOutput[]>(`/api/llm/outputs${queryParams}`);
    },
    refetchInterval: 2000, // Refresh every 2 seconds to show new outputs
  });

  // Queue item details query options
  const getQueueItemOptions = (itemId: string | undefined) => ({
    queryKey: queryKeys.queueItem(itemId!),
    queryFn: () => get<QueueItem>(`/api/llm/queue/item/${itemId}`),
    enabled: !!itemId,
    refetchInterval: 1000,
    staleTime: 500
  });

  // Cancel queue item
  const cancelQueueItem = useMutation({
    mutationFn: async (itemId: string) => {
      const response = await post(`/api/llm/queue/item/${itemId}/cancel`);
      return response;
    },
    onSuccess: (_, itemId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queueStatus });
      queryClient.invalidateQueries({ queryKey: queryKeys.queueItem(itemId) });
    },
    onError: (error: Error) => {
      if (window.showToast) {
        window.showToast({
          title: 'Failed to cancel',
          message: error.message || 'Unknown error',
          type: 'error',
          duration: 3000
        });
      }
    }
  });

  // Start queue worker
  const startWorker = useMutation({
    mutationFn: () => post('/api/llm/queue/start-worker'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queueStatus });
      if (window.showToast) {
        window.showToast({
          title: 'Worker Started',
          message: 'Enhancement queue worker is now running',
          type: 'success',
          duration: 2000
        });
      }
    },
    onError: (error: Error) => {
      if (window.showToast) {
        window.showToast({
          title: 'Failed to start worker',
          message: error.message || 'Unknown error',
          type: 'error',
          duration: 3000
        });
      }
    }
  });

  // Stop queue worker
  const stopWorker = useMutation({
    mutationFn: () => post('/api/llm/queue/stop-worker'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.queueStatus });
      if (window.showToast) {
        window.showToast({
          title: 'Worker Stopped',
          message: 'Enhancement queue worker has been stopped',
          type: 'info',
          duration: 2000
        });
      }
    },
    onError: (error: Error) => {
      if (window.showToast) {
        window.showToast({
          title: 'Failed to stop worker',
          message: error.message || 'Unknown error',
          type: 'error',
          duration: 3000
        });
      }
    }
  });

  // Start iterative enhancement
  const startIterative = useMutation({
    mutationFn: async (params: {
      enhancement_type: 'all' | 'values' | 'naics' | 'titles' | 'set_asides';
      skip_existing?: boolean;
    }) => {
      return await post('/api/llm/iterative/start', params);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.iterativeProgress });
      queryClient.invalidateQueries({ queryKey: queryKeys.enrichmentStatus });
      if (window.showToast) {
        window.showToast({
          title: 'Enhancement Started',
          message: 'Iterative enhancement process has begun',
          type: 'success',
          duration: 2000
        });
      }
    },
    onError: (error: Error) => {
      if (window.showToast) {
        window.showToast({
          title: 'Failed to start enhancement',
          message: error.message || 'Unknown error',
          type: 'error',
          duration: 3000
        });
      }
    }
  });

  // Stop iterative enhancement
  const stopIterative = useMutation({
    mutationFn: () => post('/api/llm/iterative/stop'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.iterativeProgress });
      queryClient.invalidateQueries({ queryKey: queryKeys.enrichmentStatus });
      queryClient.invalidateQueries({ queryKey: queryKeys.llmOutputs() });
      if (window.showToast) {
        window.showToast({
          title: 'Enhancement Stopping',
          message: 'Iterative enhancement will stop after current prospect',
          type: 'info',
          duration: 2000
        });
      }
    },
    onError: (error: Error) => {
      if (window.showToast) {
        window.showToast({
          title: 'Failed to stop enhancement',
          message: error.message || 'Unknown error',
          type: 'error',
          duration: 3000
        });
      }
    }
  });

  // Computed values
  const isWorkerRunning = queueStatus.data?.worker_running || false;
  const queueSize = queueStatus.data?.queue_size || 0;
  const currentItem = queueStatus.data?.current_item;
  const pendingItems = queueStatus.data?.pending_items || [];
  const recentCompleted = queueStatus.data?.recent_completed || [];

  const isIterativeProcessing = iterativeProgress.data?.status === 'processing';
  const iterativePercentage = iterativeProgress.data?.percentage || 0;

  const totalProspects = enrichmentStatus.data?.total_prospects || 0;
  const processedProspects = enrichmentStatus.data?.processed_prospects || 0;

  return {
    // Status queries
    queueStatus: queueStatus.data,
    iterativeProgress: iterativeProgress.data,
    enrichmentStatus: enrichmentStatus.data,
    llmOutputs: llmOutputs.data,

    // Loading states
    isLoadingQueue: queueStatus.isLoading,
    isLoadingIterative: iterativeProgress.isLoading,
    isLoadingEnrichment: enrichmentStatus.isLoading,
    isLoadingLLMOutputs: llmOutputs.isLoading,

    // Computed values
    isWorkerRunning,
    queueSize,
    currentItem,
    pendingItems,
    recentCompleted,
    isIterativeProcessing,
    iterativePercentage,
    totalProspects,
    processedProspects,

    // Actions
    getQueueItemOptions,
    cancelQueueItem: cancelQueueItem.mutate,
    startWorker: startWorker.mutate,
    stopWorker: stopWorker.mutate,
    startIterative: startIterative.mutate,
    stopIterative: stopIterative.mutate,

    // Action states
    isCancelling: cancelQueueItem.isPending,
    isStartingWorker: startWorker.isPending,
    isStoppingWorker: stopWorker.isPending,
    isStartingIterative: startIterative.isPending,
    isStoppingIterative: stopIterative.isPending,

    // Refetch functions
    refetchQueueStatus: queueStatus.refetch,
    refetchIterativeProgress: iterativeProgress.refetch,
    refetchEnrichmentStatus: enrichmentStatus.refetch,
    refetchLLMOutputs: llmOutputs.refetch,
  };
}
