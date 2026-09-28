import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatDate } from '@/utils/dateUtils';
import { get } from '@/utils/apiUtils';
import { LoadingButton } from '@/components/ui/LoadingButton';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { CenteredSpinner } from '@/components/ui/LoadingSpinner';
import { useToast } from '@/contexts/ToastContext';
import { useConfirmationDialog } from '@/components/ui/ConfirmationDialog';
import { ErrorSeverity, ErrorCategory } from '@/types/errors';

interface DatabaseStatus {
  prospect_count: number;
  prospects_with_source: number;
  prospects_without_source: number;
  ai_enriched_count: number;
  original_count: number;
  data_source_count: number;
  status_record_count: number;
  database_size_bytes: number | null;
  timestamp: string;
}

interface AIPreservationConfig {
  preserve_ai_data_on_refresh: boolean;
  enable_smart_duplicate_matching: boolean;
  description: string;
}

export function DatabaseManagement() {
  const queryClient = useQueryClient();
  const { showSuccessToast, showErrorToast } = useToast();
  const { confirm, ConfirmationDialog } = useConfirmationDialog();

  // Fetch database status
  const { data: statusData, isLoading, error, refetch } = useQuery<{ status: string; data: DatabaseStatus }>({
    queryKey: ['databaseStatus'],
    queryFn: () => get<{ status: string; data: DatabaseStatus }>('/api/database/status'),
  });

  // Fetch AI preservation config
  const { data: aiConfigData, isLoading: isLoadingConfig } = useQuery<{ status: string; data: AIPreservationConfig }>({
    queryKey: ['aiPreservationConfig'],
    queryFn: () => get<{ status: string; data: AIPreservationConfig }>('/api/config/ai-preservation'),
  });

  // Mutation for clearing all database
  const clearDatabaseMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch('/api/database/clear', {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to clear database');
      }
      return response.json();
    },
    onMutate: () => {
      // Loading state handled by mutation.isPending(true);
    },
    onSuccess: (data) => {
      showSuccessToast('Database Cleared', data.message || 'Database cleared successfully!');
      // Refetch all relevant data
      queryClient.invalidateQueries({ queryKey: ['databaseStatus'] });
      queryClient.invalidateQueries({ queryKey: ['dataSources'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
    },
    onError: (error: Error) => {
      showErrorToast({
        code: 'CLEAR_DATABASE_ERROR',
        message: error.message,
        severity: ErrorSeverity.ERROR,
        category: ErrorCategory.SYSTEM,
        timestamp: new Date(),
        userMessage: `Failed to clear database: ${error.message}`,
      });
    },
    onSettled: () => {
      // Loading state handled by mutation.isPending(false);
    },
  });

  // Mutation for clearing AI entries
  const clearAIMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch('/api/database/clear/ai', {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to clear AI entries');
      }
      return response.json();
    },
    onMutate: () => {
      // Loading state handled by mutation.isPending(true);
    },
    onSuccess: (data) => {
      showSuccessToast('AI Entries Cleared', data.message || 'AI entries cleared successfully!');
      // Refetch all relevant data
      queryClient.invalidateQueries({ queryKey: ['databaseStatus'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
      queryClient.invalidateQueries({ queryKey: ['ai-enrichment-status'] });
    },
    onError: (error: Error) => {
      showErrorToast({
        code: 'CLEAR_AI_ERROR',
        message: error.message,
        severity: ErrorSeverity.ERROR,
        category: ErrorCategory.SYSTEM,
        timestamp: new Date(),
        userMessage: `Failed to clear AI entries: ${error.message}`,
      });
    },
    onSettled: () => {
      // Loading state handled by mutation.isPending(false);
    },
  });

  // Mutation for clearing original entries
  const clearOriginalMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch('/api/database/clear/original', {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to clear original entries');
      }
      return response.json();
    },
    onMutate: () => {
      // Loading state handled by mutation.isPending(true);
    },
    onSuccess: (data) => {
      showSuccessToast('Original Entries Cleared', data.message || 'Original entries cleared successfully!');
      // Refetch all relevant data
      queryClient.invalidateQueries({ queryKey: ['databaseStatus'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
      queryClient.invalidateQueries({ queryKey: ['prospects'] });
    },
    onError: (error: Error) => {
      showErrorToast({
        code: 'CLEAR_ORIGINAL_ERROR',
        message: error.message,
        severity: ErrorSeverity.ERROR,
        category: ErrorCategory.SYSTEM,
        timestamp: new Date(),
        userMessage: `Failed to clear original entries: ${error.message}`,
      });
    },
    onSettled: () => {
      // Loading state handled by mutation.isPending(false);
    },
  });

  // Mutation for updating AI preservation config
  const updateAIConfigMutation = useMutation({
    mutationFn: async (updates: Partial<AIPreservationConfig>) => {
      const response = await fetch('/api/config/ai-preservation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });
      if (!response.ok) {
        throw new Error('Failed to update AI preservation config');
      }
      return response.json();
    },
    onSuccess: (data) => {
      showSuccessToast('Configuration Updated', data.data.message || 'Configuration updated successfully!');
      queryClient.invalidateQueries({ queryKey: ['aiPreservationConfig'] });
    },
    onError: (error: Error) => {
      showErrorToast({
        code: 'UPDATE_CONFIG_ERROR',
        message: error.message,
        severity: ErrorSeverity.ERROR,
        category: ErrorCategory.SYSTEM,
        timestamp: new Date(),
        userMessage: `Failed to update configuration: ${error.message}`,
      });
    },
  });

  const formatFileSize = (bytes: number | null) => {
    if (!bytes) return 'Unknown';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }

    return `${size.toFixed(1)} ${units[unitIndex]}`;
  };



  if (isLoading) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Database Management</CardTitle>
          </CardHeader>
          <CardContent>
            <CenteredSpinner text="Loading database status..." />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Database Management</CardTitle>
          </CardHeader>
          <CardContent>
            <ErrorDisplay error={error as Error} title="Failed to load database status">
              <Button onClick={() => refetch()} className="mt-4">
                Retry
              </Button>
            </ErrorDisplay>
          </CardContent>
        </Card>
      </div>
    );
  }

  const status = statusData?.data;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Database Status</CardTitle>
        </CardHeader>
        <CardContent>
          {status && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h4 className="font-medium text-gray-900">Total Prospects</h4>
                <p className="text-2xl font-bold text-blue-600">{status.prospect_count.toLocaleString()}</p>
                <p className="text-xs text-gray-500">
                  {status.prospects_with_source.toLocaleString()} with source, {status.prospects_without_source.toLocaleString()} orphaned
                </p>
              </div>
              <div>
                <h4 className="font-medium text-gray-900">Prospect Types</h4>
                <div className="space-y-1">
                  <p className="text-sm">
                    <span className="font-semibold text-green-600">{status.original_count.toLocaleString()}</span>
                    <span className="text-gray-600"> original</span>
                  </p>
                  <p className="text-sm">
                    <span className="font-semibold text-purple-600">{status.ai_enriched_count.toLocaleString()}</span>
                    <span className="text-gray-600"> AI enriched</span>
                  </p>
                </div>
              </div>
              <div>
                <h4 className="font-medium text-gray-900">Data Sources</h4>
                <p className="text-2xl font-bold text-green-600">{status.data_source_count}</p>
              </div>
              <div>
                <h4 className="font-medium text-gray-900">Status Records</h4>
                <p className="text-2xl font-bold text-purple-600">{status.status_record_count.toLocaleString()}</p>
              </div>
              <div>
                <h4 className="font-medium text-gray-900">Database Size</h4>
                <p className="text-2xl font-bold text-orange-600">{formatFileSize(status.database_size_bytes)}</p>
              </div>
              <div>
                <h4 className="font-medium text-gray-900">Last Updated</h4>
                <p className="text-sm text-gray-600">{formatDate(status.timestamp)}</p>
              </div>
            </div>
          )}
          <div className="mt-4">
            <Button onClick={() => refetch()} variant="outline">
              Refresh Status
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Database Operations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {/* Clear AI Entries */}
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Clear AI Entries Only</h4>
              <p className="text-sm text-gray-600 mb-3">
                Remove all AI-enriched prospects, enrichment logs, and LLM outputs. Original scraped data will remain.
              </p>
              <LoadingButton
                variant="primary"
                className="bg-purple-600 hover:bg-purple-700"
                isLoading={clearAIMutation.isPending}
                loadingText="Clearing AI Entries..."
                onClick={async () => {
                  const confirmed = await confirm({
                    title: 'Clear AI Entries',
                    description: 'Are you sure you want to clear all AI entries? This action cannot be undone.',
                    details: [
                      `${status?.ai_enriched_count.toLocaleString()} AI-enriched prospects`,
                      'All AI enrichment logs',
                      'All LLM outputs'
                    ],
                    confirmLabel: 'Clear AI Entries',
                    variant: 'destructive'
                  });

                  if (confirmed) {
                    clearAIMutation.mutate();
                  }
                }}
              >
                Clear AI Entries
              </LoadingButton>
            </div>

            {/* Clear Original Entries */}
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Clear Original Entries Only</h4>
              <p className="text-sm text-gray-600 mb-3">
                Remove all non-AI-enriched (original scraped) prospects. AI-enriched data will remain.
              </p>
              <LoadingButton
                variant="primary"
                className="bg-orange-600 hover:bg-orange-700"
                isLoading={clearOriginalMutation.isPending}
                loadingText="Clearing Original Entries..."
                onClick={async () => {
                  const confirmed = await confirm({
                    title: 'Clear Original Entries',
                    description: 'Are you sure you want to clear all original entries? This action cannot be undone.',
                    details: [
                      `${status?.original_count.toLocaleString()} original prospects`
                    ],
                    confirmLabel: 'Clear Original Entries',
                    variant: 'destructive'
                  });

                  if (confirmed) {
                    clearOriginalMutation.mutate();
                  }
                }}
              >
                Clear Original Entries
              </LoadingButton>
            </div>

            {/* Clear All */}
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Clear All Database</h4>
              <p className="text-sm text-gray-600 mb-3">
                This will permanently delete ALL prospects and scraper status records from the database.
                Data sources will remain but their last_scraped timestamps will be reset.
              </p>
              <LoadingButton
                variant="danger"
                isLoading={clearDatabaseMutation.isPending}
                loadingText="Clearing All..."
                onClick={async () => {
                  const confirmed = await confirm({
                    title: 'Clear Entire Database',
                    description: 'Are you sure you want to clear the ENTIRE database? This action cannot be undone.',
                    details: [
                      `${status?.prospect_count.toLocaleString()} total prospects`,
                      `${status?.status_record_count.toLocaleString()} scraper status records`,
                      'All last_scraped timestamps'
                    ],
                    confirmLabel: 'Clear All Database',
                    variant: 'destructive'
                  });

                  if (confirmed) {
                    clearDatabaseMutation.mutate();
                  }
                }}
              >
                Clear All Database
              </LoadingButton>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>AI Data Preservation & Duplicate Prevention</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoadingConfig ? (
            <CenteredSpinner text="Loading configuration..." height="h-16" />
          ) : (
            <div className="space-y-6">
              {/* AI Preservation Section */}
              <div>
                <h4 className="font-medium text-gray-900 mb-2">Preserve AI-Enhanced Data During Refreshes</h4>
                <p className="text-sm text-gray-600 mb-4">
                  {aiConfigData?.data?.description || 'Controls whether AI-enhanced fields are preserved when data sources are refreshed.'}
                </p>
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium">
                      Current Setting:
                      <span className={`ml-2 px-2 py-1 rounded-full text-xs font-semibold ${
                        aiConfigData?.data?.preserve_ai_data_on_refresh
                          ? 'bg-green-100 text-green-800'
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {aiConfigData?.data?.preserve_ai_data_on_refresh ? 'ENABLED' : 'DISABLED'}
                      </span>
                    </span>
                  </div>
                </div>
                <div className="flex space-x-2 mt-4">
                  <button
                    className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 bg-green-600 text-white shadow-xs hover:bg-green-700 h-9 px-4 py-2"
                    disabled={updateAIConfigMutation.isPending || aiConfigData?.data?.preserve_ai_data_on_refresh}
                    onClick={() => updateAIConfigMutation.mutate({ preserve_ai_data_on_refresh: true })}
                  >
                    {updateAIConfigMutation.isPending ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white mr-2"></div>
                    ) : null}
                    Enable Protection
                  </button>
                  <button
                    className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 bg-orange-600 text-white shadow-xs hover:bg-orange-700 h-9 px-4 py-2"
                    disabled={updateAIConfigMutation.isPending || !aiConfigData?.data?.preserve_ai_data_on_refresh}
                    onClick={async () => {
                      const confirmed = await confirm({
                        title: 'Disable AI Data Preservation',
                        description: 'Are you sure you want to disable AI data preservation?',
                        details: [
                          'This will allow data source refreshes to overwrite AI-enhanced fields like:',
                          '• NAICS codes and descriptions',
                          '• Parsed contact information',
                          '• LLM-enhanced values',
                          '',
                          'Consider this carefully as it may undo AI processing work.'
                        ],
                        confirmLabel: 'Disable Protection',
                        variant: 'destructive'
                      });

                      if (confirmed) {
                        updateAIConfigMutation.mutate({ preserve_ai_data_on_refresh: false });
                      }
                    }}
                  >
                    {updateAIConfigMutation.isPending ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white mr-2"></div>
                    ) : null}
                    Disable Protection
                  </button>
                </div>
              </div>

              {/* Smart Duplicate Matching Section */}
              <div className="border-t pt-6">
                <h4 className="font-medium text-gray-900 mb-2">Smart Duplicate Prevention</h4>
                <p className="text-sm text-gray-600 mb-4">
                  Advanced matching prevents duplicates when titles or descriptions change by using fuzzy matching on multiple fields (native_id, NAICS, location, content similarity).
                </p>
                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium">
                      Current Setting:
                      <span className={`ml-2 px-2 py-1 rounded-full text-xs font-semibold ${
                        aiConfigData?.data?.enable_smart_duplicate_matching
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {aiConfigData?.data?.enable_smart_duplicate_matching ? 'ENABLED' : 'DISABLED'}
                      </span>
                    </span>
                  </div>
                </div>
                <div className="flex space-x-2 mt-4">
                  <button
                    className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 bg-blue-600 text-white shadow-xs hover:bg-blue-700 h-9 px-4 py-2"
                    disabled={updateAIConfigMutation.isPending || aiConfigData?.data?.enable_smart_duplicate_matching}
                    onClick={() => updateAIConfigMutation.mutate({ enable_smart_duplicate_matching: true })}
                  >
                    {updateAIConfigMutation.isPending ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white mr-2"></div>
                    ) : null}
                    Enable Smart Matching
                  </button>
                  <button
                    className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 bg-gray-600 text-white shadow-xs hover:bg-gray-700 h-9 px-4 py-2"
                    disabled={updateAIConfigMutation.isPending || !aiConfigData?.data?.enable_smart_duplicate_matching}
                    onClick={async () => {
                      const confirmed = await confirm({
                        title: 'Disable Smart Duplicate Matching',
                        description: 'Are you sure you want to disable smart duplicate matching?',
                        details: [
                          'This will use only exact hash matching for duplicates.',
                          'Changes to titles or descriptions will create new records instead of updating existing ones.'
                        ],
                        confirmLabel: 'Disable Smart Matching',
                        variant: 'destructive'
                      });

                      if (confirmed) {
                        updateAIConfigMutation.mutate({ enable_smart_duplicate_matching: false });
                      }
                    }}
                  >
                    {updateAIConfigMutation.isPending ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white mr-2"></div>
                    ) : null}
                    Disable Smart Matching
                  </button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
      {ConfirmationDialog}
    </div>
  );
}
