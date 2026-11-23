import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ReloadIcon, Cross1Icon, DotsVerticalIcon } from '@radix-ui/react-icons';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useProspectEnhancement } from '@/contexts/ProspectEnhancementContext';
import { useEnhancementErrorHandler } from './EnhancementErrorBoundary';

interface EnhancementButtonWithSelectorProps {
  prospect: {
    id: string;
    ollama_processed_at?: string | null;
  };
  userId?: number;
  forceRedo?: boolean;
  onEnhancementStart?: () => void;
}

export function EnhancementButtonWithSelector({
  prospect,
  userId = 1,
  forceRedo = false,
  onEnhancementStart
}: EnhancementButtonWithSelectorProps) {
  const { addToQueue, getProspectStatus, cancelEnhancement } = useProspectEnhancement();
  const { handleError } = useEnhancementErrorHandler();

  const status = getProspectStatus(prospect.id);
  const isAlreadyEnhanced = !!prospect.ollama_processed_at;

  // Enhancement types state
  const [selectedEnhancementTypes, setSelectedEnhancementTypes] = useState({
    values: true,
    titles: true,
    naics: true,
    set_asides: true,
  });

  const enhancementOptions = [
    { key: 'titles', label: 'Titles' },
    { key: 'values', label: 'Values' },
    { key: 'naics', label: 'NAICS' },
    { key: 'set_asides', label: 'Set-Asides' },
  ] as const;

  const handleEnhancementTypeChange = (type: string, checked: boolean) => {
    setSelectedEnhancementTypes(prev => ({
      ...prev,
      [type]: checked
    }));
  };

  const getSelectedEnhancementTypes = () => {
    return Object.entries(selectedEnhancementTypes)
      .filter(([_, selected]) => selected)
      .map(([type, _]) => type);
  };

  const selectAllEnhancements = () => {
    setSelectedEnhancementTypes({
      values: true,
      titles: true,
      naics: true,
      set_asides: true,
    });
  };

  const deselectAllEnhancements = () => {
    setSelectedEnhancementTypes({
      values: false,
      titles: false,
      naics: false,
      set_asides: false,
    });
  };

  const hasAnySelected = Object.values(selectedEnhancementTypes).some(selected => selected);
  const hasAllSelected = Object.values(selectedEnhancementTypes).every(selected => selected);

  const handleEnhanceClick = async () => {
    try {
      // Immediately trigger the start callback to show progress box
      onEnhancementStart?.();

      const selectedTypes = getSelectedEnhancementTypes();

      await addToQueue({
        prospect_id: prospect.id,
        user_id: userId,
        force_redo: forceRedo || isAlreadyEnhanced,
        enhancement_types: selectedTypes
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
  const isActive = isQueued || isProcessing;
  const isDisabled = isActive || !hasAnySelected;

  const getButtonContent = () => {
    if (isActive) {
      // Show queue position in x/y format
      const position = status?.queuePosition || 1;
      const total = status?.queueSize || position;
      return (
        <>
          <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
          Queued ({position}/{total})
        </>
      );
    }

    return isAlreadyEnhanced ? 'Redo Enhancement' : 'Enhance with AI';
  };

  // Show cancel button alongside main button when active
  const showCancelButton = isActive;

  // Build the main button UI
  const mainButton = (
    <Button
      onClick={handleEnhanceClick}
      disabled={isDisabled}
      className={`
        ${isActive ? 'bg-gray-600' : isAlreadyEnhanced ? 'bg-blue-600 hover:bg-blue-700' : 'bg-blue-600 hover:bg-blue-700'}
        text-white disabled:bg-gray-600 disabled:opacity-100 min-w-[140px]
      `}
    >
      {getButtonContent()}
    </Button>
  );

  // Show selector only when already enhanced (redo scenario) and not active
  if (isAlreadyEnhanced && !isActive) {
    return (
      <div className="flex items-center gap-1">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              className="h-[38px] w-[38px]"
              disabled={isActive}
            >
              <DotsVerticalIcon className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuLabel>Select Enhancements</DropdownMenuLabel>
            <DropdownMenuSeparator />

            {enhancementOptions.map((option) => (
              <DropdownMenuCheckboxItem
                key={option.key}
                checked={selectedEnhancementTypes[option.key as keyof typeof selectedEnhancementTypes]}
                onCheckedChange={(checked) => handleEnhancementTypeChange(option.key, checked)}
                onSelect={(e) => e.preventDefault()}
              >
                {option.label}
              </DropdownMenuCheckboxItem>
            ))}

            <DropdownMenuSeparator />

            <DropdownMenuCheckboxItem
              checked={hasAllSelected}
              onCheckedChange={(checked) => {
                if (checked) {
                  selectAllEnhancements();
                } else {
                  deselectAllEnhancements();
                }
              }}
              onSelect={(e) => e.preventDefault()}
            >
              Select All
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {mainButton}
      </div>
    );
  }

  // Show button with cancel option if active
  if (showCancelButton) {
    return (
      <div className="flex items-center gap-1">
        {mainButton}
        <Button
          variant="ghost"
          size="sm"
          className="h-9 w-9 p-0 hover:bg-red-100"
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

  // Not enhanced yet and not active, show simple button
  return mainButton;
}
