import { useCallback, useState } from 'react';
import { useToast } from '@/contexts/ToastContext';
import { errorService } from '@/services/errorService';
import { AppError, ErrorSeverity, ErrorCategory } from '@/types/errors';

interface UseErrorOptions {
  showToast?: boolean;
  fallbackMessage?: string;
  context?: Record<string, unknown>;
  onError?: (error: AppError) => void;
}

interface UseErrorReturn {
  error: AppError | null;
  isError: boolean;
  clearError: () => void;
  handleError: (error: unknown, options?: UseErrorOptions) => AppError;
  setError: (error: AppError | null) => void;
}

/**
 * Unified error handling hook that integrates with the error service and toast system
 */
export function useError(defaultOptions?: UseErrorOptions): UseErrorReturn {
  const [error, setError] = useState<AppError | null>(null);
  const { showErrorToast, showWarningToast } = useToast();

  const handleError = useCallback((error: unknown, options?: UseErrorOptions) => {
    const opts = { showToast: true, ...defaultOptions, ...options };

    // Normalize error using error service
    const normalizedError = errorService.handleError(error, opts.context);

    // Update local error state
    setError(normalizedError);

    // Show toast if enabled
    if (opts.showToast) {
      if (normalizedError.severity === ErrorSeverity.WARNING) {
        showWarningToast(
          normalizedError.userMessage || opts.fallbackMessage || 'Warning',
          normalizedError.message
        );
      } else {
        showErrorToast(normalizedError);
      }
    }

    // Call custom error handler if provided
    if (opts.onError) {
      opts.onError(normalizedError);
    }

    return normalizedError;
  }, [showErrorToast, showWarningToast, defaultOptions]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    error,
    isError: error !== null,
    clearError,
    handleError,
    setError,
  };
}

/**
 * Hook for handling API errors with TanStack Query
 */
export function useApiError() {
  const { handleError } = useError();

  const handleApiError = useCallback((error: unknown, operation: string) => {
    return handleError(error, {
      context: { operation },
      showToast: true,
    });
  }, [handleError]);

  return { handleApiError };
}

/**
 * Hook for handling form validation errors
 */
export function useFormError(formName?: string) {
  const { error, handleError, clearError, isError } = useError({
    showToast: false, // Usually handle inline for forms
  });

  const handleValidationError = useCallback((fields: Record<string, string[]>) => {
    return handleError({
      code: 'VALIDATION_FORMAT',
      message: 'Please fix the errors below',
      severity: ErrorSeverity.WARNING,
      category: ErrorCategory.VALIDATION,
      timestamp: new Date(),
      fields,
      formName,
      userMessage: 'Please check your input',
    });
  }, [handleError, formName]);

  const getFieldErrors = useCallback((fieldName: string): string[] => {
    if (!error || !('fields' in error)) return [];
    return error.fields?.[fieldName] || [];
  }, [error]);

  const hasFieldError = useCallback((fieldName: string): boolean => {
    return getFieldErrors(fieldName).length > 0;
  }, [getFieldErrors]);

  return {
    error,
    isError,
    clearError,
    handleValidationError,
    getFieldErrors,
    hasFieldError,
  };
}

/**
 * Hook for handling async operations with error handling
 */
export function useAsyncError<T = unknown>() {
  const [isLoading, setIsLoading] = useState(false);
  const [data, setData] = useState<T | null>(null);
  const { error, handleError, clearError } = useError();

  const execute = useCallback(async (
    asyncFn: () => Promise<T>,
    options?: UseErrorOptions
  ) => {
    setIsLoading(true);
    clearError();
    setData(null);

    try {
      const result = await asyncFn();
      setData(result);
      return result;
    } catch (err) {
      handleError(err, options);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [handleError, clearError]);

  return {
    execute,
    isLoading,
    data,
    error,
    clearError,
  };
}
