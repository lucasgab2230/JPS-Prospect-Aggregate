import { useState, useCallback, useMemo } from 'react';
import type { Prospect } from '@/types/prospects';

export function useProspectModal(prospects: Prospect[] = []) {
  const [selectedProspectId, setSelectedProspectId] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const selectedProspect = useMemo(() => {
    if (!selectedProspectId || !prospects.length) return null;
    return prospects.find((p) => p.id === selectedProspectId) || null;
  }, [selectedProspectId, prospects]);

  const openModal = useCallback((prospect: Prospect) => {
    setSelectedProspectId(prospect.id);
    setIsOpen(true);
  }, []);

  const closeModal = useCallback(() => {
    setIsOpen(false);
    setSelectedProspectId(null);
  }, []);

  const handleOpenChange = useCallback((open: boolean) => {
    setIsOpen(open);
    if (!open) {
      setSelectedProspectId(null);
    }
  }, []);

  return {
    selectedProspect,
    selectedProspectId,
    isOpen,
    openModal,
    closeModal,
    handleOpenChange,
    setSelectedProspectId,
    setIsOpen
  };
}
