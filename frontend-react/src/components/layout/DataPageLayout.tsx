import React from 'react';
import { PageLayout } from './PageLayout';
import { Button } from '@/components/ui'; // Updated import

interface DataPageLayoutProps<T> {
  title: string;
  subtitle?: string;
  data: T | T[] | null;
  loading: boolean;
  error?: Error | null; // Make error optional
  onRefresh?: () => void; // Made optional as it wasn't always used
  emptyMessage?: string;
  renderHeader?: () => React.ReactNode;
  children: React.ReactNode; // Added children prop
  renderChildrenOnEmpty?: boolean; // New prop
}

export function DataPageLayout<T>({
  title,
  subtitle,
  data,
  loading,
  error,
  onRefresh,
  emptyMessage = 'No data available',
  renderHeader,
  children,
  renderChildrenOnEmpty = false // Default to false
}: DataPageLayoutProps<T>) {
  // Loading state
  if (loading && (!data || (Array.isArray(data) && data.length === 0))) {
    return (
      <PageLayout title={title} subtitle={subtitle}>
        <div className="flex justify-center items-center h-[500px]">
          <div>Loading data...</div>
        </div>
      </PageLayout>
    );
  }

  // Error state
  if (error && (!data || (Array.isArray(data) && data.length === 0))) {
    return (
      <PageLayout title={title} subtitle={subtitle}>
        <div className="space-y-4 p-4 border border-red-500 bg-red-50 dark:bg-red-900/20 rounded-md my-4">
          <h3 className="text-red-700 dark:text-red-400 font-bold">Error loading data</h3>
          <p>{error.message}</p>
          {onRefresh && (
            <Button
              variant="outline"
              onClick={onRefresh}
              className="mt-4"
            >
              Retry
            </Button>
          )}
        </div>
      </PageLayout>
    );
  }

  // Empty state
  if (!renderChildrenOnEmpty && (!data || (Array.isArray(data) && data.length === 0))) {
    return (
      <PageLayout title={title} subtitle={subtitle}>
        <div className="p-4 border border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20 rounded-md my-4">
          <h3 className="font-bold text-yellow-700 dark:text-yellow-400 mb-2">No data available</h3>
          <p>{emptyMessage}</p>
          {onRefresh && (
            <Button
              variant="outline"
              onClick={onRefresh}
              className="mt-4"
            >
              Refresh
            </Button>
          )}
        </div>
      </PageLayout>
    );
  }

  // Main content
  return (
    <PageLayout title={title} subtitle={subtitle}>
      <div className="space-y-4">
        {renderHeader && (
          <div className="flex justify-between items-center">
            {renderHeader()}
          </div>
        )}
        {children}
      </div>
    </PageLayout>
  );
}
