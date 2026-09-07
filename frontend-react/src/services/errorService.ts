import {
  AppError,
  ErrorSeverity,
  ErrorCategory,
  ERROR_CODES,
  createApiError,
  createValidationError,
  createNetworkError,
  ErrorRecoveryAction,
} from '@/types/errors';

/**
 * Centralized error handling service
 */
export class ErrorService {
  private static instance: ErrorService;
  private errorHandlers: Map<string, (error: AppError) => void> = new Map();
  private globalErrorHandler?: (error: AppError) => void;

  private constructor() {}

  static getInstance(): ErrorService {
    if (!ErrorService.instance) {
      ErrorService.instance = new ErrorService();
    }
    return ErrorService.instance;
  }

  /**
   * Set a global error handler
   */
  setGlobalErrorHandler(handler: (error: AppError) => void) {
    this.globalErrorHandler = handler;
  }

  /**
   * Register an error handler for specific error codes
   */
  registerErrorHandler(code: string, handler: (error: AppError) => void) {
    this.errorHandlers.set(code, handler);
  }

  /**
   * Process and normalize errors into AppError format
   */
  normalizeError(error: unknown): AppError {
    // If it's already an AppError, return it
    if (this.isAppError(error)) {
      return error;
    }

    // Handle ApiError from our API utils (check if it has status property)
    if (error && typeof error === 'object' && 'status' in error && 'message' in error) {
      const apiError = error as { status?: number; statusText?: string; message: string; url?: string };
      return createApiError(apiError.status || 500, apiError.message, {
        code: this.getErrorCodeFromStatus(apiError.status),
        statusText: apiError.statusText,
        technicalDetails: apiError.message,
        context: {
          url: apiError.url,
          timestamp: new Date().toISOString(),
        },
      });
    }

    // Handle native fetch errors
    if (error instanceof TypeError && error.message.includes('fetch')) {
      return createNetworkError(error.message, {
        code: ERROR_CODES.API_NETWORK_ERROR,
        offline: !navigator.onLine,
      });
    }

    // Handle validation errors (assuming they have a fields property)
    if (error && typeof error === 'object' && 'fields' in error) {
      const validationError = error as { fields: Record<string, string[]>; message?: string; formName?: string };
      return createValidationError(
        validationError.fields,
        {
          message: validationError.message || 'Validation failed',
          formName: validationError.formName,
        }
      );
    }

    // Handle generic Error objects
    if (error instanceof Error) {
      return {
        code: ERROR_CODES.UNKNOWN_ERROR,
        message: error.message,
        severity: ErrorSeverity.ERROR,
        category: ErrorCategory.UNKNOWN,
        timestamp: new Date(),
        userMessage: 'An unexpected error occurred',
        technicalDetails: error.stack,
      };
    }

    // Handle string errors
    if (typeof error === 'string') {
      return {
        code: ERROR_CODES.UNKNOWN_ERROR,
        message: error,
        severity: ErrorSeverity.ERROR,
        category: ErrorCategory.UNKNOWN,
        timestamp: new Date(),
        userMessage: error,
      };
    }

    // Fallback for unknown error types
    return {
      code: ERROR_CODES.UNKNOWN_ERROR,
      message: 'An unknown error occurred',
      severity: ErrorSeverity.ERROR,
      category: ErrorCategory.UNKNOWN,
      timestamp: new Date(),
      userMessage: 'An unexpected error occurred',
      technicalDetails: JSON.stringify(error),
    };
  }

  /**
   * Handle an error - normalize it and pass to appropriate handlers
   */
  handleError(error: unknown, context?: Record<string, unknown>): AppError {
    const normalizedError = this.normalizeError(error);

    // Add context if provided
    if (context) {
      normalizedError.context = { ...normalizedError.context, ...context };
    }

    // Log error for debugging
    this.logError(normalizedError);

    // Call specific error handler if registered
    const handler = this.errorHandlers.get(normalizedError.code);
    if (handler) {
      handler(normalizedError);
    }

    // Call global error handler
    if (this.globalErrorHandler) {
      this.globalErrorHandler(normalizedError);
    }

    return normalizedError;
  }

  /**
   * Log error for debugging/monitoring
   */
  private logError(error: AppError) {
    const logData = {
      timestamp: error.timestamp,
      code: error.code,
      category: error.category,
      severity: error.severity,
      message: error.message,
      userMessage: error.userMessage,
      context: error.context,
      technicalDetails: error.technicalDetails,
    };

    // In production, this would send to a logging service
    if (error.severity === ErrorSeverity.CRITICAL || error.severity === ErrorSeverity.ERROR) {
      console.error('[ErrorService]', logData);
    } else {
      console.warn('[ErrorService]', logData);
    }
  }

  /**
   * Get error code from HTTP status
   */
  private getErrorCodeFromStatus(status?: number): string {
    if (!status) return ERROR_CODES.UNKNOWN_ERROR;

    if (status >= 500) return ERROR_CODES.API_SERVER_ERROR;
    if (status === 401) return ERROR_CODES.AUTH_UNAUTHORIZED;
    if (status === 403) return ERROR_CODES.AUTH_FORBIDDEN;
    if (status === 404) return ERROR_CODES.ENTITY_NOT_FOUND;
    if (status === 409) return ERROR_CODES.DUPLICATE_ENTITY;
    if (status >= 400) return ERROR_CODES.API_CLIENT_ERROR;

    return ERROR_CODES.UNKNOWN_ERROR;
  }

  /**
   * Type guard to check if error is AppError
   */
  private isAppError(error: unknown): error is AppError {
    return (
      error !== null &&
      typeof error === 'object' &&
      'code' in error &&
      'message' in error &&
      'severity' in error &&
      'category' in error
    );
  }

  /**
   * Create recovery actions for common errors
   */
  createRecoveryActions(error: AppError): ErrorRecoveryAction[] {
    const actions: ErrorRecoveryAction[] = [];

    switch (error.code) {
      case ERROR_CODES.AUTH_UNAUTHORIZED:
      case ERROR_CODES.AUTH_SESSION_EXPIRED:
        actions.push({
          label: 'Sign In',
          action: () => {
            window.location.href = '/login';
          },
          primary: true,
        });
        break;

      case ERROR_CODES.API_NETWORK_ERROR:
        actions.push({
          label: 'Retry',
          action: () => {
            window.location.reload();
          },
          primary: true,
        });
        break;

      case ERROR_CODES.API_TIMEOUT:
        actions.push({
          label: 'Try Again',
          action: () => {
            // This would be overridden by specific implementations
            window.location.reload();
          },
          primary: true,
        });
        break;
    }

    return actions;
  }

  /**
   * Format error for user display
   */
  formatErrorForDisplay(error: AppError): {
    title: string;
    message: string;
    actions: ErrorRecoveryAction[];
  } {
    return {
      title: error.userMessage || 'Error',
      message: error.technicalDetails || error.message,
      actions: error.recoveryActions || this.createRecoveryActions(error),
    };
  }

  /**
   * Check if error is retryable
   */
  isRetryable(error: AppError): boolean {
    const retryableCodes: string[] = [
      ERROR_CODES.API_TIMEOUT,
      ERROR_CODES.API_NETWORK_ERROR,
      ERROR_CODES.API_SERVER_ERROR,
    ];
    return retryableCodes.includes(error.code);
  }

  /**
   * Get retry delay based on error and attempt number
   */
  getRetryDelay(error: AppError, attempt: number): number {
    // Exponential backoff with jitter
    const baseDelay = 1000; // 1 second
    const maxDelay = 30000; // 30 seconds

    if (error.code === ERROR_CODES.API_SERVER_ERROR) {
      // Longer delays for server errors
      const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
      const jitter = Math.random() * 0.3 * delay; // 30% jitter
      return delay + jitter;
    }

    // Shorter delays for network errors
    const delay = Math.min(baseDelay * attempt, 10000); // Max 10 seconds
    const jitter = Math.random() * 0.2 * delay; // 20% jitter
    return delay + jitter;
  }
}

// Export singleton instance
export const errorService = ErrorService.getInstance();
