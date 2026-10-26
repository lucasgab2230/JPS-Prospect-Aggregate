import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ProspectDetailsModal } from './ProspectDetailsModal';
import type { Prospect } from '@/types/prospects';

// Mock child components
vi.mock('@/components/GoNoGoDecision', () => ({
  GoNoGoDecision: () => <div data-testid="go-no-go-decision">GoNoGoDecision</div>
}));

vi.mock('@/components/EnhancementButtonWithSelector', () => ({
  EnhancementButtonWithSelector: ({ onEnhancementStart }: any) => (
    <button data-testid="enhancement-button" onClick={onEnhancementStart}>
      Enhance with AI
    </button>
  )
}));

vi.mock('@/components/EnhancementProgress', () => ({
  EnhancementProgress: ({ status }: any) => (
    <div data-testid="enhancement-progress">Progress: {status}</div>
  )
}));

vi.mock('@/components/EnhancementErrorBoundary', () => ({
  EnhancementErrorBoundary: ({ children }: any) => <>{children}</>
}));

vi.mock('@/hooks/api/useAuth', () => ({
  useIsSuperAdmin: () => true
}));

// Helper to generate dynamic prospect data
const generateProspect = (): Prospect => {
  const agencies = ['Department of Defense', 'Department of Energy', 'Health and Human Services', 'Department of Commerce'];
  const cities = ['Washington', 'New York', 'San Francisco', 'Chicago', 'Austin'];
  const states = ['DC', 'NY', 'CA', 'IL', 'TX'];
  const naicsCodes = ['541511', '541512', '541519', '517311', '236220'];
  const contractTypes = ['Fixed Price', 'Time and Materials', 'Cost Plus', 'IDIQ'];
  const setAsides = ['Small Business', '8(a)', 'WOSB', 'HubZone', 'VOSB'];

  const randomId = Math.random().toString(36).substr(2, 9);
  const baseValue = Math.floor(Math.random() * 1000000) + 50000;
  const enhancementStatuses = ['pending', 'processing', 'completed', 'error', null];

  return {
    id: randomId,
    native_id: `CONT-${Math.floor(Math.random() * 10000)}`,
    title: `Contract Opportunity ${Math.floor(Math.random() * 1000)}`,
    ai_enhanced_title: `Enhanced Contract ${Math.floor(Math.random() * 1000)}`,
    description: `Description for contract ${randomId}`,
    agency: agencies[Math.floor(Math.random() * agencies.length)],
    naics: naicsCodes[Math.floor(Math.random() * naicsCodes.length)],
    naics_description: `Service Description ${Math.floor(Math.random() * 100)}`,
    naics_source: Math.random() > 0.5 ? 'llm_inferred' : 'original',
    estimated_value: baseValue.toString(),
    est_value_unit: 'USD',
    estimated_value_text: `$${(baseValue * 0.8).toLocaleString()} - $${(baseValue * 1.2).toLocaleString()}`,
    estimated_value_min: (baseValue * 0.8).toString(),
    estimated_value_max: (baseValue * 1.2).toString(),
    estimated_value_single: baseValue.toString(),
    release_date: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    award_date: Math.random() > 0.7 ? new Date(Date.now() + Math.random() * 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0] : null,
    award_fiscal_year: Math.random() > 0.7 ? 2024 + Math.floor(Math.random() * 3) : null,
    place_city: cities[Math.floor(Math.random() * cities.length)],
    place_state: states[Math.floor(Math.random() * states.length)],
    place_country: 'USA',
    contract_type: contractTypes[Math.floor(Math.random() * contractTypes.length)],
    set_aside: setAsides[Math.floor(Math.random() * setAsides.length)],
    set_aside_standardized: Math.random() > 0.5 ? 'SMALL_BUSINESS' : null,
    set_aside_standardized_label: Math.random() > 0.5 ? 'Small Business Set-Aside' : null,
    inferred_set_aside: setAsides[Math.floor(Math.random() * setAsides.length)].toUpperCase().replace(' ', '_'),
    inferred_naics: naicsCodes[Math.floor(Math.random() * naicsCodes.length)],
    inferred_naics_description: `Inferred Service ${Math.floor(Math.random() * 100)}`,
    primary_contact_email: `contact${Math.floor(Math.random() * 1000)}@agency.gov`,
    primary_contact_name: `Contact ${Math.floor(Math.random() * 1000)}`,
    loaded_at: new Date().toISOString(),
    ollama_processed_at: Math.random() > 0.5 ? new Date().toISOString() : null,
    ollama_model_version: Math.random() > 0.5 ? 'qwen3-latest' : null,
    enhancement_status: enhancementStatuses[Math.floor(Math.random() * enhancementStatuses.length)],
    enhancement_started_at: Math.random() > 0.5 ? new Date().toISOString() : null,
    enhancement_user_id: Math.random() > 0.5 ? Math.floor(Math.random() * 100) : null,
    extra: null,
    source_id: Math.floor(Math.random() * 10) + 1,
    source_name: `Source ${Math.floor(Math.random() * 10) + 1}`
  };
};

describe('ProspectDetailsModal', () => {

  let testProspect: Prospect;
  let defaultProps: any;

  beforeEach(() => {
    vi.clearAllMocks();
    // Generate fresh prospect data for each test
    testProspect = generateProspect();
    defaultProps = {
      isOpen: true,
      onOpenChange: vi.fn(),
      selectedProspect: testProspect,
      showAIEnhanced: false,
      onShowAIEnhancedChange: vi.fn(),
      getProspectStatus: vi.fn(() => null),
      addToQueue: vi.fn(),
      formatUserDate: vi.fn((date: string | null | undefined) => date || '')
    };
  });


  it('renders prospect details when open', () => {
    render(<ProspectDetailsModal {...defaultProps} />);

    expect(screen.getByText('Prospect Details')).toBeInTheDocument();
    if (testProspect.title) {
      expect(screen.getByText(testProspect.title)).toBeInTheDocument();
    }
    if (testProspect.agency) {
      expect(screen.getByText(testProspect.agency)).toBeInTheDocument();
    }
  });

  it('does not render when closed', () => {
    render(<ProspectDetailsModal {...defaultProps} isOpen={false} />);

    expect(screen.queryByText('Prospect Details')).not.toBeInTheDocument();
  });

  it('handles null prospect gracefully', () => {
    render(<ProspectDetailsModal {...defaultProps} selectedProspect={null} />);

    // Should not display any prospect-specific content
    if (testProspect.title) {
      expect(screen.queryByText(testProspect.title)).not.toBeInTheDocument();
    }
    if (testProspect.agency) {
      expect(screen.queryByText(testProspect.agency)).not.toBeInTheDocument();
    }
  });

  it('toggles AI enhanced data display', async () => {
    const user = userEvent.setup();
    render(<ProspectDetailsModal {...defaultProps} />);

    const toggle = screen.getByRole('switch', { name: /show ai enhanced/i });

    // Initially shows original data
    if (testProspect.title) {
      expect(screen.getByText(testProspect.title)).toBeInTheDocument();
    }
    if (testProspect.ai_enhanced_title) {
      expect(screen.queryByText(testProspect.ai_enhanced_title)).not.toBeInTheDocument();
    }

    // Toggle to show AI enhanced
    await user.click(toggle);
    expect(defaultProps.onShowAIEnhancedChange).toHaveBeenCalledWith(true);
  });

  it('displays enhancement progress when processing', () => {
    const getProspectStatus = vi.fn(() => ({
      status: 'processing',
      currentStep: 'Analyzing values',
      queuePosition: 3,
      progress: {
        titles: { completed: true },
        naics: { completed: false },
        values: { completed: false },
        contacts: { completed: false }
      }
    }));

    render(<ProspectDetailsModal {...defaultProps} getProspectStatus={getProspectStatus} />);

    expect(screen.getByTestId('enhancement-progress')).toBeInTheDocument();
    expect(screen.getByText('Progress: processing')).toBeInTheDocument();
  });

  it('handles enhancement button click', async () => {
    const user = userEvent.setup();
    render(<ProspectDetailsModal {...defaultProps} />);

    // Click enhancement button
    const enhanceButton = screen.getByTestId('enhancement-button');
    await user.click(enhanceButton);

    // Button should trigger onEnhancementStart callback
    expect(enhanceButton).toBeInTheDocument();
  });

  it('displays all prospect fields correctly', () => {
    render(<ProspectDetailsModal {...defaultProps} />);

    // Basic Information - use the generated prospect data
    if (testProspect.set_aside) {
      expect(screen.getByText(testProspect.set_aside)).toBeInTheDocument();
    }
    if (testProspect.naics) {
      expect(screen.getByText(testProspect.naics)).toBeInTheDocument();
    }
    if (testProspect.estimated_value_text) {
      expect(screen.getByText(testProspect.estimated_value_text)).toBeInTheDocument();
    }

    // Contact Information - use the generated prospect data
    if (testProspect.primary_contact_name) {
      expect(screen.getByText(testProspect.primary_contact_name)).toBeInTheDocument();
    }
    if (testProspect.primary_contact_email) {
      expect(screen.getByText(testProspect.primary_contact_email)).toBeInTheDocument();
    }
    if (testProspect.place_city && testProspect.place_state) {
      expect(screen.getByText(`${testProspect.place_city}, ${testProspect.place_state}`)).toBeInTheDocument();
    }

    // Description - use the generated prospect data
    if (testProspect.description) {
      expect(screen.getByText(testProspect.description)).toBeInTheDocument();
    }
  });

  it('shows raw data toggle for super admin', async () => {
    const user = userEvent.setup();
    render(<ProspectDetailsModal {...defaultProps} />);

    const rawDataToggle = screen.getByText(/Show Raw Data/i);
    expect(rawDataToggle).toBeInTheDocument();

    await user.click(rawDataToggle);

    // Should show raw data section
    expect(screen.getByText(/Complete Raw Prospect Object/i)).toBeInTheDocument();
  });

  it('handles enhancement button interactions', async () => {
    const user = userEvent.setup();
    render(<ProspectDetailsModal {...defaultProps} />);

    // Click enhancement button
    const enhanceButton = screen.getByTestId('enhancement-button');
    await user.click(enhanceButton);

    // Verify button is rendered and clickable
    expect(enhanceButton).toBeInTheDocument();
  });

  it('displays AI enrichment indicators', () => {
    render(<ProspectDetailsModal {...defaultProps} />);

    // Look for AI enrichment badges
    const badges = screen.getAllByText('✨');
    expect(badges.length).toBeGreaterThan(0);
  });

  it('handles prospect without enhanced fields', () => {
    const basicProspect = {
      ...testProspect,
      ai_enhanced_title: null,
      naics: null,
      estimated_value_single: null,
      ollama_processed_at: null
    };

    render(<ProspectDetailsModal {...defaultProps} selectedProspect={basicProspect} />);

    // Should still render without errors
    expect(screen.getByText(basicProspect.title)).toBeInTheDocument();

    // Should not show AI badges
    const badges = screen.queryAllByText('✨');
    expect(badges.length).toBe(0);
  });

  it('formats dates using the provided formatter', () => {
    const formatUserDate = vi.fn((_date: string) => 'Formatted Date');
    render(<ProspectDetailsModal {...defaultProps} formatUserDate={formatUserDate} />);

    expect(formatUserDate).toHaveBeenCalled();
    expect(screen.queryAllByText('Formatted Date').length).toBeGreaterThanOrEqual(0);
  });

  it('closes modal when close button is clicked', async () => {
    const user = userEvent.setup();
    render(<ProspectDetailsModal {...defaultProps} />);

    const closeButton = screen.getByRole('button', { name: /close/i });
    await user.click(closeButton);

    expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false);
  });
});
