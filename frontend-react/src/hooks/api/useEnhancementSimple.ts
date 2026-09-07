import { useState, useEffect, useCallback, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { post, get, ApiError } from '@/utils/apiUtils';

// Simple enhancement state for a prospect
interface EnhancementState {
  status: 'idle' | 'queued' | 'processing' | 'completed' | 'failed';
  queuePosition?: number;
  queueSize?: number;
  currentStep?: string;
  completedSteps?: string[];
  enhancementTypes?: string[];
  error?: string;
  queueItemId?: string;
  plannedSteps?: Record<string, { will_process: boolean; reason?: string | null }>;
}

interface EnhancementRequest {
  prospect_id: string;
  force_redo?: boolean;
  user_id?: number;
  enhancement_types?: string[];
}

interface QueueResponse {
  queue_item_id: string;
  position?: number;
  queue_position?: number;
  queue_size?: number;
  was_existing?: boolean;
  worker_running?: boolean;
  message?: string;
  planned_steps?: Record<string, { will_process: boolean; reason?: string | null }>;
}

/**
 * Simplified enhancement hook using polling
 */
export function useEnhancementSimple() {
  const [enhancementStates, setEnhancementStates] = useState<Record<string, EnhancementState>>({});
  const pollingIntervalsRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const enhancementStatesRef = useRef<Record<string, EnhancementState>>({});
  const pollingRetryCountRef = useRef<Map<string, number>>(new Map());
  const queryClient = useQueryClient();

  // Keep ref in sync with state
  useEffect(() => {
    enhancementStatesRef.current = enhancementStates;
  }, [enhancementStates]);

  // Clean up polling intervals on unmount
  useEffect(() => {
    return () => {
      pollingIntervalsRef.current.forEach(interval => clearInterval(interval));
      pollingIntervalsRef.current.clear();
    };
  }, []);

  // Poll for enhancement status
  const pollEnhancementStatus = useCallback(async (prospectId: string, queueItemId: string) => {
    try {
      console.log(`[Enhancement] Polling status for ${prospectId} with queue item ${queueItemId}`);

      // Use the queue item status endpoint
      const response = await get<any>(`/api/llm/queue/item/${queueItemId}`);

      console.log(`[Enhancement] Poll response for ${prospectId}:`, response);

      // Get previous state from ref to preserve queue position
      const prevState = enhancementStatesRef.current[prospectId];

      // Map the response to our simple state
      const status: EnhancementState = {
        status: response.status || 'processing',
        // Preserve the initial queue position throughout processing
        queuePosition: response.position || prevState?.queuePosition || 1,
        queueSize: prevState?.queueSize, // Preserve queue size from initial response
        currentStep: response.current_step,
        completedSteps: response.completed_steps || [],
        enhancementTypes: prevState?.enhancementTypes, // Preserve enhancement types
        error: response.error,
        queueItemId: prevState?.queueItemId, // Preserve queue item ID
        plannedSteps: prevState?.plannedSteps // Preserve planned steps from initial response
      };

      // Update state
      setEnhancementStates(prev => ({
        ...prev,
        [prospectId]: status
      }));

      // Reset retry count on successful poll
      pollingRetryCountRef.current.delete(prospectId);

      // If completed or failed, stop polling
      if (status.status === 'completed' || status.status === 'failed') {
        const interval = pollingIntervalsRef.current.get(prospectId);
        if (interval) {
          clearInterval(interval);
          pollingIntervalsRef.current.delete(prospectId);
        }

        // Clean up state and invalidate queries together after a delay
        setTimeout(() => {
          setEnhancementStates(prev => {
            const updated = { ...prev };
            delete updated[prospectId];
            return updated;
          });

          // Invalidate queries to refresh data
          queryClient.invalidateQueries({ queryKey: ['prospects'] });
          queryClient.invalidateQueries({ queryKey: ['prospect', prospectId] }); // Also invalidate individual prospect
          queryClient.invalidateQueries({ queryKey: ['ai-enrichment-status'] });
        }, 5000);
      }
    } catch (error) {
      console.error(`Failed to poll status for ${prospectId}:`, error);

      // Track retry count
      const currentRetries = pollingRetryCountRef.current.get(prospectId) || 0;
      pollingRetryCountRef.current.set(prospectId, currentRetries + 1);

      // If too many retries, mark as failed
      if (currentRetries >= 5) {
        const interval = pollingIntervalsRef.current.get(prospectId);
        if (interval) {
          clearInterval(interval);
          pollingIntervalsRef.current.delete(prospectId);
        }
        pollingRetryCountRef.current.delete(prospectId);

        // Update state to show error
        setEnhancementStates(prev => ({
          ...prev,
          [prospectId]: {
            status: 'failed',
            error: 'Failed to get enhancement status after multiple retries',
            queuePosition: prev[prospectId]?.queuePosition,
            currentStep: prev[prospectId]?.currentStep,
            completedSteps: prev[prospectId]?.completedSteps || []
          }
        }));

        // Clean up after delay
        setTimeout(() => {
          setEnhancementStates(prev => {
            const updated = { ...prev };
            delete updated[prospectId];
            return updated;
          });
        }, 5000);
      }
      // Otherwise continue polling
    }
  }, [queryClient]);

  // Queue enhancement
  const queueEnhancement = useCallback(async (request: EnhancementRequest): Promise<string> => {
    const { prospect_id } = request;

    try {
      const enhancementType = request.enhancement_types?.length
        ? request.enhancement_types.join(',')
        : 'all';

      console.log(`[Enhancement] Queueing enhancement for ${prospect_id}`, { enhancementType, force_redo: request.force_redo });

      // Set initial state immediately before making the request
      setEnhancementStates(prev => ({
        ...prev,
        [prospect_id]: {
          status: 'queued',
          queuePosition: undefined, // Will be updated when response comes back
          currentStep: 'Initializing...',
          enhancementTypes: request.enhancement_types || ['values', 'titles', 'naics', 'set_asides']
        }
      }));

      const response = await post<QueueResponse>('/api/llm/enhance-single', {
        prospect_id: request.prospect_id,
        enhancement_type: enhancementType,
        force_redo: request.force_redo,
        user_id: request.user_id
      });

      const queueItemId = response.queue_item_id;
      console.log(`[Enhancement] Received queue item ID: ${queueItemId}`, response);

      // Update state with actual queue position, size, queue item ID, and planned steps
      setEnhancementStates(prev => ({
        ...prev,
        [prospect_id]: {
          ...prev[prospect_id], // Preserve existing state like enhancementTypes
          status: 'queued',
          queuePosition: response.queue_position || response.position || 1,
          queueSize: response.queue_size,
          currentStep: undefined,
          queueItemId: queueItemId,
          plannedSteps: response.planned_steps // Store planned steps from API
        }
      }));

      // Start polling
      const interval = setInterval(() => {
        pollEnhancementStatus(prospect_id, queueItemId);
      }, 2500); // Poll every 2.5 seconds

      pollingIntervalsRef.current.set(prospect_id, interval);
      pollingRetryCountRef.current.delete(prospect_id); // Reset retry count

      // Do initial poll immediately
      pollEnhancementStatus(prospect_id, queueItemId);

      // Show toast only if this is a new queue item (not already existing)
      if (window.showToast && !response.was_existing) {
        window.showToast({
          title: 'Enhancement Queued',
          message: `Enhancement queued${response.queue_position ? ` at position ${response.queue_position}` : ''}`,
          type: 'success',
          duration: 2000
        });
      }

      return queueItemId;
    } catch (error: unknown) {
      const apiError = error as ApiError;

      // Update state to show error
      setEnhancementStates(prev => ({
        ...prev,
        [prospect_id]: {
          status: 'failed',
          error: apiError.message || 'Failed to queue enhancement'
        }
      }));

      if (window.showToast) {
        window.showToast({
          title: 'Enhancement Failed',
          message: apiError.message || 'Failed to queue enhancement',
          type: 'error',
          duration: 5000
        });
      }

      throw error;
    }
  }, [pollEnhancementStatus]);

  // Get enhancement state for a specific prospect
  const getEnhancementState = useCallback((prospectId: string): EnhancementState | null => {
    return enhancementStates[prospectId] || null;
  }, [enhancementStates]);

  // Cancel enhancement - stops polling and cancels backend processing
  const cancelEnhancement = useCallback(async (prospectId: string): Promise<boolean> => {
    try {
      // Get the queue item ID from state
      const state = enhancementStatesRef.current[prospectId];

      if (state?.queueItemId) {
        // Call backend cancel API
        console.log(`[Enhancement] Cancelling enhancement for ${prospectId} with queue item ${state.queueItemId}`);

        // Try the cancel endpoint
        await post(`/api/llm/queue/item/${state.queueItemId}/cancel`, {});

        console.log(`[Enhancement] Successfully cancelled enhancement for ${prospectId}`);
      }

      // Stop polling
      const interval = pollingIntervalsRef.current.get(prospectId);
      if (interval) {
        clearInterval(interval);
        pollingIntervalsRef.current.delete(prospectId);
      }

      // Clear retry count
      pollingRetryCountRef.current.delete(prospectId);

      // Clear state
      setEnhancementStates(prev => {
        const updated = { ...prev };
        delete updated[prospectId];
        return updated;
      });

      // Show toast
      if (window.showToast) {
        window.showToast({
          title: 'Enhancement Cancelled',
          message: 'The enhancement process has been cancelled',
          type: 'info',
          duration: 2000
        });
      }

      return true;
    } catch (error) {
      console.error(`Failed to cancel enhancement for ${prospectId}:`, error);

      // Still clean up local state even if backend cancel fails
      const interval = pollingIntervalsRef.current.get(prospectId);
      if (interval) {
        clearInterval(interval);
        pollingIntervalsRef.current.delete(prospectId);
      }

      pollingRetryCountRef.current.delete(prospectId);

      setEnhancementStates(prev => {
        const updated = { ...prev };
        delete updated[prospectId];
        return updated;
      });

      if (window.showToast) {
        window.showToast({
          title: 'Cancel Warning',
          message: 'Enhancement cleared locally, but backend process may continue',
          type: 'warning',
          duration: 3000
        });
      }

      return false;
    }
  }, []);

  return {
    queueEnhancement,
    getEnhancementState,
    cancelEnhancement,
    enhancementStates
  };
}
