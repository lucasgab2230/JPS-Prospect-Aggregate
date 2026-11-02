import { useEffect, useState, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useEnhancementSimple } from '@/hooks/api/useEnhancementSimple';
import { useEnhancementQueueService } from '@/hooks/api/useEnhancementQueueService';

interface ActivityState {
  hasActiveEnhancements: boolean;
  totalActiveCount: number;
  processingCount: number;
  queuedCount: number;
  workerActive: boolean;
  iterativeActive: boolean;
  lastActivityTime: Date | null;
}

/**
 * Unified activity monitoring hook that intelligently manages polling intervals
 * based on enhancement activity across the system
 */
export function useEnhancementActivityMonitor() {
  const queryClient = useQueryClient();
  const { enhancementStates } = useEnhancementSimple();
  const { isWorkerRunning, isIterativeProcessing } = useEnhancementQueueService();

  const [activityState, setActivityState] = useState<ActivityState>({
    hasActiveEnhancements: false,
    totalActiveCount: 0,
    processingCount: 0,
    queuedCount: 0,
    workerActive: false,
    iterativeActive: false,
    lastActivityTime: null
  });

  const [pollingInterval, setPollingInterval] = useState(5000); // Default 5 seconds
  const lastActivityRef = useRef<Date | null>(null);

  // Calculate activity state
  useEffect(() => {
    const processingCount = Object.values(enhancementStates).filter(
      state => state.status === 'processing'
    ).length;

    const queuedCount = Object.values(enhancementStates).filter(
      state => state.status === 'queued'
    ).length;

    const totalActiveCount = processingCount + queuedCount;
    const hasActive = totalActiveCount > 0 || isWorkerRunning || isIterativeProcessing;

    // Update activity timestamp if there's activity
    if (hasActive && !lastActivityRef.current) {
      lastActivityRef.current = new Date();
    } else if (!hasActive && lastActivityRef.current) {
      lastActivityRef.current = null;
    }

    setActivityState({
      hasActiveEnhancements: hasActive,
      totalActiveCount,
      processingCount,
      queuedCount,
      workerActive: isWorkerRunning,
      iterativeActive: isIterativeProcessing,
      lastActivityTime: lastActivityRef.current
    });
  }, [enhancementStates, isWorkerRunning, isIterativeProcessing]);

  // Intelligently adjust polling interval based on activity
  useEffect(() => {
    let interval: number;

    if (activityState.processingCount > 0) {
      // Very frequent polling when actively processing
      interval = 1000; // 1 second
    } else if (activityState.queuedCount > 0) {
      // Moderate polling when items are queued
      interval = 2000; // 2 seconds
    } else if (activityState.workerActive || activityState.iterativeActive) {
      // Less frequent when only background processing
      interval = 3000; // 3 seconds
    } else if (activityState.lastActivityTime) {
      // Gradual slowdown after activity stops
      const timeSinceActivity = Date.now() - activityState.lastActivityTime.getTime();
      if (timeSinceActivity < 10000) {
        interval = 5000; // 5 seconds for first 10 seconds
      } else if (timeSinceActivity < 30000) {
        interval = 10000; // 10 seconds for next 20 seconds
      } else {
        interval = 30000; // 30 seconds after that
      }
    } else {
      // Default slow polling when idle
      interval = 30000; // 30 seconds
    }

    setPollingInterval(interval);
  }, [activityState]);

  // Apply polling interval to queries
  useEffect(() => {
    // Update query defaults for enhancement-related queries
    queryClient.setQueryDefaults(['prospects'], {
      refetchInterval: activityState.hasActiveEnhancements ? pollingInterval : false
    });

    queryClient.setQueryDefaults(['enhancement-queue-status'], {
      refetchInterval: pollingInterval
    });

    queryClient.setQueryDefaults(['iterative-progress'], {
      refetchInterval: activityState.iterativeActive ? 1000 : pollingInterval
    });

    queryClient.setQueryDefaults(['ai-enrichment-status'], {
      refetchInterval: activityState.hasActiveEnhancements ? pollingInterval * 2 : 60000
    });
  }, [pollingInterval, activityState, queryClient]);

  // Force refresh all enhancement-related queries
  const refreshAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['prospects'] });
    queryClient.invalidateQueries({ queryKey: ['enhancement-queue-status'] });
    queryClient.invalidateQueries({ queryKey: ['iterative-progress'] });
    queryClient.invalidateQueries({ queryKey: ['ai-enrichment-status'] });
    queryClient.invalidateQueries({ queryKey: ['llm-outputs'] });
  }, [queryClient]);

  // Check if any enhancement activity is happening
  const hasAnyActivity = activityState.hasActiveEnhancements;

  // Get a summary message of current activity
  const getActivitySummary = useCallback(() => {
    const parts: string[] = [];

    if (activityState.processingCount > 0) {
      parts.push(`${activityState.processingCount} processing`);
    }

    if (activityState.queuedCount > 0) {
      parts.push(`${activityState.queuedCount} queued`);
    }

    if (activityState.iterativeActive) {
      parts.push('bulk enhancement running');
    }

    if (parts.length === 0 && activityState.workerActive) {
      parts.push('worker idle');
    }

    return parts.join(', ') || 'No activity';
  }, [activityState]);

  return {
    // Activity state
    ...activityState,
    hasAnyActivity,

    // Polling control
    currentPollingInterval: pollingInterval,

    // Actions
    refreshAll,

    // Helpers
    getActivitySummary,
  };
}
