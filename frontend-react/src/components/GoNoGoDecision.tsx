import { useState } from 'react';
import { useCreateDecision, useProspectDecisions, useDeleteDecision } from '../hooks/api';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { useError } from '@/hooks/useError';

interface GoNoGoDecisionProps {
  prospectId: string | number;
  prospectTitle?: string;
  compact?: boolean;
}

export const GoNoGoDecision = ({ prospectId, prospectTitle, compact }: GoNoGoDecisionProps) => {
  const [showReasonDialog, setShowReasonDialog] = useState(false);
  const [pendingDecision, setPendingDecision] = useState<'go' | 'no-go' | null>(null);
  const [reason, setReason] = useState('');
  const { handleError } = useError();

  const createDecisionMutation = useCreateDecision();
  const deleteDecisionMutation = useDeleteDecision();
  const { data: decisionsData, isLoading: isLoadingDecisions, error: decisionsError } = useProspectDecisions(prospectId ? String(prospectId) : null);

  // Check if current user has already made a decision
  const existingDecision = decisionsData?.data?.decisions && Array.isArray(decisionsData.data.decisions) && decisionsData.data.decisions.length > 0
    ? decisionsData.data.decisions[0]
    : null;


  const handleDecisionClick = (decision: 'go' | 'no-go') => {
    setPendingDecision(decision);
    setShowReasonDialog(true);
  };

  const handleSubmitDecision = async () => {
    if (!pendingDecision) return;

    try {
      await createDecisionMutation.mutateAsync({
        prospect_id: String(prospectId),
        decision: pendingDecision,
        reason: reason.trim(),
      });

      setShowReasonDialog(false);
      setPendingDecision(null);
      setReason('');
    } catch (error) {
      handleError(error, {
        context: {
          operation: 'saveDecision',
          prospectId,
          decision: pendingDecision
        },
        fallbackMessage: 'Failed to save decision'
      });
    }
  };

  const handleCancel = () => {
    setShowReasonDialog(false);
    setPendingDecision(null);
    setReason('');
  };

  const handleUndoDecision = async () => {
    if (!existingDecision?.id) return;

    try {
      await deleteDecisionMutation.mutateAsync(existingDecision.id);
    } catch (error) {
      handleError(error, {
        context: {
          operation: 'undoDecision',
          decisionId: existingDecision.id,
          prospectId
        },
        fallbackMessage: 'Failed to undo decision'
      });
    }
  };

  // Show loading state
  if (isLoadingDecisions) {
    return (
      <div className="flex items-center gap-2">
        <div className="animate-pulse bg-gray-200 h-6 w-16 rounded"></div>
        <div className="animate-pulse bg-gray-200 h-6 w-16 rounded"></div>
      </div>
    );
  }

  // Show error state (optional - could be silent)
  if (decisionsError) {
    handleError(decisionsError, {
      context: {
        operation: 'loadDecisions',
        prospectId
      },
      fallbackMessage: 'Failed to load existing decisions',
      showToast: false // Silent error - don't show toast for read operations
    });
    // Continue to render without existing decisions
  }

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        {existingDecision ? (
          <div className="flex items-center gap-2">
            <span
              className={`px-2 py-1 rounded text-xs font-medium ${
                existingDecision.decision === 'go'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}
            >
              {existingDecision.decision === 'go' ? 'GO' : 'NO-GO'}
            </span>
            {existingDecision.reason && (
              <span className="text-xs text-gray-500" title={existingDecision.reason}>
                (with reason)
              </span>
            )}
          </div>
        ) : (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleDecisionClick('go')}
              disabled={createDecisionMutation.isPending}
              className="text-green-700 border-green-300 hover:bg-green-50"
            >
              GO
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleDecisionClick('no-go')}
              disabled={createDecisionMutation.isPending}
              className="text-red-700 border-red-300 hover:bg-red-50"
            >
              NO-GO
            </Button>
          </>
        )}

        <Dialog open={showReasonDialog} onOpenChange={setShowReasonDialog}>
          <DialogContent className="w-full max-w-md">
            <DialogHeader>
              <DialogTitle>
                {pendingDecision === 'go' ? 'GO Decision' : 'NO-GO Decision'}
              </DialogTitle>
            </DialogHeader>

            {prospectTitle && (
              <p className="text-sm text-gray-600 mb-4">
                <strong>Prospect:</strong> {prospectTitle}
              </p>
            )}

            <div className="mb-4">
              <Label htmlFor="reason">Reason (optional)</Label>
              <Input
                id="reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Why did you make this decision?"
                className="mt-1"
              />
            </div>

            <div className="flex gap-2 justify-end">
              <Button
                variant="outline"
                onClick={handleCancel}
                disabled={createDecisionMutation.isPending}
              >
                Cancel
              </Button>
              <Button
                onClick={handleSubmitDecision}
                disabled={createDecisionMutation.isPending}
                className={pendingDecision === 'go' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}
              >
                {createDecisionMutation.isPending ? 'Saving...' : `Confirm ${pendingDecision?.toUpperCase()}`}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  // Full version for dedicated decision pages

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold mb-4">Go/No-Go Decision</h3>

      {prospectTitle && (
        <p className="text-gray-600 mb-4">
          <strong>Prospect:</strong> {prospectTitle}
        </p>
      )}

      {existingDecision ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <span>Current Decision:</span>
            <span
              className={`px-3 py-1 rounded font-medium ${
                existingDecision.decision === 'go'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}
            >
              {existingDecision.decision === 'go' ? 'GO' : 'NO-GO'}
            </span>
          </div>

          {existingDecision.reason && (
            <div>
              <strong>Reason:</strong>
              <p className="text-gray-700 mt-1">{existingDecision.reason}</p>
            </div>
          )}

          <div className="text-sm text-gray-500">
            Decision made on {new Date(existingDecision.created_at).toLocaleDateString()}
          </div>

          <div className="pt-4 border-t">
            <p className="text-sm text-gray-600 mb-4">Want to change your decision?</p>
            <div className="flex gap-2">
              {existingDecision.decision === 'go' ? (
                <Button
                  variant="outline"
                  onClick={() => handleDecisionClick('no-go')}
                  disabled={createDecisionMutation.isPending}
                  className="text-red-700 border-red-300 hover:bg-red-50"
                >
                  Change to NO-GO
                </Button>
              ) : (
                <Button
                  variant="outline"
                  onClick={() => handleDecisionClick('go')}
                  disabled={createDecisionMutation.isPending}
                  className="text-green-700 border-green-300 hover:bg-green-50"
                >
                  Change to GO
                </Button>
              )}
              <Button
                variant="outline"
                onClick={handleUndoDecision}
                disabled={deleteDecisionMutation.isPending}
                className="text-gray-700 border-gray-300 hover:bg-gray-50"
              >
                {deleteDecisionMutation.isPending ? 'Undoing...' : 'Undo Decision'}
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-gray-600">What's your decision on this prospect?</p>

          <div className="flex gap-4">
            <Button
              onClick={() => handleDecisionClick('go')}
              disabled={createDecisionMutation.isPending}
              className="bg-green-600 hover:bg-green-700 text-white px-8 py-2"
            >
              GO
            </Button>
            <Button
              onClick={() => handleDecisionClick('no-go')}
              disabled={createDecisionMutation.isPending}
              className="bg-red-600 hover:bg-red-700 text-white px-8 py-2"
            >
              NO-GO
            </Button>
          </div>
        </div>
      )}

      <Dialog open={showReasonDialog} onOpenChange={setShowReasonDialog}>
        <DialogContent className="w-full max-w-md">
          <DialogHeader>
            <DialogTitle>
              {pendingDecision === 'go' ? 'GO Decision' : 'NO-GO Decision'}
            </DialogTitle>
          </DialogHeader>

          <div className="mb-4">
            <Label htmlFor="reason">Reason (optional)</Label>
            <Input
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why did you make this decision?"
              className="mt-1"
            />
            <p className="text-xs text-gray-500 mt-1">
              This will help train our AI to understand company preferences
            </p>
          </div>

          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={handleCancel}
              disabled={createDecisionMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmitDecision}
              disabled={createDecisionMutation.isPending}
              className={pendingDecision === 'go' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}
            >
              {createDecisionMutation.isPending ? 'Saving...' : `Confirm ${pendingDecision?.toUpperCase()}`}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
