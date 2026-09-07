/**
 * Comprehensive error type system for standardized error handling
 */

// Error severity levels
export enum ErrorSeverity {
  CRITICAL = 'critical', // System failure, requires immediate attention
  ERROR = 'error',       // Operation failed, user action blocked
  WARNING = 'warning',   // Operation completed with issues
  INFO = 'info'          // Informational, no action required
}

// Error categories for different error types
export enum ErrorCategory {
  API = 'api',
  VALIDATION = 'validation',
  NETWORK = 'network',
  BUSINESS = 'business',
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  SYSTEM = 'system',
  USER_INPUT = 'user_input',
  USER = 'user',
  EXTERNAL = 'external',
  UNKNOWN = 'unknown'
}

// Base error interface
export interface BaseError {
  code: string;
  message: string;
  severity: ErrorSeverity;
  category: ErrorCategory;
  timestamp: Date;
  context?: Record<string, unknown>;
  userMessage?: string; // User-friendly message
  technicalDetails?: string; // Technical details for debugging
  recoveryActions?: ErrorRecoveryAction[];
}

// Recovery action that can be taken for an error
export interface ErrorRecoveryAction {
  label: string;
  action: () => void | Promise<void>;
  primary?: boolean;
}

// API Error with HTTP-specific details
export interface ApiErrorDetails extends BaseError {
  category: ErrorCategory.API;
  status: number;
  statusText: string;
  endpoint?: string;
  method?: string;
  requestData?: unknown;
  responseData?: unknown;
}

// Validation Error for form/input validation
export interface ValidationErrorDetails extends BaseError {
  category: ErrorCategory.VALIDATION;
  fields?: Record<string, string[]>; // field name -> error messages
  formName?: string;
}

// Network Error for connectivity issues
export interface NetworkErrorDetails extends BaseError {
  category: ErrorCategory.NETWORK;
  retryAttempt?: number;
  maxRetries?: number;
  offline?: boolean;
}

// Business Logic Error
export interface BusinessErrorDetails extends BaseError {
  category: ErrorCategory.BUSINESS;
  businessRule?: string;
  entityType?: string;
  entityId?: string;
}

// Authentication/Authorization Errors
export interface AuthErrorDetails extends BaseError {
  category: ErrorCategory.AUTHENTICATION | ErrorCategory.AUTHORIZATION;
  requiredRole?: string;
  requiredPermission?: string;
  redirectUrl?: string;
}

// Union type for all error types
export type AppError =
  | ApiErrorDetails
  | ValidationErrorDetails
  | NetworkErrorDetails
  | BusinessErrorDetails
  | AuthErrorDetails
  | BaseError;

// Error code constants
export const ERROR_CODES = {
  // API Errors
  API_TIMEOUT: 'API_TIMEOUT',
  API_SERVER_ERROR: 'API_SERVER_ERROR',
  API_CLIENT_ERROR: 'API_CLIENT_ERROR',
  API_NETWORK_ERROR: 'API_NETWORK_ERROR',
  API_PARSE_ERROR: 'API_PARSE_ERROR',

  // Validation Errors
  VALIDATION_REQUIRED: 'VALIDATION_REQUIRED',
  VALIDATION_FORMAT: 'VALIDATION_FORMAT',
  VALIDATION_RANGE: 'VALIDATION_RANGE',
  VALIDATION_UNIQUE: 'VALIDATION_UNIQUE',

  // Business Errors
  BUSINESS_RULE_VIOLATION: 'BUSINESS_RULE_VIOLATION',
  DUPLICATE_ENTITY: 'DUPLICATE_ENTITY',
  ENTITY_NOT_FOUND: 'ENTITY_NOT_FOUND',
  OPERATION_NOT_ALLOWED: 'OPERATION_NOT_ALLOWED',

  // Auth Errors
  AUTH_UNAUTHORIZED: 'AUTH_UNAUTHORIZED',
  AUTH_FORBIDDEN: 'AUTH_FORBIDDEN',
  AUTH_SESSION_EXPIRED: 'AUTH_SESSION_EXPIRED',
  AUTH_INVALID_CREDENTIALS: 'AUTH_INVALID_CREDENTIALS',

  // System Errors
  SYSTEM_UNAVAILABLE: 'SYSTEM_UNAVAILABLE',
  SYSTEM_MAINTENANCE: 'SYSTEM_MAINTENANCE',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR'
} as const;

// Type guard functions
export function isApiError(error: AppError): error is ApiErrorDetails {
  return error.category === ErrorCategory.API;
}

export function isValidationError(error: AppError): error is ValidationErrorDetails {
  return error.category === ErrorCategory.VALIDATION;
}

export function isNetworkError(error: AppError): error is NetworkErrorDetails {
  return error.category === ErrorCategory.NETWORK;
}

export function isBusinessError(error: AppError): error is BusinessErrorDetails {
  return error.category === ErrorCategory.BUSINESS;
}

export function isAuthError(error: AppError): error is AuthErrorDetails {
  return error.category === ErrorCategory.AUTHENTICATION ||
         error.category === ErrorCategory.AUTHORIZATION;
}

// Error factory functions
export function createApiError(
  status: number,
  message: string,
  details?: Partial<ApiErrorDetails>
): ApiErrorDetails {
  return {
    code: details?.code || ERROR_CODES.API_SERVER_ERROR,
    message,
    severity: status >= 500 ? ErrorSeverity.ERROR : ErrorSeverity.WARNING,
    category: ErrorCategory.API,
    timestamp: new Date(),
    status,
    statusText: details?.statusText || 'API Error',
    userMessage: details?.userMessage || getDefaultUserMessage(ErrorCategory.API, status),
    ...details
  };
}

export function createValidationError(
  fields: Record<string, string[]>,
  details?: Partial<ValidationErrorDetails>
): ValidationErrorDetails {
  return {
    code: details?.code || ERROR_CODES.VALIDATION_FORMAT,
    message: details?.message || 'Validation failed',
    severity: ErrorSeverity.WARNING,
    category: ErrorCategory.VALIDATION,
    timestamp: new Date(),
    fields,
    userMessage: details?.userMessage || 'Please check your input and try again.',
    ...details
  };
}

export function createNetworkError(
  message: string,
  details?: Partial<NetworkErrorDetails>
): NetworkErrorDetails {
  return {
    code: details?.code || ERROR_CODES.API_NETWORK_ERROR,
    message,
    severity: ErrorSeverity.ERROR,
    category: ErrorCategory.NETWORK,
    timestamp: new Date(),
    userMessage: details?.userMessage || 'Network connection issue. Please check your internet connection.',
    ...details
  };
}

export function createBusinessError(
  message: string,
  details?: Partial<BusinessErrorDetails>
): BusinessErrorDetails {
  return {
    code: details?.code || ERROR_CODES.BUSINESS_RULE_VIOLATION,
    message,
    severity: details?.severity || ErrorSeverity.WARNING,
    category: ErrorCategory.BUSINESS,
    timestamp: new Date(),
    userMessage: details?.userMessage || 'This operation cannot be completed due to business rules.',
    ...details
  };
}

export function createBoundaryError(
  error: Error,
  details?: {
    componentStack?: string;
    errorBoundary?: string;
    context?: Record<string, unknown>;
    userMessage?: string;
    recoveryActions?: ErrorRecoveryAction[];
    timestamp?: Date;
  }
): BaseError {
  return {
    code: 'REACT_ERROR_BOUNDARY',
    message: error.message,
    severity: ErrorSeverity.ERROR,
    category: ErrorCategory.SYSTEM,
    timestamp: details?.timestamp || new Date(),
    context: {
      ...details?.context,
      errorBoundary: details?.errorBoundary,
      componentStack: details?.componentStack,
      stackTrace: error.stack,
    },
    technicalDetails: error.stack,
    userMessage: details?.userMessage || 'An unexpected error occurred. Please refresh the page.',
    recoveryActions: details?.recoveryActions || [
      { label: 'Reload Page', action: () => window.location.reload() },
      { label: 'Try Again', action: () => {} },
    ],
  };
}

// Helper to get default user-friendly messages
function getDefaultUserMessage(category: ErrorCategory, status?: number): string {
  switch (category) {
    case ErrorCategory.API:
      if (status) {
        if (status >= 500) return 'Server error occurred. Please try again later.';
        if (status === 404) return 'The requested resource was not found.';
        if (status === 403) return 'You do not have permission to perform this action.';
        if (status === 401) return 'Please sign in to continue.';
        if (status >= 400) return 'There was a problem with your request.';
      }
      return 'An error occurred while processing your request.';

    case ErrorCategory.NETWORK:
      return 'Network connection issue. Please check your internet connection.';

    case ErrorCategory.VALIDATION:
      return 'Please check your input and try again.';

    case ErrorCategory.AUTHENTICATION:
      return 'Authentication required. Please sign in.';

    case ErrorCategory.AUTHORIZATION:
      return 'You do not have permission to perform this action.';

    case ErrorCategory.BUSINESS:
      return 'This operation cannot be completed due to business rules.';

    case ErrorCategory.SYSTEM:
      return 'A system error occurred. Please try again later.';

    default:
      return 'An unexpected error occurred.';
  }
}
