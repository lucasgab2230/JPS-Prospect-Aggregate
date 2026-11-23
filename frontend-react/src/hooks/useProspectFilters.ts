import { useState, useCallback } from 'react';

export interface ProspectFilters {
  naics?: string;
  keywords?: string;
  ai_enrichment?: 'all' | 'enhanced' | 'original';
  dataSourceIds?: number[];
  agency?: string;
}

export function useProspectFilters() {
  const [filters, setFilters] = useState<ProspectFilters>({
    naics: '',
    keywords: '',
    ai_enrichment: 'all',
    dataSourceIds: []
  });

  const updateFilter = useCallback((filterKey: keyof ProspectFilters, value: string) => {
    setFilters(prev => ({ ...prev, [filterKey]: value }));
  }, []);

  const toggleDataSource = useCallback((sourceId: number) => {
    setFilters(prev => {
      const currentIds = prev.dataSourceIds || [];
      const newIds = currentIds.includes(sourceId)
        ? currentIds.filter((id: number) => id !== sourceId)
        : [...currentIds, sourceId];
      return { ...prev, dataSourceIds: newIds };
    });
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({
      naics: '',
      keywords: '',
      ai_enrichment: 'all',
      dataSourceIds: []
    });
  }, []);

  const hasActiveFilters = Object.entries(filters).some(([key, value]) => {
    if (key === 'ai_enrichment') return value !== 'all';
    if (key === 'dataSourceIds') return Array.isArray(value) && value.length > 0;
    return value !== '';
  });

  return {
    filters,
    setFilters,
    updateFilter,
    toggleDataSource,
    clearFilters,
    hasActiveFilters
  };
}
