import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ProspectFilters } from './ProspectFilters';
import type { ProspectFilters as ProspectFiltersType } from '@/hooks/useProspectFilters';
import type { DataSource } from '@/types';

// Helper function to generate dynamic data sources
const generateDataSource = (): DataSource => {
  const departments = [
    'Department of Defense', 'Department of Energy', 'Health and Human Services',
    'Department of Commerce', 'Department of Justice', 'Department of State',
    'Department of Transportation', 'Department of Treasury', 'Social Security Administration'
  ];
  const department = departments[Math.floor(Math.random() * departments.length)];
  const id = Math.floor(Math.random() * 10000) + 1;

  return {
    id,
    name: department,
    url: `https://${department.toLowerCase().replace(/\s+/g, '')}.gov/opportunities`,
    last_scraped: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString()
  };
};

const generateDataSources = (count: number = 3): DataSource[] => {
  return Array.from({ length: count }, () => generateDataSource());
};

const defaultFilters: ProspectFiltersType = {
  keywords: '',
  naics: '',
  agency: '',
  dataSourceIds: [],
  ai_enrichment: 'all'
};

const createDefaultProps = (dataSources: DataSource[] = generateDataSources()) => ({
  filters: defaultFilters,
  dataSources,
  onFilterChange: vi.fn(),
  onDataSourceToggle: vi.fn(),
  onClearFilters: vi.fn(),
  hasActiveFilters: false,
  showAIEnhanced: false,
  onShowAIEnhancedChange: vi.fn()
});

describe('ProspectFilters', () => {
  let defaultProps: any;

  beforeEach(() => {
    vi.clearAllMocks();
    defaultProps = createDefaultProps();
  });

  it('renders all filter components', () => {
    render(<ProspectFilters {...defaultProps} />);

    expect(screen.getByText('Filters')).toBeInTheDocument();
    expect(screen.getByLabelText('Keywords')).toBeInTheDocument();
    expect(screen.getByLabelText('NAICS Code')).toBeInTheDocument();
    expect(screen.getByLabelText('Agency')).toBeInTheDocument();
    expect(screen.getByText('Data Source')).toBeInTheDocument();
    expect(screen.getByText('AI Enrichment')).toBeInTheDocument();
    expect(screen.getByText('Show AI Enhancements')).toBeInTheDocument();
  });

  it('shows clear all button when filters are active', () => {
    render(<ProspectFilters {...defaultProps} hasActiveFilters={true} />);

    expect(screen.getByText('Clear All')).toBeInTheDocument();
  });

  it('hides clear all button when no filters are active', () => {
    render(<ProspectFilters {...defaultProps} hasActiveFilters={false} />);

    expect(screen.queryByText('Clear All')).not.toBeInTheDocument();
  });

  it('handles keywords input change', async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();
    const props = { ...defaultProps, onFilterChange };

    render(<ProspectFilters {...props} />);

    const keywordsInput = screen.getByLabelText('Keywords');
    await user.type(keywordsInput, 'software');

    // Check that onChange was called progressively for each character
    expect(onFilterChange).toHaveBeenCalledTimes(8);
    expect(onFilterChange).toHaveBeenNthCalledWith(1, 'keywords', 's');
    expect(onFilterChange).toHaveBeenNthCalledWith(8, 'keywords', 'e');
  });

  it('handles NAICS code input change', async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();
    const props = { ...defaultProps, onFilterChange };

    render(<ProspectFilters {...props} />);

    const naicsInput = screen.getByLabelText('NAICS Code');
    await user.type(naicsInput, '54151');

    expect(onFilterChange).toHaveBeenCalledTimes(5);
    expect(onFilterChange).toHaveBeenNthCalledWith(1, 'naics', '5');
    expect(onFilterChange).toHaveBeenNthCalledWith(5, 'naics', '1');
  });

  it('handles agency input change', async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();
    const props = { ...defaultProps, onFilterChange };

    render(<ProspectFilters {...props} />);

    const agencyInput = screen.getByLabelText('Agency');
    await user.type(agencyInput, 'DOD');

    expect(onFilterChange).toHaveBeenCalledTimes(3);
    expect(onFilterChange).toHaveBeenNthCalledWith(1, 'agency', 'D');
    expect(onFilterChange).toHaveBeenNthCalledWith(2, 'agency', 'O');
    expect(onFilterChange).toHaveBeenNthCalledWith(3, 'agency', 'D');
  });

  it('displays all data sources with checkboxes', () => {
    render(<ProspectFilters {...defaultProps} />);

    // Verify all data sources are displayed
    defaultProps.dataSources.forEach((dataSource: DataSource) => {
      expect(screen.getByText(dataSource.name)).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(defaultProps.dataSources.length);
  });

  it('handles data source toggle', async () => {
    const user = userEvent.setup();
    render(<ProspectFilters {...defaultProps} />);

    // Use the first data source for testing
    const firstDataSource = defaultProps.dataSources[0];
    const checkbox = screen.getByRole('checkbox', { name: new RegExp(firstDataSource.name, 'i') });
    await user.click(checkbox);

    expect(defaultProps.onDataSourceToggle).toHaveBeenCalledWith(firstDataSource.id);
  });

  it('shows selected data sources as checked', () => {
    // Select the first two data sources
    const selectedIds = defaultProps.dataSources.slice(0, 2).map((ds: DataSource) => ds.id);
    const filtersWithSources: ProspectFiltersType = {
      ...defaultFilters,
      dataSourceIds: selectedIds
    };

    render(<ProspectFilters {...defaultProps} filters={filtersWithSources} />);

    // Check the first two are selected
    defaultProps.dataSources.slice(0, 2).forEach((dataSource: DataSource) => {
      const checkbox = screen.getByRole('checkbox', { name: new RegExp(dataSource.name, 'i') });
      expect(checkbox).toBeChecked();
    });

    // Check the third one is not selected (if it exists)
    if (defaultProps.dataSources.length > 2) {
      const thirdDataSource = defaultProps.dataSources[2];
      const checkbox = screen.getByRole('checkbox', { name: new RegExp(thirdDataSource.name, 'i') });
      expect(checkbox).not.toBeChecked();
    }
  });

  it('shows message when no data sources available', () => {
    const emptyProps = createDefaultProps([]);
    render(<ProspectFilters {...emptyProps} />);

    expect(screen.getByText('No data sources available')).toBeInTheDocument();
  });

  it('renders AI enrichment select with correct initial value', () => {
    render(<ProspectFilters {...defaultProps} />);

    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();
    expect(select).toHaveAttribute('data-state', 'closed');
  });

  it('handles show AI enhancements toggle', async () => {
    const user = userEvent.setup();
    render(<ProspectFilters {...defaultProps} />);

    const toggle = screen.getByRole('switch');
    await user.click(toggle);

    expect(defaultProps.onShowAIEnhancedChange).toHaveBeenCalledWith(true);
  });

  it('shows correct toggle state and description', () => {
    const { rerender } = render(<ProspectFilters {...defaultProps} showAIEnhanced={false} />);

    expect(screen.getByText('Showing original data only')).toBeInTheDocument();

    rerender(<ProspectFilters {...defaultProps} showAIEnhanced={true} />);

    expect(screen.getByText('Showing AI-enhanced data in table')).toBeInTheDocument();
  });

  it('handles clear all filters button click', async () => {
    const user = userEvent.setup();
    render(<ProspectFilters {...defaultProps} hasActiveFilters={true} />);

    const clearButton = screen.getByText('Clear All');
    await user.click(clearButton);

    expect(defaultProps.onClearFilters).toHaveBeenCalled();
  });

  it('displays active filter summary when filters are applied', () => {
    const selectedDataSources = defaultProps.dataSources.slice(0, 2);
    const activeFilters: ProspectFiltersType = {
      keywords: 'software',
      naics: '541511',
      agency: 'DOD',
      dataSourceIds: selectedDataSources.map((ds: DataSource) => ds.id),
      ai_enrichment: 'enhanced'
    };

    render(<ProspectFilters {...defaultProps} filters={activeFilters} hasActiveFilters={true} />);

    expect(screen.getByText('Active filters:')).toBeInTheDocument();
    expect(screen.getByText('Keywords: software')).toBeInTheDocument();
    expect(screen.getByText('NAICS: 541511')).toBeInTheDocument();
    expect(screen.getByText('Agency: DOD')).toBeInTheDocument();
    expect(screen.getByText('AI: Enhanced Only')).toBeInTheDocument();

    // Check for the actual data source names
    selectedDataSources.forEach((dataSource: DataSource) => {
      expect(screen.getByText(`Source: ${dataSource.name}`)).toBeInTheDocument();
    });
  });

  it('allows removing individual filters from summary', async () => {
    const user = userEvent.setup();
    const selectedDataSource = defaultProps.dataSources[0];
    const activeFilters: ProspectFiltersType = {
      keywords: 'software',
      naics: '541511',
      agency: 'DOD',
      dataSourceIds: [selectedDataSource.id],
      ai_enrichment: 'enhanced'
    };

    render(<ProspectFilters {...defaultProps} filters={activeFilters} hasActiveFilters={true} />);

    // Remove keywords filter
    const keywordsRemoveButton = screen.getByText('Keywords: software').nextElementSibling;
    await user.click(keywordsRemoveButton as Element);

    expect(defaultProps.onFilterChange).toHaveBeenCalledWith('keywords', '');

    // Remove NAICS filter
    const naicsRemoveButton = screen.getByText('NAICS: 541511').nextElementSibling;
    await user.click(naicsRemoveButton as Element);

    expect(defaultProps.onFilterChange).toHaveBeenCalledWith('naics', '');

    // Remove agency filter
    const agencyRemoveButton = screen.getByText('Agency: DOD').nextElementSibling;
    await user.click(agencyRemoveButton as Element);

    expect(defaultProps.onFilterChange).toHaveBeenCalledWith('agency', '');

    // Remove AI enrichment filter
    const aiRemoveButton = screen.getByText('AI: Enhanced Only').nextElementSibling;
    await user.click(aiRemoveButton as Element);

    expect(defaultProps.onFilterChange).toHaveBeenCalledWith('ai_enrichment', 'all');

    // Remove data source filter - use the first selected data source
    const firstDataSource = defaultProps.dataSources[0];
    const sourceRemoveButton = screen.getByText(`Source: ${firstDataSource.name}`).nextElementSibling;
    await user.click(sourceRemoveButton as Element);

    expect(defaultProps.onDataSourceToggle).toHaveBeenCalledWith(firstDataSource.id);
  });

  it('displays filter values correctly in inputs', () => {
    const filtersWithValues: ProspectFiltersType = {
      keywords: 'AI development',
      naics: '541511',
      agency: 'Defense',
      dataSourceIds: [2],
      ai_enrichment: 'original'
    };

    render(<ProspectFilters {...defaultProps} filters={filtersWithValues} />);

    expect(screen.getByDisplayValue('AI development')).toBeInTheDocument();
    expect(screen.getByDisplayValue('541511')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Defense')).toBeInTheDocument();
  });

  it('shows correct placeholder text in inputs', () => {
    render(<ProspectFilters {...defaultProps} />);

    expect(screen.getByPlaceholderText('Search in title, description...')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('e.g., 541511, 334')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('e.g., DOD, HHS, DHS')).toBeInTheDocument();
  });

  it('handles keyboard navigation in inputs', async () => {
    const user = userEvent.setup();
    render(<ProspectFilters {...defaultProps} />);

    const keywordsInput = screen.getByLabelText('Keywords');
    const naicsInput = screen.getByLabelText('NAICS Code');

    await user.click(keywordsInput);
    await user.keyboard('{Tab}');

    expect(naicsInput).toHaveFocus();
  });

  it('maintains focus after filter changes', async () => {
    const user = userEvent.setup();
    render(<ProspectFilters {...defaultProps} />);

    const keywordsInput = screen.getByLabelText('Keywords');
    await user.click(keywordsInput);
    await user.type(keywordsInput, 'test');

    expect(keywordsInput).toHaveFocus();
  });

  it('shows data source count in scrollable container', () => {
    const manyDataSources = generateDataSources(10);
    const manyProps = createDefaultProps(manyDataSources);

    render(<ProspectFilters {...manyProps} />);

    const firstDataSourceName = manyDataSources[0].name;
    const dataSourceContainer = screen.getByText(firstDataSourceName).closest('.max-h-48');
    expect(dataSourceContainer).toHaveClass('overflow-y-auto');

    // All data sources should be rendered
    manyDataSources.forEach((dataSource) => {
      expect(screen.getByText(dataSource.name)).toBeInTheDocument();
    });
  });

  it('handles edge case with undefined filter values', () => {
    const undefinedFilters: ProspectFiltersType = {
      keywords: undefined as any,
      naics: undefined as any,
      agency: undefined as any,
      dataSourceIds: undefined as any,
      ai_enrichment: undefined as any
    };

    render(<ProspectFilters {...defaultProps} filters={undefinedFilters} />);

    const keywordsInput = screen.getByLabelText('Keywords');
    const naicsInput = screen.getByLabelText('NAICS Code');
    const agencyInput = screen.getByLabelText('Agency');

    expect(keywordsInput).toHaveValue('');
    expect(naicsInput).toHaveValue('');
    expect(agencyInput).toHaveValue('');
  });

  it('shows AI enrichment select component', () => {
    render(<ProspectFilters {...defaultProps} />);

    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();
    expect(screen.getByText('AI Enrichment')).toBeInTheDocument();
  });

  it('applies correct styling classes', () => {
    render(<ProspectFilters {...defaultProps} />);

    const container = screen.getByText('Filters').closest('.w-80');
    expect(container).toHaveClass('flex-shrink-0');

    const card = screen.getByText('Filters').closest('.shadow-lg');
    expect(card).toBeInTheDocument();
  });

  it('supports accessibility features', () => {
    render(<ProspectFilters {...defaultProps} />);

    // Labels should be associated with inputs
    const keywordsInput = screen.getByLabelText('Keywords');
    const naicsInput = screen.getByLabelText('NAICS Code');
    const agencyInput = screen.getByLabelText('Agency');

    expect(keywordsInput).toHaveAttribute('id', 'keywords');
    expect(naicsInput).toHaveAttribute('id', 'naics');
    expect(agencyInput).toHaveAttribute('id', 'agency');

    // Switch should have proper labeling
    const aiSwitch = screen.getByRole('switch');
    expect(aiSwitch).toHaveAttribute('id', 'show-ai-table');
  });
});
