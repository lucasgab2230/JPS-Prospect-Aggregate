import { useState, useRef, useEffect, useCallback } from 'react';
import { PageLayout } from '@/components/layout';
import { useInfiniteProspects, useProspectStatistics } from '@/hooks/api/useProspects';
import { ProspectFilters } from '@/types/prospects';
import { Button } from '@/components/ui';
import { useTimezoneDate } from '@/hooks/useTimezoneDate';
import { LoadingButton } from '@/components/ui/LoadingButton';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { CenteredSpinner } from '@/components/ui/LoadingSpinner';
import { useVirtualizer } from '@tanstack/react-virtual';
import { GoNoGoDecision } from '@/components/GoNoGoDecision';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useListDataSources } from '@/hooks/api/useDataSources';
import { DataSource } from '@/types';
import { useToast } from '@/contexts/ToastContext';

export default function Prospects() {
  const [filters, setFilters] = useState<ProspectFilters>({
    keywords: '',
    naics: '',
    agency: '',
    dataSourceIds: []
  });
  const parentRef = useRef<HTMLDivElement>(null);
  const { showInfoToast } = useToast();

  // Data sources hook
  const { data: dataSourcesData } = useListDataSources();
  const dataSources = dataSourcesData?.data || [];
  const { formatUserDate } = useTimezoneDate();

  const {
    data: prospects,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
    error
  } = useInfiniteProspects(filters);


  const { data: statisticsData, isLoading: isLoadingStats } = useProspectStatistics();

  // Filter handlers
  const handleFilterChange = useCallback((filterKey: keyof ProspectFilters, value: string) => {
    setFilters(prev => ({ ...prev, [filterKey]: value }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({ keywords: '', naics: '', agency: '', dataSourceIds: [] });
  }, []);

  const hasActiveFilters = Object.entries(filters).some(([key, value]) => {
    if (key === 'dataSourceIds') {
      return Array.isArray(value) && value.length > 0;
    }
    return value && value.trim() !== '';
  });

  const handleDataSourceToggle = useCallback((sourceId: number) => {
    setFilters(prev => {
      const currentIds = prev.dataSourceIds || [];
      const newIds = currentIds.includes(sourceId)
        ? currentIds.filter((id: number) => id !== sourceId)
        : [...currentIds, sourceId];
      return { ...prev, dataSourceIds: newIds };
    });
  }, []);

  // Set up virtualization
  const virtualizer = useVirtualizer({
    count: prospects?.length || 0,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 60, // Estimated row height in pixels
    overscan: 10, // Render 10 extra items above/below viewport for smooth scrolling
  });

  const handleLoadMore = () => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  };

  // Auto-load more data when scrolling near the end
  useEffect(() => {
    const [lastItem] = [...virtualizer.getVirtualItems()].reverse();

    if (!lastItem) return;

    if (
      prospects && lastItem.index >= prospects.length - 1 - 5 && // Load when 5 items from the end
      hasNextPage &&
      !isFetchingNextPage
    ) {
      fetchNextPage();
    }
  }, [hasNextPage, fetchNextPage, isFetchingNextPage, virtualizer.getVirtualItems(), prospects?.length]);


  const totalProspects = statisticsData?.data?.total ?? 0;

  return (
    <PageLayout
      title="Prospects"
      subtitle={`Total: ${totalProspects} prospects`}
    >
      {/* Main container with filters and content */}
      <div className="flex gap-6">
        {/* Filters Sidebar */}
        <div className="w-80 flex-shrink-0">
          <Card className="shadow-lg">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg font-semibold text-black">Filters</CardTitle>
                {hasActiveFilters && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={clearFilters}
                    className="text-xs px-2 py-1 h-7"
                  >
                    Clear All
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Keywords Filter */}
              <div className="space-y-2">
                <Label htmlFor="keywords" className="text-sm font-medium text-gray-700">
                  Keywords
                </Label>
                <Input
                  id="keywords"
                  placeholder="Search in title, description..."
                  value={filters.keywords || ''}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFilterChange('keywords', e.target.value)}
                  className="text-sm"
                />
              </div>

              {/* NAICS Code Filter */}
              <div className="space-y-2">
                <Label htmlFor="naics" className="text-sm font-medium text-gray-700">
                  NAICS Code
                </Label>
                <Input
                  id="naics"
                  placeholder="e.g., 541511, 334"
                  value={filters.naics || ''}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFilterChange('naics', e.target.value)}
                  className="text-sm"
                />
              </div>

              {/* Agency Filter */}
              <div className="space-y-2">
                <Label htmlFor="agency" className="text-sm font-medium text-gray-700">
                  Agency
                </Label>
                <Input
                  id="agency"
                  placeholder="e.g., DOD, HHS, DHS"
                  value={filters.agency || ''}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleFilterChange('agency', e.target.value)}
                  className="text-sm"
                />
              </div>

              {/* Data Source Filter */}
              <div className="space-y-2">
                <Label className="text-sm font-medium text-gray-700">
                  Data Source
                </Label>
                <div className="max-h-48 overflow-y-auto border rounded-md p-3 space-y-2">
                  {dataSources.map((source: DataSource) => (
                    <label
                      key={source.id}
                      className="flex items-center space-x-2 cursor-pointer hover:bg-gray-50 p-1 rounded"
                    >
                      <input
                        type="checkbox"
                        checked={filters.dataSourceIds?.includes(source.id) || false}
                        onChange={() => handleDataSourceToggle(source.id)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700">{source.name}</span>
                    </label>
                  ))}
                  {dataSources.length === 0 && (
                    <div className="text-sm text-gray-500 text-center py-2">
                      No data sources available
                    </div>
                  )}
                </div>
              </div>

              {/* Filter Summary */}
              {hasActiveFilters && (
                <div className="pt-2 border-t border-gray-200">
                  <p className="text-xs text-gray-600 mb-2">Active filters:</p>
                  <div className="space-y-1">
                    {filters.keywords && (
                      <div className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded flex justify-between items-center">
                        <span>Keywords: {filters.keywords}</span>
                        <button
                          onClick={() => handleFilterChange('keywords', '')}
                          className="ml-1 text-blue-500 hover:text-blue-700"
                        >
                          ×
                        </button>
                      </div>
                    )}
                    {filters.naics && (
                      <div className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded flex justify-between items-center">
                        <span>NAICS: {filters.naics}</span>
                        <button
                          onClick={() => handleFilterChange('naics', '')}
                          className="ml-1 text-green-500 hover:text-green-700"
                        >
                          ×
                        </button>
                      </div>
                    )}
                    {filters.agency && (
                      <div className="text-xs bg-purple-50 text-purple-700 px-2 py-1 rounded flex justify-between items-center">
                        <span>Agency: {filters.agency}</span>
                        <button
                          onClick={() => handleFilterChange('agency', '')}
                          className="ml-1 text-purple-500 hover:text-purple-700"
                        >
                          ×
                        </button>
                      </div>
                    )}
                    {filters.dataSourceIds && filters.dataSourceIds.length > 0 && (
                      filters.dataSourceIds.map((sourceId: number) => {
                        const source = dataSources.find((s: DataSource) => s.id === sourceId);
                        return (
                          <div key={sourceId} className="text-xs bg-orange-50 text-orange-700 px-2 py-1 rounded flex justify-between items-center">
                            <span>Source: {source ? source.name : sourceId}</span>
                            <button
                              onClick={() => handleDataSourceToggle(sourceId)}
                              className="ml-1 text-orange-500 hover:text-orange-700"
                            >
                              ×
                            </button>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Prospects List Card - Main content */}
        <div className="flex-grow">
          <Card className="shadow-lg">
            <CardHeader className="flex flex-row items-center justify-between py-5 px-6 border-b border-gray-200">
              <CardTitle className="text-2xl font-bold text-black">Prospects List</CardTitle>
            </CardHeader>
            <CardContent className="pt-6 px-6 pb-6">
              {isLoading || isLoadingStats ? (
                <div className="flex justify-center py-8">
                  <CenteredSpinner text="Loading prospects..." />
                </div>
              ) : isError ? (
                <ErrorDisplay error={error as Error} />
              ) : !prospects || prospects.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No prospects found.
                </div>
              ) : (
                <>
                  <div className="rounded-md border">
                    {/* Table Header */}
                    <div className="grid grid-cols-6 gap-4 p-4 bg-gray-50 border-b font-medium text-sm text-gray-700">
                      <div>Title</div>
                      <div>Status</div>
                      <div>Data Source</div>
                      <div>Created</div>
                      <div>Decision</div>
                      <div>Actions</div>
                    </div>

                    {/* Virtualized Table Body */}
                    <div
                      ref={parentRef}
                      className="h-[600px] overflow-auto"
                      style={{
                        contain: 'strict',
                      }}
                    >
                      <div
                        style={{
                          height: `${virtualizer.getTotalSize()}px`,
                          width: '100%',
                          position: 'relative',
                        }}
                      >
                        {virtualizer.getVirtualItems().map((virtualItem) => {
                          const prospect = prospects[virtualItem.index];
                          return (
                            <div
                              key={virtualItem.key}
                              style={{
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                width: '100%',
                                height: `${virtualItem.size}px`,
                                transform: `translateY(${virtualItem.start}px)`,
                              }}
                              className="grid grid-cols-6 gap-4 p-4 border-b hover:bg-gray-50 items-center"
                            >
                              <div className="font-medium truncate">
                                {prospect?.title || 'Untitled'}
                              </div>
                              <div className="truncate">
                                {prospect?.agency || 'N/A'}
                              </div>
                              <div className="truncate">
                                {prospect?.source_name || 'N/A'}
                              </div>
                              <div className="text-sm text-gray-600">
                                {formatUserDate(prospect?.loaded_at, 'date')}
                              </div>
                              <div>
                                <GoNoGoDecision
                                  prospectId={prospect?.id}
                                  prospectTitle={prospect?.title}
                                  compact={true}
                                />
                              </div>
                              <div>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => showInfoToast('Coming Soon', 'Prospect details view will be available in a future update.')}
                                >
                                  View
                                </Button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {hasNextPage && (
                    <div className="flex justify-center mt-6">
                      <LoadingButton
                        onClick={handleLoadMore}
                        isLoading={isFetchingNextPage}
                        loadingText="Loading..."
                      >
                        Load More
                      </LoadingButton>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </PageLayout>
  );
}
