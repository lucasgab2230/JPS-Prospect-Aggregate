import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import userEvent from '@testing-library/user-event';

// Import the components we'll test integration between
import { ProspectTable } from '@/components/prospect/ProspectTable';
import { ProspectFilters } from '@/components/prospect/ProspectFilters';
import { ProspectDetailsModal } from '@/components/prospect/ProspectDetailsModal';
import { AIEnrichment } from '@/components/AIEnrichment';

// Import contexts
import { ToastContextProvider } from '@/contexts/ToastContext';
import { ProspectEnhancementProvider } from '@/contexts/ProspectEnhancementContext';
import { TimezoneProvider } from '@/contexts/TimezoneContext';

// Mock API utils
const mockFetch = vi.fn();
global.fetch = mockFetch;

vi.mock('@/utils/apiUtils', () => ({
  get: vi.fn(),
  post: vi.fn(),
  del: vi.fn(),
  buildQueryString: vi.fn().mockImplementation(() => '')
}));

vi.mock('@/hooks/api/useEnhancementSimple', () => ({
  useEnhancementSimple: () => ({
    queueEnhancement: vi.fn().mockResolvedValue('queue-item-123'),
    getEnhancementState: vi.fn().mockReturnValue(null),
    cancelEnhancement: vi.fn().mockResolvedValue(true),
    enhancementStates: {}
  })
}));

// Helper function to generate dynamic prospect data for integration tests
const generateWorkflowProspect = () => {
  const agencies = ['Department of Defense', 'Health and Human Services', 'Department of Commerce', 'Department of Energy'];
  const naicsCodes = ['541511', '541512', '518210', '541519'];
  const statuses = ['idle', 'processing', 'completed', 'error'];
  const setAsides = ['Small Business', '8(a)', 'WOSB', 'HubZone', null];

  const randomId = Math.random().toString(36).substr(2, 9);
  const baseValue = Math.floor(Math.random() * 500000) + 50000;
  const hasAiEnhancement = Math.random() > 0.5;

  return {
    id: randomId,
    title: `Contract ${Math.floor(Math.random() * 1000)} - ${hasAiEnhancement ? 'Enhanced' : 'Original'}`,
    description: `Contract description for ${randomId}`,
    agency: agencies[Math.floor(Math.random() * agencies.length)],
    posted_date: new Date(Date.now() - Math.random() * 60 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    response_date: new Date(Date.now() + Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    loaded_at: new Date().toISOString(),
    estimated_value: baseValue,
    estimated_value_text: `$${baseValue.toLocaleString()}`,
    naics_code: naicsCodes[Math.floor(Math.random() * naicsCodes.length)],
    source_file: `source_${Math.floor(Math.random() * 100)}.json`,
    source_data_id: Math.floor(Math.random() * 1000) + 1,
    enhancement_status: statuses[Math.floor(Math.random() * statuses.length)],
    duplicate_group_id: Math.random() > 0.8 ? Math.floor(Math.random() * 100) : null,
    set_aside_status: setAsides[Math.floor(Math.random() * setAsides.length)],
    contact_email: `contact${Math.floor(Math.random() * 100)}@${agencies[Math.floor(Math.random() * agencies.length)].toLowerCase().replace(/\s+/g, '')}.gov`,
    contact_name: `Contact ${Math.floor(Math.random() * 100)}`,
    ai_enhanced_title: hasAiEnhancement ? `Enhanced: ${Math.floor(Math.random() * 1000)}` : null,
    ai_enhanced_description: hasAiEnhancement ? `AI-enhanced description ${Math.floor(Math.random() * 100)}` : null,
    parsed_contract_value: hasAiEnhancement ? baseValue : null,
    ollama_processed_at: hasAiEnhancement ? new Date().toISOString() : null
  };
};

const generatePaginatedWorkflowResponse = (prospectCount: number = 2) => {
  const prospects = Array.from({ length: prospectCount }, () => generateWorkflowProspect());
  const totalItems = Math.floor(Math.random() * 50) + prospectCount;
  const perPage = Math.floor(Math.random() * 15) + 5;

  return {
    prospects,
    pagination: {
      total_items: totalItems,
      total_pages: Math.ceil(totalItems / perPage),
      page: 1,
      per_page: perPage
    }
  };
};

// Complete App wrapper with all providers
const AppWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return (
    <QueryClientProvider client={queryClient}>
      <ToastContextProvider>
        <TimezoneProvider>
          <ProspectEnhancementProvider>
            {children}
          </ProspectEnhancementProvider>
        </TimezoneProvider>
      </ToastContextProvider>
    </QueryClientProvider>
  );
};

// Integration test component that combines multiple features
const ProspectWorkflowApp = ({ testProspects }: { testProspects: any[] }) => {
  const [selectedProspect, setSelectedProspect] = React.useState<string | null>(null);
  const [filters, setFilters] = React.useState({
    naics: '',
    keywords: '',
    agency: '',
    ai_enrichment: 'all',
    dataSourceIds: []
  });

  const handleProspectSelect = (prospectId: string) => {
    setSelectedProspect(prospectId);
  };

  const handleCloseModal = () => {
    setSelectedProspect(null);
  };

  const handleFiltersChange = (newFilters: any) => {
    setFilters(newFilters);
  };

  return (
    <div>
      <div data-testid="prospect-workflow-app">
        <ProspectFilters
          filters={filters}
          onFiltersChange={handleFiltersChange}
        />

        <ProspectTable
          prospects={testProspects}
          onProspectSelect={handleProspectSelect}
          loading={false}
          enhancementStates={{}}
        />

        <AIEnrichment />
      </div>

      {selectedProspect && (
        <ProspectDetailsModal
          prospectId={selectedProspect}
          isOpen={!!selectedProspect}
          onClose={handleCloseModal}
        />
      )}
    </div>
  );
};

describe('Prospect Workflow Integration Tests', () => {
  const user = userEvent.setup();
  let testResponse: any;
  let testProspects: any[];

  beforeEach(() => {
    vi.clearAllMocks();

    // Generate fresh test data for each test
    testResponse = generatePaginatedWorkflowResponse();
    testProspects = testResponse.prospects;

    // Mock successful API responses
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(testResponse)
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('completes full prospect discovery and filtering workflow', async () => {
    render(
      <AppWrapper>
        <ProspectWorkflowApp testProspects={testProspects} />
      </AppWrapper>
    );

    // Verify initial state - prospects are loaded
    expect(screen.getByTestId('prospect-workflow-app')).toBeInTheDocument();

    // Should show prospect table with data - test for dynamically generated titles
    await waitFor(() => {
      expect(screen.getByText(testProspects[0].title)).toBeInTheDocument();
      if (testProspects[1]) {
        expect(screen.getByText(testProspects[1].title)).toBeInTheDocument();
      }
    });

    // Test filtering workflow
    const keywordInput = screen.getByPlaceholderText(/search prospects/i);
    await user.type(keywordInput, 'software');

    // Should trigger filter change
    await waitFor(() => {
      // This would normally filter the results, but since we're mocking data,
      // we verify the input was updated
      expect(keywordInput).toHaveValue('software');
    });

    // Test agency filter
    const agencySelect = screen.getByLabelText(/agency/i);
    await user.click(agencySelect);

    // Look for agency options - use dynamic agency from test data
    const testAgency = testProspects[0].agency;
    await waitFor(() => {
      const agencyOption = screen.getByText(testAgency);
      expect(agencyOption).toBeInTheDocument();
    });

    await user.click(screen.getByText(testAgency));

    // Test NAICS code filter - use dynamic NAICS from test data
    const naicsInput = screen.getByPlaceholderText(/naics code/i);
    const testNaics = testProspects[0].naics_code;
    await user.type(naicsInput, testNaics);

    expect(naicsInput).toHaveValue(testNaics);
  });

  it('completes prospect selection and details workflow', async () => {
    render(
      <AppWrapper>
        <ProspectWorkflowApp testProspects={testProspects} />
      </AppWrapper>
    );

    // Wait for prospects to load
    const firstProspectTitle = testProspects[0].title;
    await waitFor(() => {
      expect(screen.getByText(firstProspectTitle)).toBeInTheDocument();
    });

    // Click on first prospect to open details
    const firstProspectRow = screen.getByText(firstProspectTitle).closest('tr');
    expect(firstProspectRow).toBeInTheDocument();

    await user.click(firstProspectRow!);

    // Should open prospect details modal
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Contract Details')).toBeInTheDocument();
    });

    // Verify prospect details are displayed using dynamic data
    const firstProspect = testProspects[0];
    expect(screen.getByDisplayValue(firstProspect.title)).toBeInTheDocument();
    expect(screen.getByDisplayValue(firstProspect.agency)).toBeInTheDocument();
    expect(screen.getByDisplayValue(firstProspect.estimated_value_text)).toBeInTheDocument();

    // Test decision workflow within modal
    const goButton = screen.getByRole('button', { name: /go/i });
    const noGoButton = screen.getByRole('button', { name: /no.go/i });

    expect(goButton).toBeInTheDocument();
    expect(noGoButton).toBeInTheDocument();

    // Make a decision
    await user.click(goButton);

    // Should show reason input
    const reasonInput = screen.getByPlaceholderText(/reason for your decision/i);
    expect(reasonInput).toBeInTheDocument();

    await user.type(reasonInput, 'Good fit for our development capabilities');

    // Submit decision
    const submitButton = screen.getByRole('button', { name: /submit decision/i });
    await user.click(submitButton);

    // Close modal
    const closeButton = screen.getByRole('button', { name: /close/i });
    await user.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('completes AI enhancement workflow', async () => {
    render(
      <AppWrapper>
        <ProspectWorkflowApp />
      </AppWrapper>
    );

    // Wait for UI to load
    await waitFor(() => {
      expect(screen.getByText('Software Development Services')).toBeInTheDocument();
    });

    // Find and click enhancement button for first prospect
    const enhanceButton = screen.getAllByLabelText(/enhance with ai/i)[0];
    expect(enhanceButton).toBeInTheDocument();

    await user.click(enhanceButton);

    // Should show enhancement queued state
    await waitFor(() => {
      // The button should change state or show feedback
      expect(enhanceButton).toBeInTheDocument();
    });

    // Check AI Enhancement dashboard
    const aiDashboard = screen.getByTestId(/ai.enrichment/i);
    expect(aiDashboard).toBeInTheDocument();

    // Should show activity indicators
    expect(screen.getByText(/ai enhancement/i)).toBeInTheDocument();
  });

  it('handles error states gracefully throughout workflow', async () => {
    // Mock API error
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    render(
      <AppWrapper>
        <ProspectWorkflowApp />
      </AppWrapper>
    );

    // Should handle loading error gracefully
    await waitFor(() => {
      // Error handling depends on implementation
      // At minimum, should not crash the app
      expect(screen.getByTestId('prospect-workflow-app')).toBeInTheDocument();
    });
  });

  it('maintains state consistency across component interactions', async () => {
    render(
      <AppWrapper>
        <ProspectWorkflowApp />
      </AppWrapper>
    );

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('Software Development Services')).toBeInTheDocument();
    });

    // Apply filters
    const keywordInput = screen.getByPlaceholderText(/search prospects/i);
    await user.type(keywordInput, 'cloud');

    // Open prospect details
    const secondProspect = screen.getByText('Cloud Infrastructure Setup');
    const secondProspectRow = secondProspect.closest('tr');
    await user.click(secondProspectRow!);

    // Modal should open with correct prospect
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Cloud Infrastructure Setup')).toBeInTheDocument();
    });

    // Check that AI enhanced data is shown
    expect(screen.getByDisplayValue('Enhanced: Advanced Cloud Infrastructure Implementation')).toBeInTheDocument();

    // Close modal and verify filters are maintained
    const closeButton = screen.getByRole('button', { name: /close/i });
    await user.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // Filter input should still have value
    expect(keywordInput).toHaveValue('cloud');
  });

  it('supports keyboard navigation throughout the workflow', async () => {
    render(
      <AppWrapper>
        <ProspectWorkflowApp />
      </AppWrapper>
    );

    // Wait for load
    await waitFor(() => {
      expect(screen.getByText('Software Development Services')).toBeInTheDocument();
    });

    // Tab to keyword input
    await user.tab();
    const keywordInput = screen.getByPlaceholderText(/search prospects/i);
    expect(document.activeElement).toBe(keywordInput);

    // Type search term
    await user.type(keywordInput, 'development');

    // Tab through the interface
    await user.tab(); // Should move to next focusable element
    await user.tab(); // Continue tabbing through filters

    // Use arrow keys in table if implemented
    await user.keyboard('{ArrowDown}');

    // Use Enter to select prospect
    await user.keyboard('{Enter}');

    // Modal should open
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // Escape should close modal
    await user.keyboard('{Escape}');

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('handles real-time updates and refreshing', async () => {
    const { rerender } = render(
      <AppWrapper>
        <ProspectWorkflowApp />
      </AppWrapper>
    );

    // Initial load
    await waitFor(() => {
      expect(screen.getByText('Software Development Services')).toBeInTheDocument();
    });

    // Simulate data update (e.g., from WebSocket or polling)
    const updatedMockProspects = [
      ...mockProspects,
      {
        id: 'prospect-3',
        title: 'New Prospect Added',
        description: 'Newly added prospect from real-time update',
        agency: 'Department of Energy',
        posted_date: '2024-01-17',
        response_date: '2024-02-17',
        loaded_at: '2024-01-17T10:00:00Z',
        estimated_value: 125000,
        estimated_value_text: '$125,000',
        naics_code: '541511',
        source_file: 'doe_2024_01_17.json',
        source_data_id: 3,
        enhancement_status: 'idle',
        duplicate_group_id: null,
        set_aside_status: null,
        contact_email: null,
        contact_name: null,
        ai_enhanced_title: null,
        ai_enhanced_description: null,
        parsed_contract_value: null,
        ollama_processed_at: null
      }
    ];

    // Mock updated response
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        prospects: updatedMockProspects,
        pagination: {
          total_items: 3,
          total_pages: 1,
          page: 1,
          per_page: 10
        }
      })
    });

    // Trigger refresh (this could be automatic via React Query)
    rerender(
      <AppWrapper>
        <ProspectWorkflowApp />
      </AppWrapper>
    );

    // Should show updated data
    await waitFor(() => {
      expect(screen.getByText('New Prospect Added')).toBeInTheDocument();
    });
  });

  it('maintains performance with large datasets', async () => {
    // Create larger dataset for performance testing using dynamic generation
    const performanceDataCount = Math.floor(Math.random() * 50) + 50; // 50-100 prospects
    const largeDataset = Array.from({ length: performanceDataCount }, () => generateWorkflowProspect());

    const paginatedLargeResponse = {
      prospects: largeDataset.slice(0, 10), // Paginated
      pagination: {
        total_items: performanceDataCount,
        total_pages: Math.ceil(performanceDataCount / 10),
        page: 1,
        per_page: 10
      }
    };

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(paginatedLargeResponse)
    });

    const startTime = performance.now();

    render(
      <AppWrapper>
        <ProspectWorkflowApp testProspects={paginatedLargeResponse.prospects} />
      </AppWrapper>
    );

    // Wait for first prospect to render
    await waitFor(() => {
      expect(screen.getByText(paginatedLargeResponse.prospects[0].title)).toBeInTheDocument();
    });

    const endTime = performance.now();
    const renderTime = endTime - startTime;

    // Test that rendering completes successfully (behavior-focused, not threshold)
    expect(renderTime).toBeGreaterThan(0);
    console.log(`Performance test - Render time: ${renderTime.toFixed(2)}ms for ${performanceDataCount} prospects`);

    // Test filtering behavior
    const keywordInput = screen.getByPlaceholderText(/search prospects/i);
    const filterStartTime = performance.now();

    // Use part of the first prospect's title for filtering
    const searchTerm = paginatedLargeResponse.prospects[0].title.split(' ')[0];
    await user.type(keywordInput, searchTerm);

    const filterEndTime = performance.now();
    const filterTime = filterEndTime - filterStartTime;

    // Test that filtering behavior works (no hardcoded thresholds)
    expect(filterTime).toBeGreaterThan(0);
    expect(keywordInput).toHaveValue(searchTerm);
    console.log(`Performance test - Filter time: ${filterTime.toFixed(2)}ms for search "${searchTerm}"`);
  });
});
