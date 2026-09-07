import React from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { ExclamationTriangleIcon, InfoCircledIcon } from '@radix-ui/react-icons';

interface ConfirmationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  details?: string[];
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'destructive';
  onConfirm: () => void;
  loading?: boolean;
}

export function ConfirmationDialog({
  open,
  onOpenChange,
  title,
  description,
  details,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'default',
  onConfirm,
  loading = false,
}: ConfirmationDialogProps) {
  const handleConfirm = () => {
    onConfirm();
    if (!loading) {
      onOpenChange(false);
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            {variant === 'destructive' ? (
              <ExclamationTriangleIcon className="h-5 w-5 text-red-600" />
            ) : (
              <InfoCircledIcon className="h-5 w-5 text-blue-600" />
            )}
            {title}
          </AlertDialogTitle>
          {description && (
            <AlertDialogDescription className="text-gray-600">
              {description}
            </AlertDialogDescription>
          )}
        </AlertDialogHeader>

        {details && details.length > 0 && (
          <div className={`rounded-md p-4 ${
            variant === 'destructive'
              ? 'bg-red-50 border border-red-200'
              : 'bg-blue-50 border border-blue-200'
          }`}>
            <ul className="space-y-1 text-sm">
              {details.map((detail, index) => (
                <li key={index} className={
                  variant === 'destructive' ? 'text-red-800' : 'text-blue-800'
                }>
                  {detail.startsWith('•') ? detail : `• ${detail}`}
                </li>
              ))}
            </ul>
          </div>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={loading}
            className={
              variant === 'destructive'
                ? 'bg-red-600 hover:bg-red-700 focus:ring-red-600'
                : ''
            }
          >
            {loading ? 'Processing...' : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

// Hook for easier usage
export function useConfirmationDialog() {
  const [dialogState, setDialogState] = React.useState<{
    open: boolean;
    props: Partial<ConfirmationDialogProps>;
    resolve?: (confirmed: boolean) => void;
  }>({
    open: false,
    props: {},
  });

  const confirm = React.useCallback(
    (props: Omit<ConfirmationDialogProps, 'open' | 'onOpenChange' | 'onConfirm'>) => {
      return new Promise<boolean>((resolve) => {
        setDialogState({
          open: true,
          props,
          resolve,
        });
      });
    },
    []
  );

  const handleOpenChange = React.useCallback((open: boolean) => {
    if (!open && dialogState.resolve) {
      dialogState.resolve(false);
    }
    setDialogState((prev) => ({ ...prev, open }));
  }, [dialogState.resolve]);

  const handleConfirm = React.useCallback(() => {
    if (dialogState.resolve) {
      dialogState.resolve(true);
    }
    setDialogState((prev) => ({ ...prev, open: false }));
  }, [dialogState.resolve]);

  const DialogComponent = React.useMemo(
    () => (
      <ConfirmationDialog
        open={dialogState.open}
        onOpenChange={handleOpenChange}
        onConfirm={handleConfirm}
        title="Confirm Action"
        {...dialogState.props}
      />
    ),
    [dialogState.open, dialogState.props, handleOpenChange, handleConfirm]
  );

  return { confirm, ConfirmationDialog: DialogComponent };
}
