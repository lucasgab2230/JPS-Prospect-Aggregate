import { Button } from '@/components/ui/button';
import { ReloadIcon, Cross1Icon } from '@radix-ui/react-icons';
import { useProspectEnhancement } from '@/contexts/ProspectEnhancementContext';
import { useEnhancementErrorHandler } from './EnhancementErrorBoundary';

interface EnhancementButtonProps {
  prospect: {
    id: string;
    ollama_processed_at?: string | null;
  };
  userId?: number;
  forceRedo?: boolean;
  onEnhancementStart?: () => void;
}

export function EnhancementButton({
  prospect,
  userId = 1,
  forceRedo = false,
  onEnhancementStart
}: EnhancementButtonProps) {
  const { addToQueue, getProspectStatus, cancelEnhancement } = useProspectEnhancement();
  const { handleError } = useEnhancementErrorHandler();

  const status = getProspectStatus(prospect.id);
  const isAlreadyEnhanced = !!prospect.ollama_processed_at;

  const handleEnhanceClick = async () => {
    try {
      // Immediately trigger the start callback to show progress box
      onEnhancementStart?.();

      await addToQueue({
        prospect_id: prospect.id,
        user_id: userId,
        force_redo: forceRedo || isAlreadyEnhanced
      });
    } catch (error) {
      handleError(error as Error, 'Enhancement Queue');
    }
  };

  const handleCancelClick = async () => {
    try {
      const success = await cancelEnhancement(prospect.id);
      if (!success) {
        throw new Error('Failed to cancel enhancement');
      }
    } catch (error) {
      handleError(error as Error, 'Enhancement Cancellation');
    }
  };

  const isQueued = status?.status === 'queued';
  const isProcessing = status?.status === 'processing';
  const isDisabled = isQueued || isProcessing;

  const getButtonContent = () => {
    if (isProcessing) {
      // Show queue position if available, along with current step
      const queueInfo = status?.queuePosition ? `(#${status.queuePosition}) ` : '';
      return (
        <>
          <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
          {queueInfo}{status?.currentStep || 'Enhancing...'}
        </>
      );
    }


    return isAlreadyEnhanced ? 'Redo Enhancement' : 'Enhance with AI';
  };

  if (isQueued) {
    return (
      <div className="flex items-center">
        <Button
          disabled={true}
          className="bg-orange-600 text-white disabled:bg-orange-600 disabled:opacity-100 min-w-[140px]"
        >
          <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
          <span>
            Queued (#{status?.queuePosition})
            {status?.estimatedTimeRemaining && (
              <span className="text-xs ml-1">
                ~{Math.ceil(status.estimatedTimeRemaining / 60)}m
              </span>
            )}
          </span>
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="h-9 w-9 p-0 ml-1 hover:bg-red-100"
          onClick={(e) => {
            e.stopPropagation();
            handleCancelClick();
          }}
        >
          <Cross1Icon className="h-4 w-4 text-red-600" />
        </Button>
      </div>
    );
  }

  return (
    <Button
      onClick={handleEnhanceClick}
      disabled={isDisabled}
      className={`
        ${isProcessing ? 'bg-blue-600' : 'bg-blue-600 hover:bg-blue-700'}
        text-white disabled:bg-gray-400 min-w-[140px]
      `}
    >
      {getButtonContent()}
    </Button>
  );
}
