import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useError, useApiError, useFormError, useAsyncError } from './useError';
import { AppError, ErrorSeverity, ErrorCategory } from '@/types/errors';

// Mock the ToastContext
const mockShowErrorToast = vi.fn();
const mockShowWarningToast = vi.fn();

vi.mock('@/contexts/ToastContext', () => ({
  useToast: () => ({
    showErrorToast: mockShowErrorToast,
    showWarningToast: mockShowWarningToast
  })
}));

// Mock the errorService
vi.mock('@/services/errorService', () => ({
  errorService: {
    handleError: vi.fn()
  }
}));

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
    technicalDetails: `Technical details: ${Math.random().toString(36).substr(2, 9)}`
  };
};

describe('useError', () => {
  let mockHandleError: any;
  let testError: AppError;

  beforeEach(async () => {
    vi.clearAllMocks();

    // Generate fresh error data
    testError = generateAppError();

    // Get the mocked errorService
    const { errorService } = await import('@/services/errorService');
    mockHandleError = errorService.handleError;
    mockHandleError.mockReturnValue(testError);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('initializes with no error state', () => {
    const { result } = renderHook(() => useError());

    expect(result.current.error).toBeNull();
    expect(result.current.isError).toBe(false);
  });

  it('handles errors and updates state', () => {
    const { result } = renderHook(() => useError());

    const inputError = new Error('Test error');

    act(() => {
      result.current.handleError(inputError);
    });

    expect(mockHandleError).toHaveBeenCalledWith(inputError, undefined);
    expect(result.current.error).toEqual(testError); // The errorService returns testError
    expect(result.current.isError).toBe(true);
  });

  it('shows toast by default when handling errors', () => {
    const { result } = renderHook(() => useError());

    act(() => {
      result.current.handleError(new Error('Test error'));
    });

    expect(mockShowErrorToast).toHaveBeenCalledWith(testError); // Uses the generated error from beforeEach
  });

  it('shows warning toast for warning severity errors', () => {
    const warningError: AppError = {
      ...generateAppError(ErrorSeverity.WARNING),
      severity: ErrorSeverity.WARNING,
      userMessage: 'Warning message'
    };

    mockHandleError.mockReturnValue(warningError);

    const { result } = renderHook(() => useError());

    act(() => {
      result.current.handleError(new Error('Warning error'));
    });

    expect(mockShowWarningToast).toHaveBeenCalledWith('Warning message', warningError.message);
  });

  it('uses fallback message when no user message is available', () => {
    const errorWithoutUserMessage: AppError = {
      ...generateAppError(ErrorSeverity.WARNING),
      severity: ErrorSeverity.WARNING,
      userMessage: undefined
    };

    mockHandleError.mockReturnValue(errorWithoutUserMessage);

    const { result } = renderHook(() => useError({
      fallbackMessage: 'Fallback message'
    }));

    act(() => {
      result.current.handleError(new Error('Test error'));
    });

    expect(mockShowWarningToast).toHaveBeenCalledWith('Fallback message', errorWithoutUserMessage.message);
  });

  it('respects showToast option', () => {
    const { result } = renderHook(() => useError());

    act(() => {
      result.current.handleError(new Error('Test error'), { showToast: false });
    });

    expect(mockShowErrorToast).not.toHaveBeenCalled();
    expect(result.current.error).toEqual(testError); // Uses the generated error from beforeEach
  });

  it('calls custom onError callback', () => {
    const onErrorCallback = vi.fn();
    const { result } = renderHook(() => useError());

    act(() => {
      result.current.handleError(new Error('Test error'), { onError: onErrorCallback });
    });

    expect(onErrorCallback).toHaveBeenCalledWith(testError); // Uses the generated error from beforeEach
  });

  it('passes context to error service', () => {
    const { result } = renderHook(() => useError());
    const context = { operation: 'test-operation', userId: 123 };

    act(() => {
      result.current.handleError(new Error('Test error'), { context });
    });

    expect(mockHandleError).toHaveBeenCalledWith(expect.any(Error), context);
  });

  it('merges default options with provided options', () => {
    const defaultOptions = { showToast: false, fallbackMessage: 'Default fallback' };
    const { result } = renderHook(() => useError(defaultOptions));

    act(() => {
      result.current.handleError(new Error('Test error'), { context: { test: true } });
    });

    expect(mockHandleError).toHaveBeenCalledWith(expect.any(Error), { test: true });
    expect(mockShowErrorToast).not.toHaveBeenCalled(); // Should use default showToast: false
  });

  it('clears error state', () => {
    const { result } = renderHook(() => useError());

    // Set an error first
    act(() => {
      result.current.handleError(new Error('Test error'));
    });

    expect(result.current.isError).toBe(true);

    // Clear the error
    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.isError).toBe(false);
  });

  it('sets error directly', () => {
    const { result } = renderHook(() => useError());

    const directError = generateAppError();
    act(() => {
      result.current.setError(directError);
    });

    expect(result.current.error).toEqual(directError);
    expect(result.current.isError).toBe(true);

    // Clear using setError
    act(() => {
      result.current.setError(null);
    });

    expect(result.current.error).toBeNull();
    expect(result.current.isError).toBe(false);
  });

  it('returns the normalized error from handleError', () => {
    const { result } = renderHook(() => useError());
    let returnedError: AppError;

    act(() => {
      returnedError = result.current.handleError(new Error('Test error'));
    });

    expect(returnedError!).toEqual(testError); // Uses the generated error from beforeEach
  });
});

describe('useApiError', () => {
  let mockHandleError: any;
  let testError: AppError;

  beforeEach(async () => {
    vi.clearAllMocks();
    testError = generateAppError();
    const { errorService } = await import('@/services/errorService');
    mockHandleError = errorService.handleError;
    mockHandleError.mockReturnValue(testError);
  });

  it('handles API errors with operation context', () => {
    const { result } = renderHook(() => useApiError());

    act(() => {
      result.current.handleApiError(new Error('API error'), 'fetchProspects');
    });

    expect(mockHandleError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({
        operation: 'fetchProspects'
      })
    );
  });

  it('returns the normalized error', () => {
    const { result } = renderHook(() => useApiError());
    let returnedError: AppError;

    act(() => {
      returnedError = result.current.handleApiError(new Error('API error'), 'testOperation');
    });

    expect(returnedError!).toEqual(testError);
  });
});

describe('useFormError', () => {
  let mockHandleError: any;
  let testError: AppError;

  beforeEach(async () => {
    vi.clearAllMocks();
    testError = generateAppError();
    const { errorService } = await import('@/services/errorService');
    mockHandleError = errorService.handleError;
    mockHandleError.mockReturnValue(testError);
  });

  it('initializes with showToast disabled by default', () => {
    const { result } = renderHook(() => useFormError());

    act(() => {
      result.current.handleValidationError({ email: ['Invalid email'] });
    });

    // Should not show toast for form errors by default
    expect(mockShowErrorToast).not.toHaveBeenCalled();
  });

  it('handles validation errors with field information', () => {
    const { result } = renderHook(() => useFormError('loginForm'));
    const fields = {
      email: ['Invalid email format'],
      password: ['Password too short', 'Password must contain numbers']
    };

    act(() => {
      result.current.handleValidationError(fields);
    });

    expect(mockHandleError).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'VALIDATION_FORMAT',
        message: 'Please fix the errors below',
        severity: ErrorSeverity.WARNING,
        category: ErrorCategory.VALIDATION,
        fields,
        formName: 'loginForm',
        userMessage: 'Please check your input'
      }),
      undefined
    );
  });

  it('gets field errors correctly', () => {
    const formErrorWithFields: AppError = {
      ...generateAppError(),
      fields: {
        email: ['Invalid email format'],
        password: ['Password too short']
      }
    };

    mockHandleError.mockReturnValue(formErrorWithFields);

    const { result } = renderHook(() => useFormError());

    // Set an error with fields
    act(() => {
      result.current.handleValidationError({
        email: ['Invalid email format'],
        password: ['Password too short']
      });
    });

    expect(result.current.getFieldErrors('email')).toEqual(['Invalid email format']);
    expect(result.current.getFieldErrors('password')).toEqual(['Password too short']);
    expect(result.current.getFieldErrors('nonexistent')).toEqual([]);
  });

  it('checks if field has errors', () => {
    const formErrorWithFields: AppError = {
      ...generateAppError(),
      fields: {
        email: ['Invalid email format'],
        username: []
      }
    };

    mockHandleError.mockReturnValue(formErrorWithFields);

    const { result } = renderHook(() => useFormError());

    act(() => {
      result.current.handleValidationError({
        email: ['Invalid email format'],
        username: []
      });
    });

    expect(result.current.hasFieldError('email')).toBe(true);
    expect(result.current.hasFieldError('username')).toBe(false);
    expect(result.current.hasFieldError('nonexistent')).toBe(false);
  });

  it('handles errors without fields property', () => {
    const _regularError = new Error('Regular error');
    mockHandleError.mockReturnValue(testError); // testError doesn't have fields property

    const { result } = renderHook(() => useFormError());

    // Set a regular error without fields by handling a regular error
    act(() => {
      result.current.handleValidationError({});
    });

    expect(result.current.getFieldErrors('email')).toEqual([]);
    expect(result.current.hasFieldError('email')).toBe(false);
  });
});

describe('useAsyncError', () => {
  let mockHandleError: any;
  let testError: AppError;

  beforeEach(async () => {
    vi.clearAllMocks();
    testError = generateAppError();
    const { errorService } = await import('@/services/errorService');
    mockHandleError = errorService.handleError;
    mockHandleError.mockReturnValue(testError);
  });

  it('initializes with correct default state', () => {
    const { result } = renderHook(() => useAsyncError());

    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('handles successful async operations', async () => {
    const { result } = renderHook(() => useAsyncError<string>());
    const mockAsyncFn = vi.fn().mockResolvedValue('success data');

    let returnedData: string;

    await act(async () => {
      returnedData = await result.current.execute(mockAsyncFn);
    });

    expect(mockAsyncFn).toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBe('success data');
    expect(result.current.error).toBeNull();
    expect(returnedData!).toBe('success data');
  });

  it('handles async operation errors', async () => {
    const { result } = renderHook(() => useAsyncError());
    const inputError = new Error('Async operation failed');
    const mockAsyncFn = vi.fn().mockRejectedValue(inputError);

    let thrownError: Error | undefined;

    await act(async () => {
      try {
        await result.current.execute(mockAsyncFn);
      } catch (error) {
        thrownError = error as Error;
      }
    });

    expect(mockAsyncFn).toHaveBeenCalled();
    expect(mockHandleError).toHaveBeenCalledWith(inputError, undefined);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toEqual(testError); // mockHandleError returns testError
    expect(thrownError).toBe(testError); // The thrown error is also testError
  });

  it('sets loading state during execution', async () => {
    const { result } = renderHook(() => useAsyncError());
    let resolvePromise: (value: string) => void;
    const mockAsyncFn = vi.fn().mockImplementation(() => new Promise<string>(resolve => {
      resolvePromise = resolve;
    }));

    // Start execution
    act(() => {
      result.current.execute(mockAsyncFn);
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeNull();

    // Resolve the promise
    await act(async () => {
      resolvePromise!('completed');
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBe('completed');
  });

  it('clears previous data and errors when starting new execution', async () => {
    const { result } = renderHook(() => useAsyncError());

    // First, set some initial state by causing an error
    const errorAsyncFn = vi.fn().mockRejectedValue(new Error('Initial error'));

    await act(async () => {
      try {
        await result.current.execute(errorAsyncFn);
      } catch {
        // Expected to throw
      }
    });

    expect(result.current.error).toEqual(testError);

    // Execute a successful operation
    const mockAsyncFn = vi.fn().mockResolvedValue('new data');

    await act(async () => {
      await result.current.execute(mockAsyncFn);
    });

    expect(result.current.error).toBeNull(); // Error should be cleared
    expect(result.current.data).toBe('new data');
  });

  it('passes options to error handler', async () => {
    const { result } = renderHook(() => useAsyncError());
    const testError = new Error('Async error');
    const mockAsyncFn = vi.fn().mockRejectedValue(testError);
    const options = { showToast: false, context: { operation: 'test' } };

    await act(async () => {
      try {
        await result.current.execute(mockAsyncFn, options);
      } catch {
        // Expected to throw
      }
    });

    expect(mockHandleError).toHaveBeenCalledWith(testError, expect.objectContaining({
      operation: 'test'
    }));
  });

  it('maintains stable function references', () => {
    const { result, rerender } = renderHook(() => useAsyncError());

    const initialExecute = result.current.execute;
    const initialClearError = result.current.clearError;

    rerender();

    expect(result.current.execute).toBe(initialExecute);
    expect(result.current.clearError).toBe(initialClearError);
  });

  it('clears error manually', async () => {
    const { result } = renderHook(() => useAsyncError());

    // Set an error by executing a failing function
    const errorAsyncFn = vi.fn().mockRejectedValue(new Error('Test error'));

    await act(async () => {
      try {
        await result.current.execute(errorAsyncFn);
      } catch {
        // Expected to throw
      }
    });

    expect(result.current.error).toEqual(testError);

    // Clear it
    act(() => {
      result.current.clearError();
    });

    expect(result.current.error).toBeNull();
  });

  it('handles multiple sequential executions', async () => {
    const { result } = renderHook(() => useAsyncError<number>());

    // First execution
    const firstAsyncFn = vi.fn().mockResolvedValue(1);

    await act(async () => {
      await result.current.execute(firstAsyncFn);
    });

    expect(result.current.data).toBe(1);

    // Second execution (should overwrite first)
    const secondAsyncFn = vi.fn().mockResolvedValue(2);

    await act(async () => {
      await result.current.execute(secondAsyncFn);
    });

    // The second operation should overwrite the first
    expect(result.current.data).toBe(2);
    expect(result.current.isLoading).toBe(false);
  });
});
