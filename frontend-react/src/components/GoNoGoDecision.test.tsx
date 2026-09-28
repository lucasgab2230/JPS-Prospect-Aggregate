import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GoNoGoDecision } from './GoNoGoDecision';

// Mock the API hooks
vi.mock('../hooks/api', () => ({
  useCreateDecision: vi.fn(),
  useProspectDecisions: vi.fn(),
  useDeleteDecision: vi.fn()
}));

// Mock the error hook
vi.mock('@/hooks/useError', () => ({
  useError: () => ({
    handleError: vi.fn()
  })
}));

const mockCreateDecision = {
  mutateAsync: vi.fn(),
  isPending: false
};

const mockDeleteDecision = {
  mutateAsync: vi.fn(),
  isPending: false
};

const mockProspectDecisions = {
  data: null,
  isLoading: false,
  error: null
};

// Helper function to generate dynamic decision data
function generateMockDecision() {
  const decisions = ['go', 'no-go'];
  const reasons = [
    'Aligns with our capabilities',
    'Outside our scope',
    'Good budget match',
    'Timeline conflicts',
    'Strong technical fit',
    'Resource constraints'
  ];

  return {
    id: Math.floor(Math.random() * 1000) + 1,
    decision: decisions[Math.floor(Math.random() * decisions.length)],
    reason: reasons[Math.floor(Math.random() * reasons.length)],
    created_at: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString()
  };
}

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

describe('GoNoGoDecision', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    const { useCreateDecision, useProspectDecisions, useDeleteDecision } = require('../hooks/api');
    useCreateDecision.mockReturnValue(mockCreateDecision);
    useDeleteDecision.mockReturnValue(mockDeleteDecision);
    useProspectDecisions.mockReturnValue(mockProspectDecisions);
  });

  describe('Loading State', () => {
    it('shows loading state when decisions are loading', () => {
      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        isLoading: true
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" prospectTitle="Test Contract" />
      );

      const loadingElements = screen.getAllByRole('generic', { hidden: true });
      expect(loadingElements.some(el => el.classList.contains('animate-pulse'))).toBe(true);
    });
  });

  describe('Compact Mode', () => {
    it('renders GO and NO-GO buttons when no existing decision', () => {
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      expect(screen.getByRole('button', { name: 'GO' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'NO-GO' })).toBeInTheDocument();
    });

    it('shows existing decision badge when decision exists', () => {
      const mockDecision = generateMockDecision();
      mockDecision.decision = 'go'; // Ensure it's a GO decision for this test

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      expect(screen.getByText('GO')).toBeInTheDocument();
      expect(screen.getByText('(with reason)')).toBeInTheDocument();
    });

    it('shows NO-GO badge for no-go decisions', () => {
      const mockDecision = generateMockDecision();
      mockDecision.decision = 'no-go'; // Ensure it's a NO-GO decision for this test

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      expect(screen.getByText('NO-GO')).toBeInTheDocument();
      expect(screen.getByText('NO-GO')).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('does not show reason indicator when no reason exists', () => {
      const mockDecision = generateMockDecision();
      mockDecision.reason = ''; // Ensure no reason for this test

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      expect(screen.queryByText('(with reason)')).not.toBeInTheDocument();
    });
  });

  describe('Full Mode', () => {
    it('renders full decision interface when no compact prop', () => {
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" prospectTitle="Test Contract" />
      );

      expect(screen.getByText('Go/No-Go Decision')).toBeInTheDocument();
      expect(screen.getByText('Prospect: Test Contract')).toBeInTheDocument();
      expect(screen.getByText("What's your decision on this prospect?")).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'GO' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'NO-GO' })).toBeInTheDocument();
    });

    it('shows existing decision details in full mode', () => {
      const mockDecision = generateMockDecision();
      mockDecision.decision = 'go'; // Set to GO for this test

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" prospectTitle="Test Contract" />
      );

      expect(screen.getByText('Current Decision:')).toBeInTheDocument();
      expect(screen.getByText('GO')).toBeInTheDocument();
      expect(screen.getByText('Reason:')).toBeInTheDocument();
      expect(screen.getByText(mockDecision.reason)).toBeInTheDocument();
      expect(screen.getByText(/Decision made on/)).toBeInTheDocument();
    });

    it('shows change decision options when decision exists', () => {
      const mockDecision = generateMockDecision();
      mockDecision.decision = 'go'; // Set to GO for this test

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" />
      );

      expect(screen.getByText('Want to change your decision?')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Change to NO-GO' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Undo Decision' })).toBeInTheDocument();
    });

    it('shows opposite change button based on current decision', () => {
      const mockDecision = generateMockDecision();
      mockDecision.decision = 'no-go'; // Set to NO-GO for this test

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" />
      );

      expect(screen.getByRole('button', { name: 'Change to GO' })).toBeInTheDocument();
    });
  });

  describe('Decision Dialog', () => {
    it('opens reason dialog when GO button is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" prospectTitle="Test Contract" compact={true} />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      await user.click(goButton);

      expect(screen.getByText('GO Decision')).toBeInTheDocument();
      expect(screen.getByText('Prospect: Test Contract')).toBeInTheDocument();
      expect(screen.getByLabelText('Reason (optional)')).toBeInTheDocument();
    });

    it('opens reason dialog when NO-GO button is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const noGoButton = screen.getByRole('button', { name: 'NO-GO' });
      await user.click(noGoButton);

      expect(screen.getByText('NO-GO Decision')).toBeInTheDocument();
    });

    it('allows entering reason in dialog', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      await user.click(goButton);

      const reasonInput = screen.getByLabelText('Reason (optional)');
      await user.type(reasonInput, 'Perfect fit for our capabilities');

      expect(reasonInput).toHaveValue('Perfect fit for our capabilities');
    });

    it('submits decision with reason', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      await user.click(goButton);

      const reasonInput = screen.getByLabelText('Reason (optional)');
      await user.type(reasonInput, 'Great opportunity');

      const confirmButton = screen.getByRole('button', { name: 'Confirm GO' });
      await user.click(confirmButton);

      expect(mockCreateDecision.mutateAsync).toHaveBeenCalledWith({
        prospect_id: 'TEST-001',
        decision: 'go',
        reason: 'Great opportunity'
      });
    });

    it('submits decision without reason when reason is empty', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const noGoButton = screen.getByRole('button', { name: 'NO-GO' });
      await user.click(noGoButton);

      const confirmButton = screen.getByRole('button', { name: 'Confirm NO-GO' });
      await user.click(confirmButton);

      expect(mockCreateDecision.mutateAsync).toHaveBeenCalledWith({
        prospect_id: 'TEST-001',
        decision: 'no-go',
        reason: undefined
      });
    });

    it('closes dialog when cancel is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      await user.click(goButton);

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      expect(screen.queryByText('GO Decision')).not.toBeInTheDocument();
    });

    it('clears form state when dialog is closed', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      // Open dialog and enter reason
      const goButton = screen.getByRole('button', { name: 'GO' });
      await user.click(goButton);

      const reasonInput = screen.getByLabelText('Reason (optional)');
      await user.type(reasonInput, 'Test reason');

      // Cancel
      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await user.click(cancelButton);

      // Reopen dialog
      await user.click(goButton);

      // Reason should be cleared
      const newReasonInput = screen.getByLabelText('Reason (optional)');
      expect(newReasonInput).toHaveValue('');
    });

    it('shows saving state during submission', async () => {
      const user = userEvent.setup();
      const { useCreateDecision } = require('../hooks/api');
      useCreateDecision.mockReturnValue({
        ...mockCreateDecision,
        isPending: true
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      await user.click(goButton);

      expect(screen.getByText('Saving...')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    });

    it('shows AI training hint in full mode', () => {
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      fireEvent.click(goButton);

      expect(screen.getByText('This will help train our AI to understand company preferences')).toBeInTheDocument();
    });
  });

  describe('Undo Decision', () => {
    it('calls delete mutation when undo is clicked', async () => {
      const user = userEvent.setup();
      const mockDecision = generateMockDecision();

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" />
      );

      const undoButton = screen.getByRole('button', { name: 'Undo Decision' });
      await user.click(undoButton);

      expect(mockDeleteDecision.mutateAsync).toHaveBeenCalledWith(mockDecision.id);
    });

    it('shows undoing state during deletion', () => {
      const mockDecision = generateMockDecision();

      const { useProspectDecisions, useDeleteDecision } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });
      useDeleteDecision.mockReturnValue({
        ...mockDeleteDecision,
        isPending: true
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" />
      );

      expect(screen.getByText('Undoing...')).toBeInTheDocument();
    });
  });

  describe('Disabled States', () => {
    it('disables buttons when create mutation is pending', () => {
      const { useCreateDecision } = require('../hooks/api');
      useCreateDecision.mockReturnValue({
        ...mockCreateDecision,
        isPending: true
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      expect(screen.getByRole('button', { name: 'GO' })).toBeDisabled();
      expect(screen.getByRole('button', { name: 'NO-GO' })).toBeDisabled();
    });

    it('disables change buttons when create mutation is pending', () => {
      const mockDecision = generateMockDecision();
      mockDecision.decision = 'go';

      const { useProspectDecisions, useCreateDecision } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });
      useCreateDecision.mockReturnValue({
        ...mockCreateDecision,
        isPending: true
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" />
      );

      expect(screen.getByRole('button', { name: 'Change to NO-GO' })).toBeDisabled();
    });

    it('disables undo button when delete mutation is pending', () => {
      const mockDecision = generateMockDecision();

      const { useProspectDecisions, useDeleteDecision } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });
      useDeleteDecision.mockReturnValue({
        ...mockDeleteDecision,
        isPending: true
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" />
      );

      expect(screen.getByRole('button', { name: 'Undoing...' })).toBeDisabled();
    });
  });

  describe('Error Handling', () => {
    it('handles prospect decisions loading error gracefully', () => {
      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        error: new Error('Failed to load decisions')
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      // Should still render decision buttons even with error
      expect(screen.getByRole('button', { name: 'GO' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'NO-GO' })).toBeInTheDocument();
    });

    it('handles empty decisions array', () => {
      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: []
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      expect(screen.getByRole('button', { name: 'GO' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'NO-GO' })).toBeInTheDocument();
    });

    it('handles null decisions data', () => {
      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: null
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      expect(screen.getByRole('button', { name: 'GO' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'NO-GO' })).toBeInTheDocument();
    });
  });

  describe('Styling and Classes', () => {
    it('applies correct styling for GO badge', () => {
      const mockDecision = generateMockDecision();
      mockDecision.decision = 'go';

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const goBadge = screen.getByText('GO');
      expect(goBadge).toHaveClass('bg-green-100', 'text-green-800');
    });

    it('applies correct styling for NO-GO badge', () => {
      const mockDecision = generateMockDecision();
      mockDecision.decision = 'no-go';

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const noGoBadge = screen.getByText('NO-GO');
      expect(noGoBadge).toHaveClass('bg-red-100', 'text-red-800');
    });

    it('applies correct button styling in compact mode', () => {
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      const noGoButton = screen.getByRole('button', { name: 'NO-GO' });

      expect(goButton).toHaveClass('text-green-700', 'border-green-300', 'hover:bg-green-50');
      expect(noGoButton).toHaveClass('text-red-700', 'border-red-300', 'hover:bg-red-50');
    });
  });

  describe('Accessibility', () => {
    it('provides proper labels for form inputs', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      await user.click(goButton);

      const reasonInput = screen.getByLabelText('Reason (optional)');
      expect(reasonInput).toHaveAttribute('id', 'reason');
    });

    it('provides proper button labels and roles', () => {
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      expect(screen.getByRole('button', { name: 'GO' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'NO-GO' })).toBeInTheDocument();
    });

    it('includes title attribute for reason indicator', () => {
      const mockDecision = generateMockDecision();
      mockDecision.decision = 'go';
      // Ensure it has a reason for this test
      if (!mockDecision.reason) {
        mockDecision.reason = 'Test reason for tooltip';
      }

      const { useProspectDecisions } = require('../hooks/api');
      useProspectDecisions.mockReturnValue({
        ...mockProspectDecisions,
        data: {
          data: {
            decisions: [mockDecision]
          }
        }
      });

      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const reasonIndicator = screen.getByText('(with reason)');
      expect(reasonIndicator).toHaveAttribute('title', mockDecision.reason);
    });
  });

  describe('Edge Cases', () => {
    it('handles string and number prospect IDs', () => {
      renderWithQueryClient(
        <GoNoGoDecision prospectId={123} compact={true} />
      );

      expect(screen.getByRole('button', { name: 'GO' })).toBeInTheDocument();
    });

    it('trims whitespace from reason input', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      await user.click(goButton);

      const reasonInput = screen.getByLabelText('Reason (optional)');
      await user.type(reasonInput, '  Good opportunity  ');

      const confirmButton = screen.getByRole('button', { name: 'Confirm GO' });
      await user.click(confirmButton);

      expect(mockCreateDecision.mutateAsync).toHaveBeenCalledWith({
        prospect_id: 'TEST-001',
        decision: 'go',
        reason: 'Good opportunity'
      });
    });

    it('sets reason to undefined when only whitespace', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(
        <GoNoGoDecision prospectId="TEST-001" compact={true} />
      );

      const goButton = screen.getByRole('button', { name: 'GO' });
      await user.click(goButton);

      const reasonInput = screen.getByLabelText('Reason (optional)');
      await user.type(reasonInput, '   ');

      const confirmButton = screen.getByRole('button', { name: 'Confirm GO' });
      await user.click(confirmButton);

      expect(mockCreateDecision.mutateAsync).toHaveBeenCalledWith({
        prospect_id: 'TEST-001',
        decision: 'go',
        reason: undefined
      });
    });
  });
});
