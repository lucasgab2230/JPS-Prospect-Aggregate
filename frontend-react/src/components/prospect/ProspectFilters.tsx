import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { ProspectFilters as ProspectFiltersType } from '@/hooks/useProspectFilters';
import type { DataSource } from '@/types';

interface ProspectFiltersProps {
  filters: ProspectFiltersType;
  dataSources: DataSource[];
  onFilterChange: (filterKey: keyof ProspectFiltersType, value: string) => void;
  onDataSourceToggle: (sourceId: number) => void;
  onClearFilters: () => void;
  hasActiveFilters: boolean;
  showAIEnhanced: boolean;
  onShowAIEnhancedChange: (checked: boolean) => void;
}

export function ProspectFilters({
  filters,
  dataSources,
  onFilterChange,
  onDataSourceToggle,
  onClearFilters,
  hasActiveFilters,
  showAIEnhanced,
  onShowAIEnhancedChange
}: ProspectFiltersProps) {
  return (
    <div className="w-80 flex-shrink-0">
      <Card className="shadow-lg">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-semibold text-black">Filters</CardTitle>
            {hasActiveFilters && (
              <Button
                variant="outline"
                size="sm"
                onClick={onClearFilters}
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
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => onFilterChange('keywords', e.target.value)}
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
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => onFilterChange('naics', e.target.value)}
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
                    onChange={() => onDataSourceToggle(source.id)}
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

          {/* AI Enrichment Filter */}
          <div className="space-y-2">
            <Label htmlFor="ai-enrichment" className="text-sm font-medium text-gray-700">
              AI Enrichment
            </Label>
            <Select
              value={filters.ai_enrichment || 'all'}
              onValueChange={(value: 'all' | 'enhanced' | 'original') => onFilterChange('ai_enrichment', value)}
            >
              <SelectTrigger className="text-sm">
                <SelectValue placeholder="All prospects" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Prospects</SelectItem>
                <SelectItem value="enhanced">AI Enhanced Only</SelectItem>
                <SelectItem value="original">Original Data Only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Show AI Enhancements Toggle */}
          <div className="space-y-2 pt-2 border-t border-gray-200">
            <div className="flex items-center justify-between">
              <Label htmlFor="show-ai-table" className="text-sm font-medium text-gray-700">
                Show AI Enhancements
              </Label>
              <Switch
                id="show-ai-table"
                checked={showAIEnhanced}
                onCheckedChange={onShowAIEnhancedChange}
              />
            </div>
            <p className="text-xs text-gray-500">
              {showAIEnhanced ? 'Showing AI-enhanced data in table' : 'Showing original data only'}
            </p>
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
                      onClick={() => onFilterChange('keywords', '')}
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
                      onClick={() => onFilterChange('naics', '')}
                      className="ml-1 text-green-500 hover:text-green-700"
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
                          onClick={() => onDataSourceToggle(sourceId)}
                          className="ml-1 text-orange-500 hover:text-orange-700"
                        >
                          ×
                        </button>
                      </div>
                    );
                  })
                )}
                {filters.ai_enrichment && filters.ai_enrichment !== 'all' && (
                  <div className="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded flex justify-between items-center">
                    <span>AI: {filters.ai_enrichment === 'enhanced' ? 'Enhanced Only' : 'Original Only'}</span>
                    <button
                      onClick={() => onFilterChange('ai_enrichment', 'all')}
                      className="ml-1 text-indigo-500 hover:text-indigo-700"
                    >
                      ×
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
