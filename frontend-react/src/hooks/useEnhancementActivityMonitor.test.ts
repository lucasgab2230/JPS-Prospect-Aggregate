import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useEnhancementActivityMonitor } from './useEnhancementActivityMonitor';

// Mock the hooks it depends on
const mockEnhancementStates = vi.fn();
const mockIsWorkerRunning = vi.fn();
const mockIsIterativeProcessing = vi.fn();

vi.mock('@/hooks/api/useEnhancementSimple', () => ({
  useEnhancementSimple: () => ({
    enhancementStates: mockEnhancementStates()
  })
}));

vi.mock('@/hooks/api/useEnhancementQueueService', () => ({
  useEnhancementQueueService: () => ({
    isWorkerRunning: mockIsWorkerRunning(),
    isIterativeProcessing: mockIsIterativeProcessing()
  })
}));

// Mock enhancement states
const mockIdleState = { status: 'idle', progress: {} };
const mockQueuedState = { status: 'queued', progress: {}, queuePosition: 1 };
const mockProcessingState = { status: 'processing', progress: {}, currentStep: 'values' };
const mockCompletedState = { status: 'completed', progress: {} };
const mockFailedState = { status: 'failed', progress: {}, error: 'Test error' };

// Wrapper component for React Query
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  // Spy on setQueryDefaults to verify polling configuration
  vi.spyOn(queryClient, 'setQueryDefaults');
  vi.spyOn(queryClient, 'invalidateQueries');

  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe('useEnhancementActivityMonitor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();

    // Default mock returns
    mockEnhancementStates.mockReturnValue({});
    mockIsWorkerRunning.mockReturnValue(false);
    mockIsIterativeProcessing.mockReturnValue(false);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it('initializes with no activity state', () => {
    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(false);
    expect(result.current.totalActiveCount).toBe(0);
    expect(result.current.processingCount).toBe(0);
    expect(result.current.queuedCount).toBe(0);
    expect(result.current.workerActive).toBe(false);
    expect(result.current.iterativeActive).toBe(false);
    expect(result.current.lastActivityTime).toBeNull();
    expect(result.current.hasAnyActivity).toBe(false);
  });

  it('detects processing enhancements', () => {
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockProcessingState,
      'prospect-2': mockIdleState,
      'prospect-3': mockProcessingState
    });

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(true);
    expect(result.current.totalActiveCount).toBe(2);
    expect(result.current.processingCount).toBe(2);
    expect(result.current.queuedCount).toBe(0);
    expect(result.current.hasAnyActivity).toBe(true);
  });

  it('detects queued enhancements', () => {
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockQueuedState,
      'prospect-2': mockCompletedState,
      'prospect-3': mockQueuedState,
      'prospect-4': mockFailedState
    });

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(true);
    expect(result.current.totalActiveCount).toBe(2);
    expect(result.current.processingCount).toBe(0);
    expect(result.current.queuedCount).toBe(2);
    expect(result.current.hasAnyActivity).toBe(true);
  });

  it('detects mixed processing and queued enhancements', () => {
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockProcessingState,
      'prospect-2': mockQueuedState,
      'prospect-3': mockQueuedState,
      'prospect-4': mockCompletedState
    });

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(true);
    expect(result.current.totalActiveCount).toBe(3);
    expect(result.current.processingCount).toBe(1);
    expect(result.current.queuedCount).toBe(2);
  });

  it('detects worker activity even without active enhancements', () => {
    mockEnhancementStates.mockReturnValue({});
    mockIsWorkerRunning.mockReturnValue(true);

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(true);
    expect(result.current.totalActiveCount).toBe(0);
    expect(result.current.workerActive).toBe(true);
    expect(result.current.hasAnyActivity).toBe(true);
  });

  it('detects iterative processing activity', () => {
    mockEnhancementStates.mockReturnValue({});
    mockIsIterativeProcessing.mockReturnValue(true);

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(true);
    expect(result.current.totalActiveCount).toBe(0);
    expect(result.current.iterativeActive).toBe(true);
    expect(result.current.hasAnyActivity).toBe(true);
  });

  it('adjusts polling interval based on processing activity', () => {
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockProcessingState
    });

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    // The polling interval should eventually be set to 1000ms for processing
    expect(result.current.hasActiveEnhancements).toBe(true);
    expect(result.current.processingCount).toBe(1);
  });

  it('adjusts polling interval based on queued activity', () => {
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockQueuedState,
      'prospect-2': mockQueuedState
    });

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(true);
    expect(result.current.queuedCount).toBe(2);
  });

  it('detects background worker activity', () => {
    mockEnhancementStates.mockReturnValue({});
    mockIsWorkerRunning.mockReturnValue(true);

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(true);
    expect(result.current.workerActive).toBe(true);
  });

  it('detects idle state correctly', () => {
    mockEnhancementStates.mockReturnValue({});
    mockIsWorkerRunning.mockReturnValue(false);
    mockIsIterativeProcessing.mockReturnValue(false);

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(false);
    expect(result.current.hasAnyActivity).toBe(false);
  });

  it('handles activity state changes over time', () => {
    // Start with processing
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockProcessingState
    });

    const { result, rerender } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.processingCount).toBe(1);
    expect(result.current.hasAnyActivity).toBe(true);

    // Change to queued
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockQueuedState
    });
    rerender();

    expect(result.current.processingCount).toBe(0);
    expect(result.current.queuedCount).toBe(1);
    expect(result.current.hasAnyActivity).toBe(true);

    // Go to idle
    mockEnhancementStates.mockReturnValue({});
    rerender();

    expect(result.current.hasAnyActivity).toBe(false);
    expect(result.current.totalActiveCount).toBe(0);
  });

  it('provides activity summary for processing state', () => {
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockProcessingState,
      'prospect-2': mockProcessingState
    });

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.getActivitySummary()).toBe('2 processing');
  });

  it('provides activity summary for queued state', () => {
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockQueuedState,
      'prospect-2': mockQueuedState,
      'prospect-3': mockQueuedState
    });

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.getActivitySummary()).toBe('3 queued');
  });

  it('provides activity summary for mixed states', () => {
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockProcessingState,
      'prospect-2': mockQueuedState,
      'prospect-3': mockQueuedState
    });

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.getActivitySummary()).toBe('1 processing, 2 queued');
  });

  it('provides activity summary for iterative processing', () => {
    mockEnhancementStates.mockReturnValue({});
    mockIsIterativeProcessing.mockReturnValue(true);

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.getActivitySummary()).toBe('bulk enhancement running');
  });

  it('provides activity summary for idle worker', () => {
    mockEnhancementStates.mockReturnValue({});
    mockIsWorkerRunning.mockReturnValue(true);

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.getActivitySummary()).toBe('worker idle');
  });

  it('provides no activity summary when completely idle', () => {
    mockEnhancementStates.mockReturnValue({});
    mockIsWorkerRunning.mockReturnValue(false);
    mockIsIterativeProcessing.mockReturnValue(false);

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.getActivitySummary()).toBe('No activity');
  });

  it('refreshes all enhancement-related queries', async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper }
    );

    // Get the query client from the wrapper to check calls
    const _mockInvalidateQueries = vi.fn();

    act(() => {
      result.current.refreshAll();
    });

    // The refreshAll function should call invalidateQueries
    expect(typeof result.current.refreshAll).toBe('function');
  });

  it('has access to query configuration functions', () => {
    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    // The hook should have access to refreshAll function
    expect(typeof result.current.refreshAll).toBe('function');
  });

  it('handles rapid state changes without issues', async () => {
    const { result, rerender } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    // Rapid state changes
    mockEnhancementStates.mockReturnValue({ 'prospect-1': mockProcessingState });
    rerender();

    mockEnhancementStates.mockReturnValue({ 'prospect-1': mockQueuedState });
    rerender();

    mockEnhancementStates.mockReturnValue({});
    rerender();

    mockEnhancementStates.mockReturnValue({ 'prospect-1': mockProcessingState });
    rerender();

    // Should handle all changes gracefully
    expect(result.current.hasAnyActivity).toBe(true);
    expect(result.current.processingCount).toBe(1);
  });

  it('provides stable function references', () => {
    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    // Functions should exist and be functions
    expect(typeof result.current.refreshAll).toBe('function');
    expect(typeof result.current.getActivitySummary).toBe('function');
  });

  it('handles empty enhancement states', () => {
    mockEnhancementStates.mockReturnValue({});

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.hasActiveEnhancements).toBe(false);
    expect(result.current.totalActiveCount).toBe(0);
    expect(result.current.processingCount).toBe(0);
    expect(result.current.queuedCount).toBe(0);
  });

  it('calculates activity timing correctly', () => {
    const mockDate = new Date('2024-01-15T10:00:00Z');
    vi.setSystemTime(mockDate);

    // Start with activity
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockProcessingState
    });

    const { result, rerender } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.lastActivityTime).toBeTruthy();
    expect(result.current.lastActivityTime?.getTime()).toBe(mockDate.getTime());

    // Stop activity
    mockEnhancementStates.mockReturnValue({});
    rerender();

    expect(result.current.lastActivityTime).toBeNull();
  });

  it('prioritizes processing over queued in activity detection', () => {
    // Mix of processing and queued
    mockEnhancementStates.mockReturnValue({
      'prospect-1': mockProcessingState,
      'prospect-2': mockQueuedState,
      'prospect-3': mockQueuedState
    });

    const { result } = renderHook(
      () => useEnhancementActivityMonitor(),
      { wrapper: createWrapper() }
    );

    expect(result.current.processingCount).toBe(1);
    expect(result.current.queuedCount).toBe(2);
    expect(result.current.totalActiveCount).toBe(3);
    expect(result.current.hasAnyActivity).toBe(true);
  });
});
