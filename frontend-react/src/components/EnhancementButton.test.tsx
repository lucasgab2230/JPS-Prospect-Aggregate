import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { EnhancementButton } from './EnhancementButton';

// Mock the context
const mockAddToQueue = vi.fn();
const mockGetProspectStatus = vi.fn();
const mockCancelEnhancement = vi.fn();

vi.mock('@/contexts/ProspectEnhancementContext', () => ({
  useProspectEnhancement: () => ({
    addToQueue: mockAddToQueue,
    getProspectStatus: mockGetProspectStatus,
    cancelEnhancement: mockCancelEnhancement
  })
}));

// Mock error handler
const mockHandleError = vi.fn();
vi.mock('./EnhancementErrorBoundary', () => ({
  useEnhancementErrorHandler: () => ({
    handleError: mockHandleError
  })
}));

describe('EnhancementButton', () => {
  const defaultProps = {
    prospect: { id: '123', ollama_processed_at: null },
    userId: 1,
    forceRedo: false
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockGetProspectStatus.mockReturnValue(null);
  });

  it('renders with default text when no status', () => {
    render(<EnhancementButton {...defaultProps} />);

    expect(screen.getByRole('button')).toHaveTextContent('Enhance with AI');
    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('calls addToQueue when clicked', async () => {
    mockAddToQueue.mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<EnhancementButton {...defaultProps} />);

    const button = screen.getByRole('button');
    await user.click(button);

    expect(mockAddToQueue).toHaveBeenCalledWith({
      prospect_id: '123',
      user_id: 1,
      force_redo: false
    });
  });

  it('calls onEnhancementStart callback when provided', async () => {
    const onEnhancementStart = vi.fn();
    const user = userEvent.setup();

    render(<EnhancementButton {...defaultProps} onEnhancementStart={onEnhancementStart} />);

    const button = screen.getByRole('button');
    await user.click(button);

    expect(onEnhancementStart).toHaveBeenCalled();
    // Verify onEnhancementStart was called before addToQueue
    const callOrder = vi.mocked(onEnhancementStart).mock.invocationCallOrder[0];
    const addToQueueOrder = mockAddToQueue.mock.invocationCallOrder[0];
    expect(callOrder).toBeLessThan(addToQueueOrder || 0);
  });

  it('shows queued status with position', () => {
    mockGetProspectStatus.mockReturnValue({
      status: 'queued',
      queuePosition: 3,
      estimatedTimeRemaining: 120
    });

    render(<EnhancementButton {...defaultProps} />);

    expect(screen.getByText(/Queued \(#3\)/)).toBeInTheDocument();
    expect(screen.getByText('~2m')).toBeInTheDocument();
    // Check button has orange background for queued state
    const buttons = screen.getAllByRole('button');
    expect(buttons[0].className).toContain('bg-orange-600');
    // Check cancel button exists
    expect(buttons[1]).toBeInTheDocument();
  });

  it('shows processing status with current step', () => {
    mockGetProspectStatus.mockReturnValue({
      status: 'processing',
      currentStep: 'Analyzing values'
    });

    render(<EnhancementButton {...defaultProps} />);

    expect(screen.getByText('Analyzing values')).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeDisabled();

    // Check for spinning icon
    const spinIcon = screen.getByRole('button').querySelector('.animate-spin');
    expect(spinIcon).toBeInTheDocument();
  });

  it('shows generic processing message when no current step', () => {
    mockGetProspectStatus.mockReturnValue({
      status: 'processing'
    });

    render(<EnhancementButton {...defaultProps} />);

    expect(screen.getByText('Enhancing...')).toBeInTheDocument();
  });

  it('allows cancellation when queued', async () => {
    mockGetProspectStatus.mockReturnValue({
      status: 'queued',
      queuePosition: 2
    });
    mockCancelEnhancement.mockResolvedValue(true);
    const user = userEvent.setup();

    render(<EnhancementButton {...defaultProps} />);

    // Find the cancel button (nested button with X icon)
    const buttons = screen.getAllByRole('button');
    const cancelButton = buttons.find(btn => btn.querySelector('.text-red-600'));
    expect(cancelButton).toBeInTheDocument();

    await user.click(cancelButton!);

    expect(mockCancelEnhancement).toHaveBeenCalledWith('123');
  });

  it('handles cancellation failure', async () => {
    mockGetProspectStatus.mockReturnValue({
      status: 'queued',
      queuePosition: 1
    });
    mockCancelEnhancement.mockResolvedValue(false);
    const user = userEvent.setup();

    render(<EnhancementButton {...defaultProps} />);

    const buttons = screen.getAllByRole('button');
    const cancelButton = buttons.find(btn => btn.querySelector('.text-red-600'));
    await user.click(cancelButton!);

    expect(mockHandleError).toHaveBeenCalledWith(
      expect.any(Error),
      'Enhancement Cancellation'
    );
    expect(mockHandleError.mock.calls[0]?.[0].message).toBe('Failed to cancel enhancement');
  });

  it('handles enhancement errors', async () => {
    const error = new Error('Queue is full');
    mockAddToQueue.mockRejectedValue(error);
    const user = userEvent.setup();

    render(<EnhancementButton {...defaultProps} />);

    const button = screen.getByRole('button');
    await user.click(button);

    await waitFor(() => {
      expect(mockHandleError).toHaveBeenCalledWith(error, 'Enhancement Queue');
    });
  });

  it('passes forceRedo parameter correctly', async () => {
    const user = userEvent.setup();

    render(<EnhancementButton {...defaultProps} forceRedo={true} />);

    const button = screen.getByRole('button');
    await user.click(button);

    expect(mockAddToQueue).toHaveBeenCalledWith({
      prospect_id: '123',
      user_id: 1,
      force_redo: true
    });
  });

  it('uses custom userId when provided', async () => {
    const user = userEvent.setup();

    render(<EnhancementButton {...defaultProps} userId={42} />);

    const button = screen.getByRole('button');
    await user.click(button);

    expect(mockAddToQueue).toHaveBeenCalledWith({
      prospect_id: '123',
      user_id: 42,
      force_redo: false
    });
  });

  it('prevents click propagation on cancel button', async () => {
    mockGetProspectStatus.mockReturnValue({
      status: 'queued',
      queuePosition: 1
    });

    const parentClickHandler = vi.fn();
    const user = userEvent.setup();

    render(
      <div onClick={parentClickHandler}>
        <EnhancementButton {...defaultProps} />
      </div>
    );

    const buttons = screen.getAllByRole('button');
    const cancelButton = buttons.find(btn => btn.querySelector('.text-red-600'));
    await user.click(cancelButton!);

    expect(mockCancelEnhancement).toHaveBeenCalled();
    expect(parentClickHandler).not.toHaveBeenCalled();
  });

  it('applies correct styles based on status', () => {
    // Default state
    const { rerender } = render(<EnhancementButton {...defaultProps} />);
    let button = screen.getByRole('button');
    expect(button).toHaveClass('bg-blue-600');

    // Queued state
    mockGetProspectStatus.mockReturnValue({ status: 'queued' });
    rerender(<EnhancementButton {...defaultProps} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons[0]).toHaveClass('bg-orange-600');

    // Processing state
    mockGetProspectStatus.mockReturnValue({ status: 'processing' });
    rerender(<EnhancementButton {...defaultProps} />);
    button = screen.getByRole('button');
    expect(button).toHaveClass('disabled:bg-gray-400');
  });

  it('handles cancellation errors gracefully', async () => {
    mockGetProspectStatus.mockReturnValue({
      status: 'queued',
      queuePosition: 1
    });
    const error = new Error('Network error');
    mockCancelEnhancement.mockRejectedValue(error);
    const user = userEvent.setup();

    render(<EnhancementButton {...defaultProps} />);

    const buttons = screen.getAllByRole('button');
    const cancelButton = buttons.find(btn => btn.querySelector('.text-red-600'));
    await user.click(cancelButton!);

    await waitFor(() => {
      expect(mockHandleError).toHaveBeenCalledWith(error, 'Enhancement Cancellation');
    });
  });

  it('shows "Redo Enhancement" for already enhanced prospects', () => {
    const enhancedProspect = {
      ...defaultProps.prospect,
      ollama_processed_at: '2024-01-01T00:00:00Z'
    };

    render(<EnhancementButton {...defaultProps} prospect={enhancedProspect} />);

    expect(screen.getByText('Redo Enhancement')).toBeInTheDocument();
  });

  it('sets force_redo to true for already enhanced prospects', async () => {
    const enhancedProspect = {
      ...defaultProps.prospect,
      ollama_processed_at: '2024-01-01T00:00:00Z'
    };
    const user = userEvent.setup();

    render(<EnhancementButton {...defaultProps} prospect={enhancedProspect} />);

    const button = screen.getByRole('button');
    await user.click(button);

    expect(mockAddToQueue).toHaveBeenCalledWith({
      prospect_id: '123',
      user_id: 1,
      force_redo: true
    });
  });
});
