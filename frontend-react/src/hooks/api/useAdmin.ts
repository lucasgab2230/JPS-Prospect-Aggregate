import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { get, put } from '@/utils/apiUtils';
import {
  ApiResponse,
  GoNoGoDecision,
  AdminDecisionStats,
  UserWithStats,
  UpdateUserRoleRequest,
  DecisionExport
} from '../../types/api';

const API_BASE = '/api/admin';

// Admin API functions
const adminApi = {
  // Decision management
  getAllDecisions: async (params?: {
    page?: number;
    per_page?: number;
    decision?: 'go' | 'no-go';
    user_id?: number;
  }): Promise<ApiResponse<{
    decisions: GoNoGoDecision[];
    pagination: {
      page: number;
      per_page: number;
      total: number;
      pages: number;
    };
    filters: {
      decision?: string;
      user_id?: number;
    };
  }>> => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.per_page) searchParams.set('per_page', params.per_page.toString());
    if (params?.decision) searchParams.set('decision', params.decision);
    if (params?.user_id) searchParams.set('user_id', params.user_id.toString());

    const url = `${API_BASE}/decisions/all${searchParams.toString() ? `?${searchParams}` : ''}`;
    return await get<ApiResponse<{
      decisions: GoNoGoDecision[];
      pagination: {
        page: number;
        per_page: number;
        total: number;
        pages: number;
      };
      filters: {
        decision?: string;
        user_id?: number;
      };
    }>>(url, { credentials: 'include' });
  },

  getDecisionStats: async (): Promise<ApiResponse<AdminDecisionStats>> => {
    return await get<ApiResponse<AdminDecisionStats>>(
      `${API_BASE}/decisions/stats`,
      { credentials: 'include' }
    );
  },

  exportDecisions: async (): Promise<ApiResponse<{
    decisions: DecisionExport[];
    total_count: number;
    export_timestamp: string;
  }>> => {
    return await get<ApiResponse<{
      decisions: DecisionExport[];
      total_count: number;
      export_timestamp: string;
    }>>(
      `${API_BASE}/decisions/export`,
      { credentials: 'include' }
    );
  },

  // User management
  getAllUsers: async (params?: {
    page?: number;
    per_page?: number;
  }): Promise<ApiResponse<{
    users: UserWithStats[];
    pagination: {
      page: number;
      per_page: number;
      total: number;
      pages: number;
    };
  }>> => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.per_page) searchParams.set('per_page', params.per_page.toString());

    const url = `${API_BASE}/users${searchParams.toString() ? `?${searchParams}` : ''}`;
    return await get<ApiResponse<{
      users: UserWithStats[];
      pagination: {
        page: number;
        per_page: number;
        total: number;
        pages: number;
      };
    }>>(url, { credentials: 'include' });
  },

  updateUserRole: async (userId: number, data: UpdateUserRoleRequest): Promise<ApiResponse<{ message: string }>> => {
    return await put<ApiResponse<{ message: string }>>(
      `${API_BASE}/users/${userId}/role`,
      data,
      { credentials: 'include' }
    );
  },
};

// Admin Hooks

// Hook to get all decisions (admin only)
export const useAdminDecisions = (params?: {
  page?: number;
  per_page?: number;
  decision?: 'go' | 'no-go';
  user_id?: number;
}) => {
  return useQuery({
    queryKey: ['admin', 'decisions', 'all', params],
    queryFn: () => adminApi.getAllDecisions(params),
    retry: false,
  });
};

// Hook to get admin decision statistics
export const useAdminDecisionStats = () => {
  return useQuery({
    queryKey: ['admin', 'decisions', 'stats'],
    queryFn: adminApi.getDecisionStats,
    retry: false,
  });
};

// Hook to export all decisions
export const useExportDecisions = () => {
  return useMutation({
    mutationFn: adminApi.exportDecisions,
  });
};

// Hook to get all users (admin only)
export const useAdminUsers = (params?: {
  page?: number;
  per_page?: number;
}) => {
  return useQuery({
    queryKey: ['admin', 'users', params],
    queryFn: () => adminApi.getAllUsers(params),
    retry: false,
  });
};

// Hook to update user role
export const useUpdateUserRole = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, data }: { userId: number; data: UpdateUserRoleRequest }) =>
      adminApi.updateUserRole(userId, data),
    onSuccess: () => {
      // Invalidate admin queries to refetch data
      queryClient.invalidateQueries({ queryKey: ['admin'] });
    },
  });
};
