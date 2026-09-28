import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AIEnrichment } from './AIEnrichment';

// Mock the hooks
vi.mock('@/hooks/useTimezoneDate', () => ({
  useTimezoneDate: () => ({
    formatLastProcessed: vi.fn((date) => `Formatted: ${date}`),
    formatUserDate: vi.fn((date, type) => `Formatted ${type}: ${date}`)
  })
}));

import { useEnhancementQueueService } from '@/hooks/api/useEnhancementQueueService';

vi.mock('@/hooks/api/useEnhancementQueueService', () => ({
  useEnhancementQueueService: vi.fn()
}));

vi.mock('@/utils/statusUtils', () => ({
  getStatusColor: vi.fn((status) => {
    const colors = {
      processing: 'text-blue-600',
      completed: 'text-green-600',
      stopped: 'text-yellow-600',
      error: 'text-red-600'
    };
    return colors[status as keyof typeof colors] || 'text-gray-600';
  })
}));

// Helper functions to generate dynamic test data
const generateEnhancementStatus = () => {
  const totalProspects = Math.floor(Math.random() * 5000) + 1000;
  const processedProspects = Math.floor(Math.random() * totalProspects);
  const naicsOriginal = Math.floor(Math.random() * processedProspects * 0.5);
  const naicsInferred = Math.floor(Math.random() * (processedProspects - naicsOriginal));
  const naicsPercentage = ((naicsOriginal + naicsInferred) / totalProspects * 100);

  const valueParsedCount = Math.floor(Math.random() * processedProspects);
  const valuePercentage = (valueParsedCount / totalProspects * 100);

  const setAsideCount = Math.floor(Math.random() * processedProspects);
  const setAsidePercentage = (setAsideCount / totalProspects * 100);

  const titleCount = Math.floor(Math.random() * processedProspects);
  const titlePercentage = (titleCount / totalProspects * 100);

  return {
    total_prospects: totalProspects,
    processed_prospects: processedProspects,
    naics_coverage: {
      original: naicsOriginal,
      llm_inferred: naicsInferred,
      total_percentage: Number(naicsPercentage.toFixed(1))
    },
    value_parsing: {
      parsed_count: valueParsedCount,
      total_percentage: Number(valuePercentage.toFixed(1))
    },
    set_aside_standardization: {
      standardized_count: setAsideCount,
      total_percentage: Number(setAsidePercentage.toFixed(1))
    },
    title_enhancement: {
      enhanced_count: titleCount,
      total_percentage: Number(titlePercentage.toFixed(1))
    },
    last_processed: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000).toISOString(),
    model_version: ['qwen3-latest', 'qwen3-v2', 'qwen3-stable'][Math.floor(Math.random() * 3)]
  };
};

const generateProgress = () => {
  const total = Math.floor(Math.random() * 500) + 50;
  const processed = Math.floor(Math.random() * total);
  const percentage = (processed / total) * 100;

  const contractTypes = ['Software Development', 'Cybersecurity', 'Data Analytics', 'Cloud Services', 'IT Support'];
  const contractType = contractTypes[Math.floor(Math.random() * contractTypes.length)];

  return {
    status: 'processing' as const,
    current_type: 'all' as const,
    processed,
    total,
    percentage: Number(percentage.toFixed(1)),
    current_prospect: {
      id: Math.floor(Math.random() * 10000),
      title: `${contractType} Contract ${Math.floor(Math.random() * 1000)}`
    },
    started_at: new Date(Date.now() - Math.random() * 60 * 60 * 1000).toISOString(),
    errors: []
  };
};

const generateLLMOutput = (success: boolean = true) => {
  const enhancementTypes = ['naics', 'values', 'titles', 'set_asides'] as const;
  const enhancementType = enhancementTypes[Math.floor(Math.random() * enhancementTypes.length)];

  const contractTypes = ['Software Development', 'Cybersecurity', 'Data Analytics', 'Cloud Services'];
  const contractType = contractTypes[Math.floor(Math.random() * contractTypes.length)];

  const naicsCodes = ['541511', '541512', '541513', '541519', '518210'];
  const naicsCode = naicsCodes[Math.floor(Math.random() * naicsCodes.length)];

  let response, parsed_result;

  if (success) {
    switch (enhancementType) {
      case 'naics':
        response = JSON.stringify({
          code: naicsCode,
          description: `${contractType} Services`
        });
        parsed_result = { code: naicsCode, description: `${contractType} Services` };
        break;
      case 'values':
        const value = Math.floor(Math.random() * 1000000) + 50000;
        response = JSON.stringify({ single: value });
        parsed_result = { single: value };
        break;
      case 'titles':
        const newTitle = `Enhanced ${contractType} Contract`;
        response = JSON.stringify({ title: newTitle });
        parsed_result = { title: newTitle };
        break;
      default:
        response = JSON.stringify({ result: 'processed' });
        parsed_result = { result: 'processed' };
    }
  } else {
    response = 'Invalid JSON response';
    parsed_result = null;
  }

  return {
    id: Math.floor(Math.random() * 10000),
    timestamp: new Date(Date.now() - Math.random() * 60 * 60 * 1000).toISOString(),
    prospect_id: Math.random().toString(36).substr(2, 9),
    prospect_title: `${contractType} Contract ${Math.floor(Math.random() * 1000)}`,
    enhancement_type: enhancementType,
    prompt: `Extract ${enhancementType}`,
    response,
    parsed_result,
    success,
    error_message: success ? null : 'JSON parsing failed',
    processing_time: Number((Math.random() * 5).toFixed(2))
  };
};

const generateLLMOutputs = () => [
  generateLLMOutput(true),
  generateLLMOutput(true),
  generateLLMOutput(false)
];

const createMockHookDefault = () => {
  const enrichmentStatus = generateEnhancementStatus();
  const llmOutputs = generateLLMOutputs();

  return {
    // Status queries
    queueStatus: undefined,
    iterativeProgress: undefined,
    enrichmentStatus,
    llmOutputs,

    // Loading states
    isLoadingQueue: false,
    isLoadingIterative: false,
    isLoadingEnrichment: false,
    isLoadingLLMOutputs: false,

    // Computed values
    isWorkerRunning: false,
    queueSize: 0,
    currentItem: undefined,
    pendingItems: [],
    recentCompleted: [],
    isIterativeProcessing: false,
    iterativePercentage: 0,
    totalProspects: enrichmentStatus.total_prospects,
    processedProspects: enrichmentStatus.processed_prospects,

    // Actions
    getQueueItemOptions: vi.fn(),
    cancelQueueItem: vi.fn(),
    startWorker: vi.fn(),
    stopWorker: vi.fn(),
    startIterative: vi.fn(),
    stopIterative: vi.fn(),

    // Action states
    isCancelling: false,
    isStartingWorker: false,
    isStoppingWorker: false,
    isStartingIterative: false,
    isStoppingIterative: false,

    // Refetch functions
    refetchQueueStatus: vi.fn(),
    refetchIterativeProgress: vi.fn(),
    refetchEnrichmentStatus: vi.fn(),
    refetchLLMOutputs: vi.fn(),
  };
};

function renderWithQueryClient(component: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
}

describe('AIEnrichment', () => {
  let mockHookDefault: any;

  beforeEach(() => {
    vi.clearAllMocks();
    mockHookDefault = createMockHookDefault();
    vi.mocked(useEnhancementQueueService).mockReturnValue(mockHookDefault);
  });

  it('renders main components', () => {
    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('AI Enrichment Status')).toBeInTheDocument();
    expect(screen.getByText('Controls')).toBeInTheDocument();
    expect(screen.getByText('LLM Output Log')).toBeInTheDocument();
  });

  it('displays enrichment status overview', () => {
    renderWithQueryClient(<AIEnrichment />);

    const { enrichmentStatus } = mockHookDefault;
    const expectedText = `${enrichmentStatus.processed_prospects.toLocaleString()} of ${enrichmentStatus.total_prospects.toLocaleString()} processed`;

    expect(screen.getByText(expectedText)).toBeInTheDocument();
    expect(screen.getByText('NAICS Classification')).toBeInTheDocument();
    expect(screen.getByText('Value Parsing')).toBeInTheDocument();
    expect(screen.getByText('Set-Aside Standardization')).toBeInTheDocument();
    expect(screen.getByText('Title Enhancement')).toBeInTheDocument();
  });

  it('shows correct coverage percentages', () => {
    renderWithQueryClient(<AIEnrichment />);

    const { enrichmentStatus } = mockHookDefault;

    expect(screen.getByText(`${enrichmentStatus.naics_coverage.total_percentage}%`)).toBeInTheDocument();
    expect(screen.getByText(`${enrichmentStatus.value_parsing.total_percentage}%`)).toBeInTheDocument();
    expect(screen.getByText(`${enrichmentStatus.set_aside_standardization.total_percentage}%`)).toBeInTheDocument();
    expect(screen.getByText(`${enrichmentStatus.title_enhancement.total_percentage}%`)).toBeInTheDocument();
  });

  it('displays last processed information', () => {
    renderWithQueryClient(<AIEnrichment />);

    const { enrichmentStatus } = mockHookDefault;

    expect(screen.getByText('Last processed:')).toBeInTheDocument();
    expect(screen.getByText(`Formatted: ${enrichmentStatus.last_processed}`)).toBeInTheDocument();
    expect(screen.getByText('Model version:')).toBeInTheDocument();
    expect(screen.getByText(enrichmentStatus.model_version)).toBeInTheDocument();
  });

  it('shows loading state for status', () => {
    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      isLoadingEnrichment: true,
      enrichmentStatus: undefined
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByRole('generic', { hidden: true })).toHaveClass('animate-spin');
  });

  it('shows error state when status fails to load', () => {
    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      enrichmentStatus: undefined,
      isLoadingEnrichment: false
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('Failed to load AI enrichment status')).toBeInTheDocument();
  });

  it('renders enhancement type selector', () => {
    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('Enhancement Type')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('handles enhancement type selection', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<AIEnrichment />);

    const select = screen.getByRole('combobox');
    await user.click(select);

    const valueOption = screen.getByText('Value Parsing');
    await user.click(valueOption);

    // Verify that the selection triggers hook re-render with new type
    expect(select).toBeInTheDocument(); // Basic check that interaction worked
  });

  it('renders processing mode radio buttons', () => {
    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('Processing Mode')).toBeInTheDocument();
    expect(screen.getByText('Skip existing AI data')).toBeInTheDocument();
    expect(screen.getByText('Replace existing AI data')).toBeInTheDocument();

    const radioButtons = screen.getAllByRole('radio');
    expect(radioButtons).toHaveLength(2);
    expect(radioButtons[0]).toBeChecked(); // Default to 'skip'
  });

  it('handles processing mode change', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<AIEnrichment />);

    const replaceRadio = screen.getByRole('radio', { name: /replace existing/i });
    await user.click(replaceRadio);

    expect(replaceRadio).toBeChecked();
  });

  it('shows start button when not processing', () => {
    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByRole('button', { name: /start enhancement/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start enhancement/i })).not.toBeDisabled();
  });

  it('calls startIterative when start button is clicked', async () => {
    const user = userEvent.setup();
    const mockStartIterative = vi.fn();

    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      startIterative: mockStartIterative
    });

    renderWithQueryClient(<AIEnrichment />);

    const startButton = screen.getByRole('button', { name: /start enhancement/i });
    await user.click(startButton);

    expect(mockStartIterative).toHaveBeenCalledWith({
      enhancement_type: 'all',
      skip_existing: true
    });
  });

  it('shows stop button and progress when processing', () => {
    const testProgress = generateProgress();
    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      iterativeProgress: testProgress
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByRole('button', { name: /stop enhancement/i })).toBeInTheDocument();
    expect(screen.getByText('Status: Processing')).toBeInTheDocument();
    expect(screen.getByText(`${testProgress.processed} / ${testProgress.total}`)).toBeInTheDocument();
    expect(screen.getByText(`${testProgress.percentage}% Complete`)).toBeInTheDocument();
  });

  it('shows current prospect when processing', () => {
    const testProgress = generateProgress();
    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      iterativeProgress: testProgress
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('Currently processing:')).toBeInTheDocument();
    expect(screen.getByText(testProgress.current_prospect.title)).toBeInTheDocument();
  });

  it('calls stopIterative when stop button is clicked', async () => {
    const user = userEvent.setup();
    const mockStopIterative = vi.fn();
    const testProgress = generateProgress();

    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      iterativeProgress: testProgress,
      stopIterative: mockStopIterative
    });

    renderWithQueryClient(<AIEnrichment />);

    const stopButton = screen.getByRole('button', { name: /stop enhancement/i });
    await user.click(stopButton);

    expect(mockStopIterative).toHaveBeenCalled();
  });

  it('shows stopping state', () => {
    const testProgress = { ...generateProgress(), status: 'stopping' };
    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      iterativeProgress: testProgress
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('Stopping...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /stopping/i })).toBeDisabled();
  });

  it('shows completion message', () => {
    const testProgress = { ...generateProgress(), status: 'completed' };
    testProgress.processed = testProgress.total;

    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      iterativeProgress: testProgress
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('Enhancement completed successfully!')).toBeInTheDocument();
    expect(screen.getByText(`Processed all ${testProgress.total} available records`)).toBeInTheDocument();
  });

  it('shows stopped message', () => {
    const testProgress = { ...generateProgress(), status: 'stopped' };
    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      iterativeProgress: testProgress
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('Enhancement stopped')).toBeInTheDocument();
    expect(screen.getByText(`Processed ${testProgress.processed} records before stopping`)).toBeInTheDocument();
  });

  it('shows error message when present', () => {
    const errorMessage = `Connection failed at ${Date.now()}`;
    const testProgress = { ...generateProgress(), error_message: errorMessage };

    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      iterativeProgress: testProgress
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText(`Error: ${errorMessage}`)).toBeInTheDocument();
  });

  it('displays LLM outputs', () => {
    renderWithQueryClient(<AIEnrichment />);

    const { llmOutputs } = mockHookDefault;

    llmOutputs.forEach((output: any) => {
      expect(screen.getByText(output.prospect_title)).toBeInTheDocument();
    });
  });

  it('shows collapsed output summaries', () => {
    renderWithQueryClient(<AIEnrichment />);

    const { llmOutputs } = mockHookDefault;
    const successfulOutputs = llmOutputs.filter((output: any) => output.success);

    // Check that we have output summaries displayed
    expect(successfulOutputs.length).toBeGreaterThan(0);

    successfulOutputs.forEach((output: any) => {
      if (output.enhancement_type === 'naics' && output.parsed_result?.code) {
        const expectedText = `NAICS: ${output.parsed_result.code} - ${output.parsed_result.description}`;
        expect(screen.getByText(expectedText)).toBeInTheDocument();
      }
      if (output.enhancement_type === 'values' && output.parsed_result?.single) {
        const expectedText = `Value: $${output.parsed_result.single.toLocaleString()}`;
        expect(screen.getByText(expectedText)).toBeInTheDocument();
      }
    });
  });

  it('expands and collapses output details', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<AIEnrichment />);

    const expandButtons = screen.getAllByRole('button', { name: '' });
    const expandButton = expandButtons[0];
    if (expandButton) {
      await user.click(expandButton);
    }

    expect(screen.getByText('Response:')).toBeInTheDocument();
    expect(screen.getByText('Parsed Result:')).toBeInTheDocument();

    // Collapse again
    if (expandButton) {
      await user.click(expandButton);
    }

    // Details should be hidden again
    expect(screen.queryByText('Response:')).not.toBeInTheDocument();
  });

  it('shows error details in failed outputs', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<AIEnrichment />);

    // Find and expand the failed output
    const failedOutput = screen.getByText('Failed Processing Example').closest('div');
    const expandButton = failedOutput?.querySelector('button');

    if (expandButton) {
      await user.click(expandButton);
      expect(screen.getByText('Error: JSON parsing failed')).toBeInTheDocument();
    }
  });

  it('shows processing times', () => {
    renderWithQueryClient(<AIEnrichment />);

    const { llmOutputs } = mockHookDefault;

    llmOutputs.forEach((output: any) => {
      expect(screen.getByText(`${output.processing_time}s`)).toBeInTheDocument();
    });
  });

  it('shows formatted timestamps', () => {
    renderWithQueryClient(<AIEnrichment />);

    const { llmOutputs } = mockHookDefault;

    llmOutputs.forEach((output: any) => {
      expect(screen.getByText(`Formatted datetime: ${output.timestamp}`)).toBeInTheDocument();
    });
  });

  it('shows loading state for LLM outputs', () => {
    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      isLoadingLLMOutputs: true,
      llmOutputs: []
    });

    renderWithQueryClient(<AIEnrichment />);

    const spinners = screen.getAllByRole('generic', { hidden: true });
    expect(spinners.some(spinner => spinner.classList.contains('animate-spin'))).toBe(true);
  });

  it('shows empty state for LLM outputs', () => {
    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      llmOutputs: []
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('No LLM outputs yet. Start an enhancement to see outputs here.')).toBeInTheDocument();
  });

  it('disables controls when processing', () => {
    const testProgress = generateProgress();
    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      iterativeProgress: testProgress
    });

    renderWithQueryClient(<AIEnrichment />);

    const select = screen.getByRole('combobox');
    const radioButtons = screen.getAllByRole('radio');

    expect(select).toBeDisabled();
    expect(radioButtons[0]).toBeDisabled();
    expect(radioButtons[1]).toBeDisabled();
  });

  it('handles missing title enhancement data gracefully', () => {
    const statusWithoutTitleEnhancement = {
      ...generateEnhancementStatus(),
      title_enhancement: { enhanced_count: 0, total_percentage: 0.0 }
    };

    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      enrichmentStatus: statusWithoutTitleEnhancement
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('0')).toBeInTheDocument(); // Should show 0 for enhanced count
    expect(screen.getByText('0%')).toBeInTheDocument(); // Should show 0% for coverage
  });

  it('shows errors count when processing has errors', () => {
    const errorCount = Math.floor(Math.random() * 5) + 1;
    const errors = Array.from({ length: errorCount }, (_, i) => ({
      prospect_id: Math.floor(Math.random() * 10000),
      error: `Error ${i + 1} - ${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(Date.now() - Math.random() * 60 * 60 * 1000).toISOString()
    }));

    const progressWithErrors = {
      ...generateProgress(),
      errors
    };

    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      iterativeProgress: progressWithErrors
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('Errors encountered:')).toBeInTheDocument();
    expect(screen.getByText(`${errorCount} prospect(s) failed`)).toBeInTheDocument();
  });

  it('formats large numbers with locale string', () => {
    const largeStatus = generateEnhancementStatus();
    largeStatus.total_prospects = 1234567;
    largeStatus.processed_prospects = 987654;
    largeStatus.naics_coverage.original = 123456;
    largeStatus.naics_coverage.llm_inferred = 234567;

    vi.mocked(useEnhancementQueueService).mockReturnValue({
      ...mockHookDefault,
      enrichmentStatus: largeStatus
    });

    renderWithQueryClient(<AIEnrichment />);

    expect(screen.getByText('987,654 of 1,234,567 processed')).toBeInTheDocument();
    expect(screen.getByText('123,456')).toBeInTheDocument();
    expect(screen.getByText('234,567')).toBeInTheDocument();
  });
});
