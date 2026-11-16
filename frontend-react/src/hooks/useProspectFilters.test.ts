import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useProspectFilters, ProspectFilters } from './useProspectFilters';

describe('useProspectFilters', () => {
  it('initializes with default filter values', () => {
    const { result } = renderHook(() => useProspectFilters());

    expect(result.current.filters).toEqual({
      naics: '',
      keywords: '',
      agency: '',
      ai_enrichment: 'all',
      dataSourceIds: []
    });

    expect(result.current.hasActiveFilters).toBe(false);
  });

  it('detects active filters correctly', () => {
    const { result } = renderHook(() => useProspectFilters());

    // No active filters initially
    expect(result.current.hasActiveFilters).toBe(false);

    // Keywords filter makes it active
    act(() => {
      result.current.updateFilter('keywords', 'software');
    });
    expect(result.current.hasActiveFilters).toBe(true);

    // Clear keywords
    act(() => {
      result.current.updateFilter('keywords', '');
    });
    expect(result.current.hasActiveFilters).toBe(false);

    // NAICS filter makes it active
    act(() => {
      result.current.updateFilter('naics', '541511');
    });
    expect(result.current.hasActiveFilters).toBe(true);

    // Clear NAICS
    act(() => {
      result.current.updateFilter('naics', '');
    });
    expect(result.current.hasActiveFilters).toBe(false);

    // Agency filter makes it active
    act(() => {
      result.current.updateFilter('agency', 'DOD');
    });
    expect(result.current.hasActiveFilters).toBe(true);

    // Clear agency
    act(() => {
      result.current.updateFilter('agency', '');
    });
    expect(result.current.hasActiveFilters).toBe(false);
  });

  it('detects AI enrichment filter as active when not "all"', () => {
    const { result } = renderHook(() => useProspectFilters());

    // Default 'all' is not active
    expect(result.current.hasActiveFilters).toBe(false);

    // 'enhanced' makes it active
    act(() => {
      result.current.updateFilter('ai_enrichment', 'enhanced');
    });
    expect(result.current.hasActiveFilters).toBe(true);

    // 'original' makes it active
    act(() => {
      result.current.updateFilter('ai_enrichment', 'original');
    });
    expect(result.current.hasActiveFilters).toBe(true);

    // Back to 'all' makes it inactive
    act(() => {
      result.current.updateFilter('ai_enrichment', 'all');
    });
    expect(result.current.hasActiveFilters).toBe(false);
  });

  it('detects data source IDs as active when array has items', () => {
    const { result } = renderHook(() => useProspectFilters());

    // Empty array is not active
    expect(result.current.hasActiveFilters).toBe(false);

    // Add a data source
    act(() => {
      result.current.toggleDataSource(1);
    });
    expect(result.current.hasActiveFilters).toBe(true);
    expect(result.current.filters.dataSourceIds).toEqual([1]);

    // Add another data source
    act(() => {
      result.current.toggleDataSource(2);
    });
    expect(result.current.hasActiveFilters).toBe(true);
    expect(result.current.filters.dataSourceIds).toEqual([1, 2]);

    // Remove first data source
    act(() => {
      result.current.toggleDataSource(1);
    });
    expect(result.current.hasActiveFilters).toBe(true);
    expect(result.current.filters.dataSourceIds).toEqual([2]);

    // Remove last data source
    act(() => {
      result.current.toggleDataSource(2);
    });
    expect(result.current.hasActiveFilters).toBe(false);
    expect(result.current.filters.dataSourceIds).toEqual([]);
  });

  it('updates individual filter fields correctly', () => {
    const { result } = renderHook(() => useProspectFilters());

    // Update keywords
    act(() => {
      result.current.updateFilter('keywords', 'artificial intelligence');
    });
    expect(result.current.filters.keywords).toBe('artificial intelligence');
    expect(result.current.filters.naics).toBe('');
    expect(result.current.filters.agency).toBe('');

    // Update NAICS
    act(() => {
      result.current.updateFilter('naics', '541511');
    });
    expect(result.current.filters.keywords).toBe('artificial intelligence');
    expect(result.current.filters.naics).toBe('541511');
    expect(result.current.filters.agency).toBe('');

    // Update agency
    act(() => {
      result.current.updateFilter('agency', 'Department of Defense');
    });
    expect(result.current.filters.keywords).toBe('artificial intelligence');
    expect(result.current.filters.naics).toBe('541511');
    expect(result.current.filters.agency).toBe('Department of Defense');
  });

  it('toggles data sources correctly', () => {
    const { result } = renderHook(() => useProspectFilters());

    // Initially empty
    expect(result.current.filters.dataSourceIds).toEqual([]);

    // Add data source 1
    act(() => {
      result.current.toggleDataSource(1);
    });
    expect(result.current.filters.dataSourceIds).toEqual([1]);

    // Add data source 3
    act(() => {
      result.current.toggleDataSource(3);
    });
    expect(result.current.filters.dataSourceIds).toEqual([1, 3]);

    // Add data source 2 (should be added to end)
    act(() => {
      result.current.toggleDataSource(2);
    });
    expect(result.current.filters.dataSourceIds).toEqual([1, 3, 2]);

    // Remove data source 3 (should maintain order)
    act(() => {
      result.current.toggleDataSource(3);
    });
    expect(result.current.filters.dataSourceIds).toEqual([1, 2]);

    // Remove data source 1
    act(() => {
      result.current.toggleDataSource(1);
    });
    expect(result.current.filters.dataSourceIds).toEqual([2]);

    // Remove data source 2
    act(() => {
      result.current.toggleDataSource(2);
    });
    expect(result.current.filters.dataSourceIds).toEqual([]);
  });

  it('toggles existing data source correctly (remove)', () => {
    const { result } = renderHook(() => useProspectFilters());

    // Start with some data sources
    act(() => {
      result.current.setFilters({
        naics: '',
        keywords: '',
        agency: '',
        ai_enrichment: 'all',
        dataSourceIds: [1, 2, 3]
      });
    });

    expect(result.current.filters.dataSourceIds).toEqual([1, 2, 3]);

    // Toggle existing data source (should remove it)
    act(() => {
      result.current.toggleDataSource(2);
    });
    expect(result.current.filters.dataSourceIds).toEqual([1, 3]);
  });

  it('clears all filters correctly', () => {
    const { result } = renderHook(() => useProspectFilters());

    // Set up some filters
    act(() => {
      result.current.updateFilter('keywords', 'AI development');
      result.current.updateFilter('naics', '541511');
      result.current.updateFilter('agency', 'DOD');
      result.current.updateFilter('ai_enrichment', 'enhanced');
      result.current.toggleDataSource(1);
      result.current.toggleDataSource(2);
    });

    expect(result.current.hasActiveFilters).toBe(true);
    expect(result.current.filters).toEqual({
      keywords: 'AI development',
      naics: '541511',
      agency: 'DOD',
      ai_enrichment: 'enhanced',
      dataSourceIds: [1, 2]
    });

    // Clear all filters
    act(() => {
      result.current.clearFilters();
    });

    expect(result.current.hasActiveFilters).toBe(false);
    expect(result.current.filters).toEqual({
      naics: '',
      keywords: '',
      agency: '',
      ai_enrichment: 'all',
      dataSourceIds: []
    });
  });

  it('sets filters directly using setFilters', () => {
    const { result } = renderHook(() => useProspectFilters());

    const newFilters: ProspectFilters = {
      keywords: 'cloud computing',
      naics: '518210',
      agency: 'HHS',
      ai_enrichment: 'original',
      dataSourceIds: [4, 5, 6]
    };

    act(() => {
      result.current.setFilters(newFilters);
    });

    expect(result.current.filters).toEqual(newFilters);
    expect(result.current.hasActiveFilters).toBe(true);
  });

  it('maintains stable references for callback functions', () => {
    const { result, rerender } = renderHook(() => useProspectFilters());

    const initialUpdateFilter = result.current.updateFilter;
    const initialToggleDataSource = result.current.toggleDataSource;
    const initialClearFilters = result.current.clearFilters;
    const initialSetFilters = result.current.setFilters;

    // Trigger a re-render by updating a filter
    act(() => {
      result.current.updateFilter('keywords', 'test');
    });

    rerender();

    // Functions should maintain stable references
    expect(result.current.updateFilter).toBe(initialUpdateFilter);
    expect(result.current.toggleDataSource).toBe(initialToggleDataSource);
    expect(result.current.clearFilters).toBe(initialClearFilters);
    expect(result.current.setFilters).toBe(initialSetFilters);
  });

  it('handles edge cases with undefined/null dataSourceIds', () => {
    const { result } = renderHook(() => useProspectFilters());

    // Set filters with undefined dataSourceIds
    act(() => {
      result.current.setFilters({
        keywords: 'test',
        naics: '',
        agency: '',
        ai_enrichment: 'all',
        dataSourceIds: undefined as any
      });
    });

    // Should handle undefined gracefully
    act(() => {
      result.current.toggleDataSource(1);
    });

    expect(result.current.filters.dataSourceIds).toEqual([1]);
  });

  it('handles complex filter combination scenarios', () => {
    const { result } = renderHook(() => useProspectFilters());

    // Apply multiple filters in sequence
    act(() => {
      result.current.updateFilter('keywords', 'machine learning');
    });
    expect(result.current.hasActiveFilters).toBe(true);

    act(() => {
      result.current.updateFilter('ai_enrichment', 'enhanced');
    });
    expect(result.current.hasActiveFilters).toBe(true);

    act(() => {
      result.current.toggleDataSource(1);
    });
    expect(result.current.hasActiveFilters).toBe(true);

    // Clear keywords but keep others
    act(() => {
      result.current.updateFilter('keywords', '');
    });
    expect(result.current.hasActiveFilters).toBe(true); // Still active due to AI enrichment and data source

    // Clear AI enrichment
    act(() => {
      result.current.updateFilter('ai_enrichment', 'all');
    });
    expect(result.current.hasActiveFilters).toBe(true); // Still active due to data source

    // Clear data source
    act(() => {
      result.current.toggleDataSource(1);
    });
    expect(result.current.hasActiveFilters).toBe(false); // Now inactive
  });

  it('preserves filter state across multiple operations', () => {
    const { result } = renderHook(() => useProspectFilters());

    // Set up initial state
    act(() => {
      result.current.updateFilter('keywords', 'cybersecurity');
      result.current.updateFilter('naics', '541512');
      result.current.toggleDataSource(1);
      result.current.toggleDataSource(3);
    });

    const initialState = result.current.filters;

    // Perform additional operations
    act(() => {
      result.current.updateFilter('agency', 'DHS');
      result.current.toggleDataSource(2);
    });

    // Verify state progression
    expect(result.current.filters.keywords).toBe(initialState.keywords);
    expect(result.current.filters.naics).toBe(initialState.naics);
    expect(result.current.filters.agency).toBe('DHS');
    expect(result.current.filters.dataSourceIds).toEqual([1, 3, 2]);
  });

  it('returns consistent hasActiveFilters for equivalent states', () => {
    const { result: result1 } = renderHook(() => useProspectFilters());
    const { result: result2 } = renderHook(() => useProspectFilters());

    // Both should start inactive
    expect(result1.current.hasActiveFilters).toBe(result2.current.hasActiveFilters);

    // Apply same filters to both
    act(() => {
      result1.current.updateFilter('keywords', 'blockchain');
      result2.current.updateFilter('keywords', 'blockchain');
    });

    expect(result1.current.hasActiveFilters).toBe(result2.current.hasActiveFilters);
    expect(result1.current.hasActiveFilters).toBe(true);

    // Clear filters on both
    act(() => {
      result1.current.clearFilters();
      result2.current.clearFilters();
    });

    expect(result1.current.hasActiveFilters).toBe(result2.current.hasActiveFilters);
    expect(result1.current.hasActiveFilters).toBe(false);
  });
});
