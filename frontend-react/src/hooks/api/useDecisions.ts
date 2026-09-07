import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { get, post, del, buildQueryString } from '@/utils/apiUtils';
import {
  ApiResponse,
  GoNoGoDecision,
  DecisionStats,
  CreateDecisionRequest,
  PaginationMeta
} from '../../types/api';

const API_BASE = '/api/decisions';

// Decision API functions
const decisionsApi = {
  createDecision: async (data: CreateDecisionRequest): Promise<ApiResponse<{ decision: GoNoGoDecision; message: string }>> => {
    return await post<ApiResponse<{ decision: GoNoGoDecision; message: string }>>(
      `${API_BASE}/`,
      data,
      { credentials: 'include' }
    );
  },

  getProspectDecisions: async (prospectId: string): Promise<ApiResponse<{ prospect_id: string; decisions: GoNoGoDecision[]; total_decisions: number }>> => {
    return await get<ApiResponse<{ prospect_id: string; decisions: GoNoGoDecision[]; total_decisions: number }>>(
      `${API_BASE}/${prospectId}`,
      { credentials: 'include' }
    );
  },

  getMyDecisions: async (page = 1, perPage = 50): Promise<ApiResponse<{ decisions: GoNoGoDecision[]; pagination: PaginationMeta }>> => {
    const queryParams = buildQueryString({ page, per_page: perPage });
    return await get<ApiResponse<{ decisions: GoNoGoDecision[]; pagination: PaginationMeta }>>(
      `${API_BASE}/my${queryParams}`,
      { credentials: 'include' }
    );
  },

  getDecisionStats: async (): Promise<ApiResponse<DecisionStats>> => {
    return await get<ApiResponse<DecisionStats>>(
      `${API_BASE}/stats`,
      { credentials: 'include' }
    );
  },

  deleteDecision: async (decisionId: number): Promise<ApiResponse<{ message: string }>> => {
    return await del<ApiResponse<{ message: string }>>(
      `${API_BASE}/${decisionId}`,
      { credentials: 'include' }
    );
  },
};

// Hook to get decisions for a specific prospect
export const useProspectDecisions = (prospectId: string | null) => {
  return useQuery({
    queryKey: ['decisions', 'prospect', prospectId],
    queryFn: () => decisionsApi.getProspectDecisions(prospectId!),
    enabled: !!prospectId,
    staleTime: 1 * 60 * 1000, // 1 minute
    retry: 1, // Only retry once
    retryDelay: 1000, // Wait 1 second before retry
  });
};

// Hook to get current user's decisions
export const useMyDecisions = (page = 1, perPage = 50) => {
  return useQuery({
    queryKey: ['decisions', 'my', page, perPage],
    queryFn: () => decisionsApi.getMyDecisions(page, perPage),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};

// Hook to get decision statistics
export const useDecisionStats = () => {
  return useQuery({
    queryKey: ['decisions', 'stats'],
    queryFn: decisionsApi.getDecisionStats,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

// Hook to create or update a decision
export const useCreateDecision = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: decisionsApi.createDecision,
    onSuccess: (_, variables) => {
      // Invalidate queries related to this prospect
      queryClient.invalidateQueries({
        queryKey: ['decisions', 'prospect', variables.prospect_id]
      });
      // Invalidate user's decisions and stats
      queryClient.invalidateQueries({
        queryKey: ['decisions', 'my']
      });
      queryClient.invalidateQueries({
        queryKey: ['decisions', 'stats']
      });
      // Invalidate admin queries to refresh admin dashboard
      queryClient.invalidateQueries({
        queryKey: ['admin']
      });
    },
  });
};

// Hook to delete a decision
export const useDeleteDecision = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: decisionsApi.deleteDecision,
    onSuccess: () => {
      // Invalidate all decision queries
      queryClient.invalidateQueries({
        queryKey: ['decisions']
      });
      // Invalidate admin queries to refresh admin dashboard
      queryClient.invalidateQueries({
        queryKey: ['admin']
      });
    },
  });
};
