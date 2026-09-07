import { useMutation, useQueryClient } from '@tanstack/react-query';
import { postProcessing } from '@/utils/apiUtils';
import { useClearDataSourceData, useListDataSourcesAdmin } from '@/hooks/api/useDataSources';
import { useToast } from '@/contexts/ToastContext';
import { formatScraperResults } from '@/utils/statusUtils';
import { DataSource } from '@/types';
import { ErrorSeverity, ErrorCategory } from '@/types/errors';

interface ScraperResult {
  source_name: string;
  source_id: number;
  status: string;
  duration: number;
  message?: string;
  error?: string;
}

export function useDataSourceManagement(enabled: boolean = true) {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast, showInfoToast } = useToast();
  const clearDataMutation = useClearDataSourceData();

  // Fetch data sources with frequent updates when scrapers are running
  // Using admin endpoint for full data (includes status, last_scraped, etc.)
  const { data: sourcesData, isLoading, error } = useListDataSourcesAdmin({
    refetchInterval: 5000, // Check every 5 seconds for simplicity
    refetchIntervalInBackground: true,
    enabled,
  });
  const sources = sourcesData;

  // Mutation for running all scrapers
  const runAllScrapersMutation = useMutation({
    mutationFn: () => postProcessing<{
      message: string;
      total_duration: number;
      results?: ScraperResult[];
    }>('/api/data-sources/run-all', undefined, {
      deduplicate: true,
      deduplicationKey: 'run-all-scrapers'
    }),
    onMutate: () => {
      // Show initial toast when scrapers start
      showInfoToast('Scrapers Started', 'Running all scrapers... This may take several minutes.');
    },
    onSuccess: (data) => {
      // All scrapers completed - show results
      if (data.results) {
        const { message, failedCount } = formatScraperResults(data.results, data.total_duration);

        // Show appropriate toast based on results
        if (failedCount === 0) {
          showSuccessToast('All Scrapers Completed', message);
        } else if (failedCount === data.results.length) {
          showErrorToast({
            code: 'ALL_SCRAPERS_FAILED',
            message: message,
            severity: ErrorSeverity.ERROR,
            category: ErrorCategory.SYSTEM,
            timestamp: new Date(),
            userMessage: message,
          });
        } else {
          // Some succeeded, some failed
          showInfoToast('Scrapers Completed with Errors', message);
        }
      }
    },
    onError: (error) => {
      showErrorToast({
        code: 'RUN_ALL_SCRAPERS_ERROR',
        message: error instanceof Error ? error.message : 'Failed to run scrapers',
        severity: ErrorSeverity.ERROR,
        category: ErrorCategory.SYSTEM,
        timestamp: new Date(),
        userMessage: 'Failed to start scrapers. Please try again.',
      });
    },
    onSettled: () => {
      // Refetch data sources to update status
      queryClient.invalidateQueries({ queryKey: ['dataSources'] });
    },
  });

  // Handle clearing data source data
  const handleClearData = async (id: DataSource['id'], sourceName: string) => {
    try {
      const result = await clearDataMutation.mutateAsync(id);
      showSuccessToast(
        'Data Cleared',
        `Successfully cleared ${result.deleted_count} prospects from ${sourceName}.`
      );
      // Query invalidation is handled by the mutation's onSuccess
    } catch (err) {
      // Failed to clear data source data
      showErrorToast({
        code: 'CLEAR_DATA_ERROR',
        message: err instanceof Error ? err.message : 'Failed to clear data source data',
        severity: ErrorSeverity.ERROR,
        category: ErrorCategory.SYSTEM,
        timestamp: new Date(),
        userMessage: 'Failed to clear data source data. Please try again.',
      });
    }
  };

  return {
    // Data
    sources,
    isLoading,
    error,

    // Mutations
    runAllScrapersMutation,
    clearDataMutation,

    // Handlers
    handleClearData,
  };
}
