import { useState } from 'react';
import { useMutation, useQueryClient, UseMutationResult } from '@tanstack/react-query';
import { post } from '@/utils/apiUtils';
import { DataSource } from '@/types';

interface ScraperResult {
  source_name: string;
  source_id: number;
  status: string;
  duration: number;
  message?: string;
  error?: string;
}

export function useScraperOperations() {
  const queryClient = useQueryClient();
  const [runningScrapers, setRunningScrapers] = useState<Set<number>>(new Set());
  const [runAllInProgress, setRunAllInProgress] = useState(false);

  // Track which scrapers are actually working based on API status
  const [workingScrapers] = useState(() => new Set<number>());

  // Mutation for running individual scraper
  const runScraperMutation = useMutation({
    mutationFn: (sourceId: number) => post(`/api/data-sources/${sourceId}/pull`),
    onMutate: (sourceId) => {
      // Only track the API call, not the scraper status
      setRunningScrapers(prev => new Set(prev).add(sourceId));
    },
    onSettled: (_, __, sourceId) => {
      // Remove from API call tracking
      setRunningScrapers(prev => {
        const next = new Set(prev);
        next.delete(sourceId);
        return next;
      });
      // Immediately refetch to get updated status
      queryClient.invalidateQueries({ queryKey: ['dataSources'] });
    },
    onError: () => {
      // Scraper start failed
    },
  });

  // Update working scrapers when sources data changes
  const updateWorkingScrapers = (sources: DataSource[]) => {
    const currentlyWorking = new Set(
      sources.filter(source => source.status === 'working').map(source => source.id)
    );

    // Update the working scrapers set
    workingScrapers.clear();
    currentlyWorking.forEach(id => workingScrapers.add(id));
  };

  // Handle running individual scraper
  const handleRunScraper = (sourceId: number) => {
    runScraperMutation.mutate(sourceId);
  };

  // Handle running all scrapers with progress tracking
  const handleRunAllScrapers = (runAllMutation: UseMutationResult<{
    message: string;
    total_duration: number;
    results?: ScraperResult[];
  }, Error, void, unknown>) => {
    setRunAllInProgress(true);
    return runAllMutation.mutate(undefined, {
      onSettled: () => {
        setRunAllInProgress(false);
      },
    });
  };

  // Get scraper button state
  const getScraperButtonState = (source: DataSource) => {
    const isApiCallInProgress = runningScrapers.has(source.id);
    const isScraperWorking = source.status === 'working';
    const isDisabled = runAllInProgress || isScraperWorking || isApiCallInProgress;

    // Determine button text and loading state
    let buttonText = 'Run Scraper';
    let isLoading = false;

    if (isScraperWorking) {
      buttonText = 'Running...';
      isLoading = true;
    } else if (isApiCallInProgress) {
      buttonText = 'Starting...';
      isLoading = true;
    }

    return {
      buttonText,
      isLoading,
      isDisabled,
      isApiCallInProgress,
      isScraperWorking,
    };
  };

  return {
    // State
    runningScrapers,
    runAllInProgress,
    workingScrapers,

    // Mutations
    runScraperMutation,

    // Handlers
    handleRunScraper,
    handleRunAllScrapers,
    updateWorkingScrapers,
    getScraperButtonState,
  };
}
