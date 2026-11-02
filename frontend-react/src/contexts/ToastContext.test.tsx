import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React, { act } from 'react';
import { ToastContextProvider, useToast } from './ToastContext';
import { AppError, ErrorSeverity, ErrorCategory } from '@/types/errors';

// Mock the Toast UI components
vi.mock('@/components/ui/Toast', () => ({
  Toast: ({ children, onOpenChange, ...props }: any) =>
    React.createElement('div', {
      'data-testid': 'toast',
      'data-variant': props.variant,
      'data-severity': props.severity,
      onClick: () => onOpenChange?.(false),
      ...props
    }, children),
  ToastClose: () => React.createElement('button', { 'data-testid': 'toast-close' }, 'Close'),
  ToastDescription: ({ children }: any) => React.createElement('div', { 'data-testid': 'toast-description' }, children),
  ToastProvider: ({ children }: any) => React.createElement('div', { 'data-testid': 'toast-provider' }, children),
  ToastTitle: ({ children }: any) => React.createElement('div', { 'data-testid': 'toast-title' }, children),
  ToastViewport: () => React.createElement('div', { 'data-testid': 'toast-viewport' }),
  ToastAction: ({ children, onClick }: any) => React.createElement('button', { 'data-testid': 'toast-action', onClick }, children),
  ToastIcon: ({ variant, severity }: any) => React.createElement('div', { 'data-testid': 'toast-icon', 'data-variant': variant, 'data-severity': severity }),
}));

// Helper to generate dynamic toast content
const generateToastContent = () => {
  const titles = ['Alert', 'Notification', 'Update', 'Message', 'Status'];
  const descriptions = ['Process completed', 'Action required', 'System update', 'New information', 'Status changed'];
  return {
    title: titles[Math.floor(Math.random() * titles.length)] + ` ${Math.floor(Math.random() * 1000)}`,
    description: descriptions[Math.floor(Math.random() * descriptions.length)] + ` ${Math.floor(Math.random() * 1000)}`
  };
};

// Test component that uses the toast context
const TestComponent = () => {
  const {
    showToast,
    showErrorToast,
    showSuccessToast,
    showInfoToast,
    showWarningToast
  } = useToast();

  const handleShowToast = () => {
    const content = generateToastContent();
    showToast({ title: content.title, description: content.description });
  };

  const handleShowError = () => {
    const messages = ['Operation failed', 'Network error', 'Validation failed', 'Permission denied'];
    const message = messages[Math.floor(Math.random() * messages.length)] + ` ${Math.floor(Math.random() * 1000)}`;
    showErrorToast(message);
  };

  const handleShowSuccess = () => {
    const content = generateToastContent();
    showSuccessToast(content.title, content.description);
  };

  const handleShowInfo = () => {
    const content = generateToastContent();
    showInfoToast(content.title, content.description);
  };

  const handleShowWarning = () => {
    const content = generateToastContent();
    showWarningToast(content.title, content.description);
  };

  const handleShowJSError = () => {
    const errorMessages = ['Async operation failed', 'Network timeout', 'Parse error', 'Connection lost'];
    const message = errorMessages[Math.floor(Math.random() * errorMessages.length)];
    showErrorToast(new Error(message));
  };

  return (
    <div>
      <button onClick={handleShowToast}>
        Show Toast
      </button>
      <button onClick={handleShowError}>
        Show Error
      </button>
      <button onClick={handleShowSuccess}>
        Show Success
      </button>
      <button onClick={handleShowInfo}>
        Show Info
      </button>
      <button onClick={handleShowWarning}>
        Show Warning
      </button>
      <button onClick={handleShowJSError}>
        Show JS Error
      </button>
    </div>
  );
};

// Helper to generate dynamic error data
const generateAppError = (severity: ErrorSeverity = ErrorSeverity.ERROR): AppError => {
  const errorCodes = ['NETWORK_ERROR', 'VALIDATION_ERROR', 'AUTH_ERROR', 'SYSTEM_ERROR', 'USER_ERROR'];
  const messages = ['Operation failed', 'Invalid input', 'Access denied', 'System unavailable', 'User action required'];
  const userMessages = ['Something went wrong', 'Please check your input', 'Authentication required', 'Service temporarily unavailable', 'Please try again'];
  const categories = [ErrorCategory.SYSTEM, ErrorCategory.NETWORK, ErrorCategory.VALIDATION, ErrorCategory.USER, ErrorCategory.EXTERNAL];

  return {
    code: errorCodes[Math.floor(Math.random() * errorCodes.length)],
    message: messages[Math.floor(Math.random() * messages.length)],
    severity,
    category: categories[Math.floor(Math.random() * categories.length)],
    timestamp: new Date(),
    userMessage: userMessages[Math.floor(Math.random() * userMessages.length)],
    technicalDetails: `Technical details: ${Math.random().toString(36).substr(2, 9)}`,
    recoveryActions: [
      {
        label: Math.random() > 0.5 ? 'Retry' : 'Dismiss',
        action: vi.fn(),
        primary: Math.random() > 0.5
      }
    ]
  };
};

describe('ToastContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it('provides toast context to children', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    expect(screen.getByText('Show Toast')).toBeInTheDocument();
    expect(screen.getByText('Show Error')).toBeInTheDocument();
    expect(screen.getByText('Show Success')).toBeInTheDocument();
  });

  it('throws error when useToast is used outside provider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(() => {
      render(<TestComponent />);
    }).toThrow('useToast must be used within a ToastProvider');

    consoleSpy.mockRestore();
  });

  it('shows basic toast with title and description', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Toast'));

    expect(screen.getByTestId('toast')).toBeInTheDocument();
    // Should display title and description content
    const title = screen.getByTestId('toast-title');
    const description = screen.getByTestId('toast-description');
    expect(title.textContent).toBeTruthy();
    expect(description.textContent).toBeTruthy();
  });

  it('shows error toast with correct styling', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Error'));

    const toast = screen.getByTestId('toast');
    expect(toast).toBeInTheDocument();
    expect(toast).toHaveAttribute('data-variant', 'destructive');
    // Should display error title and description
    expect(screen.getByTestId('toast-title')).toHaveTextContent('Error');
    const description = screen.getByTestId('toast-description');
    expect(description.textContent).toBeTruthy();
  });

  it('shows success toast with correct styling', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Success'));

    const toast = screen.getByTestId('toast');
    expect(toast).toBeInTheDocument();
    expect(toast).toHaveAttribute('data-variant', 'success');
    // Should display success content
    const title = screen.getByTestId('toast-title');
    const description = screen.getByTestId('toast-description');
    expect(title.textContent).toBeTruthy();
    expect(description.textContent).toBeTruthy();
  });

  it('shows info toast with correct styling', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Info'));

    const toast = screen.getByTestId('toast');
    expect(toast).toBeInTheDocument();
    expect(toast).toHaveAttribute('data-variant', 'info');
    expect(toast).toHaveAttribute('data-severity', 'info');
    // Should display info content
    const title = screen.getByTestId('toast-title');
    expect(title.textContent).toBeTruthy();
  });

  it('shows warning toast with correct styling', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Warning'));

    const toast = screen.getByTestId('toast');
    expect(toast).toBeInTheDocument();
    expect(toast).toHaveAttribute('data-variant', 'warning');
    expect(toast).toHaveAttribute('data-severity', 'warning');
    // Should display warning content
    const title = screen.getByTestId('toast-title');
    expect(title.textContent).toBeTruthy();
  });

  it('handles JavaScript Error objects', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show JS Error'));

    const toast = screen.getByTestId('toast');
    expect(toast).toBeInTheDocument();
    expect(toast).toHaveAttribute('data-variant', 'destructive');
    expect(screen.getByTestId('toast-title')).toHaveTextContent('Error');
    expect(screen.getByTestId('toast-description')).toHaveTextContent('JS Error');
  });

  it('handles AppError objects with recovery actions', () => {
    const testError = generateAppError();
    const TestAppErrorComponent = () => {
      const { showErrorToast } = useToast();
      return (
        <button onClick={() => showErrorToast(testError)}>
          Show App Error
        </button>
      );
    };

    render(
      <ToastContextProvider>
        <TestAppErrorComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show App Error'));

    const toast = screen.getByTestId('toast');
    expect(toast).toBeInTheDocument();
    expect(toast).toHaveAttribute('data-variant', 'destructive');
    expect(toast).toHaveAttribute('data-severity', 'error');

    // Should display the user message from the generated error
    expect(screen.getByTestId('toast-title')).toHaveTextContent(testError.userMessage!);
    expect(screen.getByTestId('toast-description')).toHaveTextContent(testError.technicalDetails!);

    // Should show recovery action with the generated label
    expect(screen.getByTestId('toast-action')).toHaveTextContent(testError.recoveryActions![0].label);
  });

  it('calls recovery action when clicked', () => {
    const testError = generateAppError();
    const TestAppErrorComponent = () => {
      const { showErrorToast } = useToast();
      return (
        <button onClick={() => showErrorToast(testError)}>
          Show App Error
        </button>
      );
    };

    render(
      <ToastContextProvider>
        <TestAppErrorComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show App Error'));
    fireEvent.click(screen.getByTestId('toast-action'));

    expect(testError.recoveryActions![0].action).toHaveBeenCalled();
  });

  it('auto-removes toasts after duration', async () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Toast'));
    expect(screen.getByTestId('toast')).toBeInTheDocument();

    // Fast-forward time by 5 seconds (default duration)
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    await waitFor(() => {
      expect(screen.queryByTestId('toast')).not.toBeInTheDocument();
    });
  });

  it('uses custom duration for different toast types', async () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    // Success toast has 3 second duration
    fireEvent.click(screen.getByText('Show Success'));
    expect(screen.getByTestId('toast')).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    await waitFor(() => {
      expect(screen.queryByTestId('toast')).not.toBeInTheDocument();
    });
  });

  it('error toasts have 8 second duration', async () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Error'));
    expect(screen.getByTestId('toast')).toBeInTheDocument();

    // Should still be there after 5 seconds
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByTestId('toast')).toBeInTheDocument();

    // Should be gone after 8 seconds
    act(() => {
      vi.advanceTimersByTime(3000);
    });

    await waitFor(() => {
      expect(screen.queryByTestId('toast')).not.toBeInTheDocument();
    });
  });

  it('allows manual dismissal of toasts', async () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Toast'));
    expect(screen.getByTestId('toast')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('toast'));

    await waitFor(() => {
      expect(screen.queryByTestId('toast')).not.toBeInTheDocument();
    });
  });

  it('handles multiple toasts simultaneously', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Toast'));
    fireEvent.click(screen.getByText('Show Error'));
    fireEvent.click(screen.getByText('Show Success'));

    const toasts = screen.getAllByTestId('toast');
    expect(toasts).toHaveLength(3);
  });

  it('sets up global window.showToast function', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    expect(window.showToast).toBeDefined();
    expect(typeof window.showToast).toBe('function');

    // Test global function with dynamic content
    const content = generateToastContent();
    act(() => {
      window.showToast({
        title: content.title,
        message: content.description,
        type: 'success'
      });
    });

    expect(screen.getByTestId('toast')).toBeInTheDocument();
    expect(screen.getByTestId('toast-title')).toHaveTextContent(content.title);
    expect(screen.getByTestId('toast-description')).toHaveTextContent(content.description);

    const toast = screen.getByTestId('toast');
    expect(toast).toHaveAttribute('data-variant', 'success');
  });

  it('cleans up global function on unmount', () => {
    const { unmount } = render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    expect(window.showToast).toBeDefined();

    unmount();

    expect(window.showToast).toBeUndefined();
  });

  it('handles toast with no description', () => {
    const TestNoDescriptionComponent = () => {
      const { showToast } = useToast();
      return (
        <button onClick={() => showToast({ title: 'Title Only' })}>
          Show Title Only
        </button>
      );
    };

    render(
      <ToastContextProvider>
        <TestNoDescriptionComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Title Only'));

    expect(screen.getByTestId('toast-title')).toHaveTextContent('Title Only');
    expect(screen.queryByTestId('toast-description')).not.toBeInTheDocument();
  });

  it('handles custom toast options', () => {
    const TestCustomToastComponent = () => {
      const { showToast } = useToast();
      return (
        <button onClick={() => showToast({
          title: 'Custom Toast',
          description: 'Custom description',
          variant: 'warning',
          severity: ErrorSeverity.WARNING,
          duration: 10000
        })}>
          Show Custom Toast
        </button>
      );
    };

    render(
      <ToastContextProvider>
        <TestCustomToastComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Custom Toast'));

    const toast = screen.getByTestId('toast');
    expect(toast).toHaveAttribute('data-variant', 'warning');
    expect(toast).toHaveAttribute('data-severity', 'warning');
  });

  it('handles AppError without recovery actions', () => {
    const errorWithoutActions: AppError = {
      ...generateAppError(),
      recoveryActions: undefined
    };

    const TestNoActionsComponent = () => {
      const { showErrorToast } = useToast();
      return (
        <button onClick={() => showErrorToast(errorWithoutActions)}>
          Show Error No Actions
        </button>
      );
    };

    render(
      <ToastContextProvider>
        <TestNoActionsComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Error No Actions'));

    expect(screen.getByTestId('toast')).toBeInTheDocument();
    expect(screen.queryByTestId('toast-action')).not.toBeInTheDocument();
  });

  it('handles AppError with fallback message', () => {
    const baseError = generateAppError();
    const errorWithoutUserMessage: AppError = {
      ...baseError,
      userMessage: undefined
    };

    const TestFallbackComponent = () => {
      const { showErrorToast } = useToast();
      return (
        <button onClick={() => showErrorToast(errorWithoutUserMessage)}>
          Show Error Fallback
        </button>
      );
    };

    render(
      <ToastContextProvider>
        <TestFallbackComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Error Fallback'));

    // Should use the error message as fallback when userMessage is undefined
    expect(screen.getByTestId('toast-title')).toHaveTextContent(baseError.message);
  });

  it('generates unique IDs for toasts', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    fireEvent.click(screen.getByText('Show Toast'));
    fireEvent.click(screen.getByText('Show Error'));

    const toasts = screen.getAllByTestId('toast');
    expect(toasts).toHaveLength(2);
    // Each toast should be a separate element
    expect(toasts[0]).not.toBe(toasts[1]);
  });

  it('handles global toast with different types', () => {
    render(
      <ToastContextProvider>
        <TestComponent />
      </ToastContextProvider>
    );

    const testCases = [
      { type: 'success', expectedVariant: 'success' },
      { type: 'error', expectedVariant: 'destructive' },
      { type: 'info', expectedVariant: 'info' },
      { type: 'warning', expectedVariant: 'warning' },
      { type: 'unknown', expectedVariant: 'info' } // fallback
    ];

    testCases.forEach(({ type, expectedVariant }, index) => {
      const content = generateToastContent();
      act(() => {
        window.showToast({
          title: `${content.title} (${type})`,
          message: content.description,
          type
        });
      });

      const toasts = screen.getAllByTestId('toast');
      const currentToast = toasts[index];
      expect(currentToast).toHaveAttribute('data-variant', expectedVariant);
    });
  });
});
