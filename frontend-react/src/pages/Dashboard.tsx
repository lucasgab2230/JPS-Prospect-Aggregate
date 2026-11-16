import { PageLayout } from '@/components/layout';
import { getCoreRowModel, useReactTable } from '@tanstack/react-table';
import { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useProspectEnhancement } from '@/contexts/ProspectEnhancementContext';
import { useTimezoneDate } from '@/hooks/useTimezoneDate';
import { useListDataSources } from '@/hooks/api/useDataSources';
import { useProspectFilters, usePaginatedProspects, useProspectModal, useProspectColumns } from '@/hooks';
import type { ProspectFilters as ProspectFiltersType } from '@/hooks/useProspectFilters';
import type { Prospect } from '@/types/prospects';
import { ProspectFilters } from '@/components/prospect/ProspectFilters';
import { ProspectTablePagination } from '@/components/prospect/ProspectTablePagination';
import { ProspectTable } from '@/components/prospect/ProspectTable';
import { ProspectDetailsModal } from '@/components/prospect/ProspectDetailsModal';

export default function Dashboard() {
  const [showAIEnhanced, setShowAIEnhanced] = useState(true);

  // Use the new hooks
  const {
    filters,
    updateFilter,
    toggleDataSource,
    clearFilters,
    hasActiveFilters
  } = useProspectFilters();

  const {
    prospects,
    total,
    totalPages,
    currentPage,
    itemsPerPage,
    isLoading: isLoadingProspects,
    isFetching: isFetchingProspects,
    handlePageChange,
    handlePageSizeChange,
    resetPagination,
    refetch: _refetch
  } = usePaginatedProspects(filters);

  const {
    selectedProspect,
    isOpen: isDialogOpen,
    openModal,
    closeModal: _closeModal,
    handleOpenChange,
    setIsOpen: _setIsDialogOpen
  } = useProspectModal(prospects);

  const { columns } = useProspectColumns(showAIEnhanced);

  // Data sources hook
  const { data: dataSourcesData } = useListDataSources();
  const dataSources = dataSourcesData?.data || [];

  // Enhancement hook
  const { addToQueue, getProspectStatus } = useProspectEnhancement();


  // Timezone hook for date formatting
  const { formatUserDate } = useTimezoneDate();

  const table = useReactTable({
    data: prospects,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    rowCount: total,
  });

  const handlePreviousPage = useCallback(() => {
    handlePageChange(currentPage - 1);
  }, [currentPage, handlePageChange]);

  const handleNextPage = useCallback(() => {
    handlePageChange(currentPage + 1);
  }, [currentPage, handlePageChange]);

  const handleFilterChange = useCallback((filterKey: keyof ProspectFiltersType, value: string) => {
    updateFilter(filterKey, value);
    resetPagination();
  }, [updateFilter, resetPagination]);

  const handleDataSourceToggle = useCallback((sourceId: number) => {
    toggleDataSource(sourceId);
    resetPagination();
  }, [toggleDataSource, resetPagination]);

  const handleRowClick = useCallback((prospect: Prospect) => {
    openModal(prospect);
  }, [openModal]);

  const handleClearFilters = useCallback(() => {
    clearFilters();
    resetPagination();
  }, [clearFilters, resetPagination]);


  return (
    <PageLayout
      title="Dashboard"
      subtitle="Overview of your data collection system"
    >
      {/* Main container with filters and content */}
      <div className="flex gap-6">
        {/* Filters Sidebar */}
        <ProspectFilters
          filters={filters}
          dataSources={dataSources}
          onFilterChange={handleFilterChange}
          onDataSourceToggle={handleDataSourceToggle}
          onClearFilters={handleClearFilters}
          hasActiveFilters={hasActiveFilters}
          showAIEnhanced={showAIEnhanced}
          onShowAIEnhancedChange={setShowAIEnhanced}
        />

        {/* Prospects List Card - Main content */}
        <div className="flex-grow">
          <Card className="shadow-lg">
            <CardHeader className="flex flex-row items-center justify-between py-5 px-6 border-b border-gray-200">
              <CardTitle className="text-2xl font-bold text-black">Prospects List</CardTitle>
              <div className="flex items-center space-x-4">
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-medium text-gray-600">Rows per page:</span>
                  <Select value={itemsPerPage.toString()} onValueChange={(value) => handlePageSizeChange(Number(value))}>
                    <SelectTrigger className="w-[80px] h-9 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                      <SelectValue placeholder={itemsPerPage} />
                    </SelectTrigger>
                    <SelectContent>
                      {[10, 20, 30, 50, 100].map(val => (
                        <SelectItem key={val} value={val.toString()} className="text-sm">
                          {val}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-6 px-6 pb-6 relative">
              <ProspectTable
                table={table}
                prospects={prospects}
                isLoading={isLoadingProspects}
                isFetching={isFetchingProspects}
                onRowClick={handleRowClick}
              />
              <ProspectTablePagination
                currentPage={currentPage}
                totalPages={totalPages}
                total={total}
                itemsPerPage={itemsPerPage}
                onPageChange={handlePageChange}
                onPreviousPage={handlePreviousPage}
                onNextPage={handleNextPage}
              />
            </CardContent>
          </Card>
        </div>
      </div>

      <ProspectDetailsModal
        isOpen={isDialogOpen}
        onOpenChange={handleOpenChange}
        selectedProspect={selectedProspect}
        showAIEnhanced={showAIEnhanced}
        onShowAIEnhancedChange={setShowAIEnhanced}
        getProspectStatus={getProspectStatus}
        addToQueue={addToQueue}
        formatUserDate={formatUserDate}
      />
    </PageLayout>
  );
}
