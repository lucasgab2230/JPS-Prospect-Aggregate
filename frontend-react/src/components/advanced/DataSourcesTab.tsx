import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { LoadingButton } from '@/components/ui/LoadingButton';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { CenteredSpinner } from '@/components/ui/LoadingSpinner';
import { DataSource } from '@/types';
import { DataSourceTable } from './DataSourceTable';

interface DataSourcesTabProps {
  sources: { status: string; data: DataSource[] } | undefined;
  isLoading: boolean;
  error: unknown;
  runAllInProgress: boolean;
  onRunAllScrapers: () => void;
  onRunScraper: (sourceId: number) => void;
  onClearData: (id: number, sourceName: string) => void;
  getScraperButtonState: (source: DataSource) => {
    buttonText: string;
    isLoading: boolean;
    isDisabled: boolean;
    isApiCallInProgress: boolean;
    isScraperWorking: boolean;
  };
  clearDataMutation: {
    isPending: boolean;
    variables: unknown;
  };
}

export function DataSourcesTab({
  sources,
  isLoading,
  error,
  runAllInProgress,
  onRunAllScrapers,
  onRunScraper,
  onClearData,
  getScraperButtonState,
  clearDataMutation,
}: DataSourcesTabProps) {
  if (isLoading) {
    return <CenteredSpinner text="Loading data sources..." height="h-64" />;
  }

  if (error) {
    return <ErrorDisplay error={error as Error} title="Failed to load data sources" />;
  }

  const dataSources = sources?.data || [];
  const activeScrapers = dataSources.filter((source: DataSource) => source.status === 'working');
  const hasActiveScrapers = activeScrapers.length > 0;

  return (
    <div className="space-y-6">
      {/* Active Scrapers Status */}
      {hasActiveScrapers && (
        <div className="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-md">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="h-3 w-3 rounded-full bg-blue-400 animate-pulse"></div>
            </div>
            <div className="ml-3">
              <p className="text-sm text-blue-700">
                <strong>{activeScrapers.length}</strong> scraper{activeScrapers.length !== 1 ? 's' : ''} currently running: {' '}
                {activeScrapers.map((s: DataSource) => s.name).join(', ')}
              </p>
            </div>
          </div>
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Data Sources</CardTitle>
          <LoadingButton
            onClick={onRunAllScrapers}
            isLoading={runAllInProgress}
            loadingText="Running All Scrapers..."
            disabled={dataSources.length === 0 || hasActiveScrapers}
            className="bg-blue-600 hover:bg-blue-700"
          >
            Pull All Sources
          </LoadingButton>
        </CardHeader>
        <CardContent>
          <DataSourceTable
            dataSources={dataSources}
            onRunScraper={onRunScraper}
            onClearData={onClearData}
            getScraperButtonState={getScraperButtonState}
            clearDataMutation={clearDataMutation}
          />
        </CardContent>
      </Card>
    </div>
  );
}
