import React, { createContext, useContext, useState, useCallback } from 'react';
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
  ToastAction,
  ToastIcon,
} from '@/components/ui/Toast';
import { AppError, ErrorSeverity } from '@/types/errors';

interface ToastData {
  id: string;
  title: string;
  description?: string;
  severity?: ErrorSeverity;
  variant?: 'default' | 'destructive' | 'success' | 'warning' | 'info';
  action?: {
    label: string;
    onClick: () => void;
  };
  duration?: number;
}

interface ToastContextType {
  showToast: (toast: Omit<ToastData, 'id'>) => void;
  showErrorToast: (error: AppError | Error | string) => void;
  showSuccessToast: (message: string, description?: string) => void;
  showInfoToast: (message: string, description?: string) => void;
  showWarningToast: (message: string, description?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

interface ToastProviderProps {
  children: React.ReactNode;
}

export const ToastContextProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const showToast = useCallback((toast: Omit<ToastData, 'id'>) => {
    const id = Date.now().toString();
    const newToast: ToastData = {
      ...toast,
      id,
      duration: toast.duration ?? 5000,
    };

    setToasts((current) => [...current, newToast]);

    // Auto-remove toast after duration
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        setToasts((current) => current.filter((t) => t.id !== id));
      }, newToast.duration);
    }
  }, []);

  const showErrorToast = useCallback((error: AppError | Error | string) => {
    let title = 'Error';
    let description = 'An unexpected error occurred';
    let severity = ErrorSeverity.ERROR;
    let action: ToastData['action'] | undefined;

    if (typeof error === 'string') {
      description = error;
    } else if ('severity' in error && 'userMessage' in error) {
      // It's an AppError
      title = error.userMessage || error.message;
      description = error.technicalDetails || '';
      severity = error.severity;

      // Add recovery actions if available
      const primaryAction = error.recoveryActions?.find(a => a.primary);
      if (primaryAction) {
        action = {
          label: primaryAction.label,
          onClick: primaryAction.action,
        };
      }
    } else {
      // It's a regular Error
      description = error.message;
    }

    showToast({
      title,
      description,
      severity,
      variant: 'destructive',
      action,
      duration: 8000, // Errors stay longer
    });
  }, [showToast]);

  const showSuccessToast = useCallback((message: string, description?: string) => {
    showToast({
      title: message,
      description,
      variant: 'success',
      duration: 3000,
    });
  }, [showToast]);

  const showInfoToast = useCallback((message: string, description?: string) => {
    showToast({
      title: message,
      description,
      variant: 'info',
      severity: ErrorSeverity.INFO,
      duration: 4000,
    });
  }, [showToast]);

  const showWarningToast = useCallback((message: string, description?: string) => {
    showToast({
      title: message,
      description,
      variant: 'warning',
      severity: ErrorSeverity.WARNING,
      duration: 5000,
    });
  }, [showToast]);

  // Also set up the global window.showToast for backward compatibility
  React.useEffect(() => {
    window.showToast = ({ title, message, type = 'info', duration = 5000 }) => {
      const variantMap: Record<string, 'success' | 'destructive' | 'info' | 'warning'> = {
        success: 'success',
        error: 'destructive',
        info: 'info',
        warning: 'warning',
      };

      showToast({
        title,
        description: message,
        variant: variantMap[type] || 'info',
        duration,
      });

      // Return empty string as the global type expects
      return '';
    };

    return () => {
      delete window.showToast;
    };
  }, [showToast]);

  const contextValue: ToastContextType = {
    showToast,
    showErrorToast,
    showSuccessToast,
    showInfoToast,
    showWarningToast,
  };

  return (
    <ToastContext.Provider value={contextValue}>
      <ToastProvider>
        {children}
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            variant={toast.variant}
            severity={toast.severity}
            onOpenChange={(open) => {
              if (!open) {
                setToasts((current) => current.filter((t) => t.id !== toast.id));
              }
            }}
          >
            <div className="flex items-start">
              <ToastIcon variant={toast.variant} severity={toast.severity} />
              <div className="flex-1">
                <ToastTitle>{toast.title}</ToastTitle>
                {toast.description && (
                  <ToastDescription>{toast.description}</ToastDescription>
                )}
              </div>
            </div>
            {toast.action && (
              <ToastAction altText={toast.action.label} onClick={toast.action.onClick}>
                {toast.action.label}
              </ToastAction>
            )}
            <ToastClose />
          </Toast>
        ))}
        <ToastViewport />
      </ToastProvider>
    </ToastContext.Provider>
  );
};

// Re-export the hook for convenience
export { ToastContextProvider as ToastProvider };
