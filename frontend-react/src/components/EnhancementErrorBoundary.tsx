import { Component, ReactNode, ErrorInfo } from 'react';
import { Button } from '@/components/ui/button';
import { ExclamationTriangleIcon, ReloadIcon } from '@radix-ui/react-icons';
import { errorService } from '@/services/errorService';
import { createBoundaryError, createNetworkError, ErrorSeverity } from '@/types/errors';
import { useToast } from '@/contexts/ToastContext';
import { useCallback } from 'react';

interface Props {
  children: ReactNode;
  fallbackComponent?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class EnhancementErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({
      error,
      errorInfo
    });

    // Create a boundary error specific to enhancement system
    const boundaryError = createBoundaryError(error, {
      componentStack: errorInfo.componentStack || '',
      errorBoundary: 'EnhancementErrorBoundary',
      context: { feature: 'enhancement' },
      userMessage: 'An error occurred in the enhancement system. Please try again.',
      recoveryActions: [
        { label: 'Try Again', action: () => this.handleRetry() },
        { label: 'Reload Page', action: () => window.location.reload() }
      ]
    });

    // Handle through error service for centralized logging
    errorService.handleError(boundaryError);

    // Call the onError callback if provided
    this.props.onError?.(error, errorInfo);

    // Show error toast using the centralized system
    if (window.showToast) {
      window.showToast({
        title: 'Enhancement Error',
        message: 'An error occurred in the enhancement system. Please try again.',
        type: 'error',
        duration: 5000
      });
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallbackComponent) {
        return this.props.fallbackComponent;
      }

      // Default fallback UI
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mt-0.5 mr-3 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="text-sm font-medium text-red-800">
                Enhancement System Error
              </h3>
              <p className="mt-1 text-sm text-red-700">
                There was an error with the AI enhancement system. This might be due to a network issue or temporary service problem.
              </p>

              {/* Show error details in development */}
              {process.env.NODE_ENV === 'development' && this.state.error && (
                <details className="mt-2">
                  <summary className="text-xs text-red-600 cursor-pointer hover:text-red-800">
                    Error Details (Development Only)
                  </summary>
                  <pre className="mt-1 text-xs text-red-600 bg-red-100 p-2 rounded overflow-auto max-h-32">
                    {this.state.error.toString()}
                    {this.state.errorInfo?.componentStack}
                  </pre>
                </details>
              )}

              <div className="mt-3 flex space-x-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={this.handleRetry}
                  className="text-red-700 border-red-300 hover:bg-red-100"
                >
                  <ReloadIcon className="w-3 h-3 mr-1" />
                  Try Again
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => window.location.reload()}
                  className="text-red-700 hover:bg-red-100"
                >
                  Reload Page
                </Button>
              </div>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Hook version for functional components
export function useEnhancementErrorHandler() {
  const { showErrorToast } = useToast();

  const handleError = useCallback((error: Error, context: string = 'Enhancement') => {
    // Create a normalized error through error service
    const normalizedError = errorService.normalizeError(error);

    // Add enhancement-specific context
    const enhancementError = {
      ...normalizedError,
      context: {
        ...normalizedError.context,
        feature: 'enhancement',
        operation: context
      },
      userMessage: normalizedError.userMessage || `${context} error occurred. Please try again.`
    };

    // Handle through error service for logging
    errorService.handleError(enhancementError);

    // Show toast notification
    showErrorToast(enhancementError);
  }, [showErrorToast]);


  const handleNetworkError = useCallback((error: Error) => {
    const networkError = createNetworkError(error.message, {
      userMessage: 'Unable to connect to server. Please check your connection.',
      severity: ErrorSeverity.ERROR,
      recoveryActions: [
        { label: 'Retry', action: () => {} },
        { label: 'Reload Page', action: () => window.location.reload() }
      ]
    });

    errorService.handleError(networkError);
    showErrorToast(networkError);
  }, [showErrorToast]);

  return {
    handleError,
    handleNetworkError
  };
}
