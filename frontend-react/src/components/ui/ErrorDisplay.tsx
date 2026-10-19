import React from 'react';

export type ErrorSeverity = 'error' | 'warning' | 'info';
export type ErrorSize = 'sm' | 'md' | 'lg';

export interface ErrorDisplayProps {
  error?: Error | string | null;
  title?: string;
  severity?: ErrorSeverity;
  size?: ErrorSize;
  className?: string;
  showIcon?: boolean;
  dismissible?: boolean;
  onDismiss?: () => void;
  children?: React.ReactNode;
}

const severityClasses = {
  error: {
    container: 'border-red-200 bg-red-50 text-red-800',
    icon: 'text-red-400',
    title: 'text-red-800',
  },
  warning: {
    container: 'border-yellow-200 bg-yellow-50 text-yellow-800',
    icon: 'text-yellow-400',
    title: 'text-yellow-800',
  },
  info: {
    container: 'border-blue-200 bg-blue-50 text-blue-800',
    icon: 'text-blue-400',
    title: 'text-blue-800',
  },
};

const sizeClasses = {
  sm: {
    container: 'text-sm p-3',
    icon: 'h-4 w-4',
    title: 'text-sm font-medium',
  },
  md: {
    container: 'text-base p-4',
    icon: 'h-5 w-5',
    title: 'text-base font-medium',
  },
  lg: {
    container: 'text-lg p-6',
    icon: 'h-6 w-6',
    title: 'text-lg font-medium',
  },
};

const ErrorIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 20 20">
    <path
      fillRule="evenodd"
      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
      clipRule="evenodd"
    />
  </svg>
);

const WarningIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 20 20">
    <path
      fillRule="evenodd"
      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
      clipRule="evenodd"
    />
  </svg>
);

const InfoIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 20 20">
    <path
      fillRule="evenodd"
      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
      clipRule="evenodd"
    />
  </svg>
);

const XIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

/**
 * Reusable error display component with consistent styling and behavior
 */
export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  error,
  title,
  severity = 'error',
  size = 'md',
  className = '',
  showIcon = true,
  dismissible = false,
  onDismiss,
  children,
}) => {
  // Don't render if no error and no children
  if (!error && !children) return null;

  const errorMessage = error instanceof Error ? error.message : error;
  const severityStyles = severityClasses[severity];
  const sizeStyles = sizeClasses[size];

  const IconComponent = severity === 'error' ? ErrorIcon
    : severity === 'warning' ? WarningIcon
    : InfoIcon;

  const containerClasses = [
    'border rounded-md',
    severityStyles.container,
    sizeStyles.container,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={containerClasses}>
      <div className="flex items-start">
        {showIcon && (
          <div className="flex-shrink-0 mr-3">
            <IconComponent className={`${sizeStyles.icon} ${severityStyles.icon}`} />
          </div>
        )}

        <div className="flex-1">
          {title && (
            <h3 className={`${sizeStyles.title} ${severityStyles.title} mb-1`}>
              {title}
            </h3>
          )}

          {errorMessage && (
            <div className="mb-0">
              {errorMessage}
            </div>
          )}

          {children && (
            <div className={errorMessage ? 'mt-2' : ''}>
              {children}
            </div>
          )}
        </div>

        {dismissible && onDismiss && (
          <div className="flex-shrink-0 ml-3">
            <button
              type="button"
              className={`inline-flex rounded-md p-1.5 focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                severity === 'error' ? 'hover:bg-red-100 focus:ring-red-600' :
                severity === 'warning' ? 'hover:bg-yellow-100 focus:ring-yellow-600' :
                'hover:bg-blue-100 focus:ring-blue-600'
              }`}
              onClick={onDismiss}
            >
              <span className="sr-only">Dismiss</span>
              <XIcon className={`h-4 w-4 ${severityStyles.icon}`} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

/**
 * Inline error display for form fields and small spaces
 */
export const InlineError: React.FC<{
  error?: Error | string | null;
  className?: string;
}> = ({ error, className = '' }) => {
  if (!error) return null;

  const errorMessage = error instanceof Error ? error.message : error;

  return (
    <div className={`text-red-600 text-sm mt-1 ${className}`}>
      {errorMessage}
    </div>
  );
};

/**
 * Error boundary fallback component
 */
export const ErrorFallback: React.FC<{
  error?: Error;
  resetError?: () => void;
}> = ({ error, resetError }) => {
  return (
    <ErrorDisplay
      error={error}
      title="Something went wrong"
      severity="error"
      size="lg"
      className="m-4"
    >
      <div className="mt-4">
        <button
          type="button"
          onClick={resetError}
          className="bg-red-600 text-white px-4 py-2 rounded-md text-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500"
        >
          Try again
        </button>
      </div>

      {process.env.NODE_ENV === 'development' && error && (
        <details className="mt-4">
          <summary className="text-sm font-medium cursor-pointer">
            Error details (development only)
          </summary>
          <pre className="mt-2 text-xs bg-red-100 p-2 rounded overflow-auto">
            {error.stack}
          </pre>
        </details>
      )}
    </ErrorDisplay>
  );
};

export default ErrorDisplay;
