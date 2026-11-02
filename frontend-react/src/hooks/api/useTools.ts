import { useQuery, useMutation } from '@tanstack/react-query';
import { get, post } from '@/utils/apiUtils';
import type { Script, ExecuteScriptParams, ExecutionResult } from '@/types/tools';
import type { ApiResponse } from '@/types/api';

// Fetch available scripts
export function useTools() {
  const query = useQuery({
    queryKey: ['tools', 'scripts'],
    queryFn: async () => {
      const response = await get<ApiResponse<{ scripts: Record<string, Script[]> }>>('/api/tools/scripts');
      return response.data.scripts;
    }
  });

  return {
    scripts: query.data,
    isLoading: query.isLoading,
    error: query.error
  };
}

// Get script details
export function useScriptDetails(scriptId: string) {
  return useQuery({
    queryKey: ['tools', 'script', scriptId],
    queryFn: async () => {
      const response = await get<ApiResponse<Script>>(`/api/tools/scripts/${scriptId}`);
      return response.data;
    },
    enabled: !!scriptId
  });
}

// Execute script
export function useExecuteScript() {
  return useMutation({
    mutationFn: async ({ scriptId, parameters }: ExecuteScriptParams) => {
      const response = await post<ApiResponse<{ execution_id: string; message: string }>>(
        `/api/tools/execute/${scriptId}`,
        { parameters }
      );
      return response;
    }
  });
}

// Get executions list
export function useExecutions() {
  return useQuery({
    queryKey: ['tools', 'executions'],
    queryFn: async () => {
      const response = await get<ApiResponse<{ executions: ExecutionResult[] }>>('/api/tools/executions');
      return response.data.executions;
    },
    refetchInterval: 5000 // Refresh every 5 seconds
  });
}

// Get execution details
export function useExecutionDetails(executionId: string) {
  return useQuery({
    queryKey: ['tools', 'execution', executionId],
    queryFn: async () => {
      const response = await get<ApiResponse<ExecutionResult>>(`/api/tools/executions/${executionId}`);
      return response.data;
    },
    enabled: !!executionId,
    refetchInterval: (query) => {
      // Stop refetching once execution is complete
      if (query.state.data?.status && ['completed', 'failed', 'error'].includes(query.state.data.status)) {
        return false;
      }
      return 1000; // Refresh every second while running
    }
  });
}
