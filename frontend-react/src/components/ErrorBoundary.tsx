import React from 'react';
import { errorService } from '@/services/errorService';
import { createBoundaryError } from '@/types/errors';

interface ErrorBoundaryProps {
  fallback?: React.ReactNode;
  children: React.ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  resetOnPropsChange?: boolean;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: React.ErrorInfo;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Update state with error info for more detailed reporting
    this.setState({ errorInfo });

    // Create a boundary error and handle it through the error service
    const boundaryError = createBoundaryError(error, {
      componentStack: errorInfo.componentStack || '',
      errorBoundary: 'ErrorBoundary',
      timestamp: new Date(),
    });

    // Handle through error service for centralized logging
    errorService.handleError(boundaryError);

    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  // Reset error state when props change if resetOnPropsChange is true
  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    // Reset the error state if resetOnPropsChange is true and children have changed
    if (
      this.props.resetOnPropsChange &&
      this.state.hasError &&
      // Simple check, might need deeper comparison for complex children
      prevProps.children !== this.props.children
    ) {
      this.resetErrorState();
    }
  }

  resetErrorState = () => {
    this.setState({ hasError: false });
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Render default fallback UI
      return (
        <div className="p-4 border border-red-500 bg-red-50 rounded-md shadow-md my-4 text-gray-700 dark:border-red-500 dark:bg-red-900/20 dark:text-gray-300">
          <h2 className="text-red-700 text-lg font-semibold mb-2 dark:text-red-400">Something went wrong</h2>
          <p className="mb-2">{this.state.error?.message || 'An unexpected error occurred'}</p>
          {this.state.error?.stack && (
            <details className="mt-2">
              <summary className="cursor-pointer text-sm text-gray-600 dark:text-gray-400 list-none [&::-webkit-details-marker]:hidden before:content-['▶_'] before:text-[0.7em] before:mr-1 open:before:content-['▼_']">View technical details</summary>
              <pre className="mt-2 text-xs overflow-auto p-2 bg-gray-100 dark:bg-gray-700 dark:text-gray-300 rounded whitespace-pre-wrap break-all max-h-[200px]">
                {this.state.error.stack}
              </pre>
            </details>
          )}
          <div className="mt-4">
            <button
              className="px-3 py-1 border border-gray-300 dark:border-gray-600 rounded cursor-pointer bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
              onClick={this.resetErrorState}
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export { ErrorBoundary };
