/**
 * Type definitions for AI enhancement features
 */

// Data returned from enhancement steps
export interface EnhancementStepData {
  completed: boolean;
  skipped?: boolean;
  data?: {
    // Values step data
    estimated_value_single?: string;
    estimated_value_min?: string;
    estimated_value_max?: string;

    // NAICS step data
    naics?: string;
    naics_description?: string;
    naics_source?: string;

    // Titles step data
    ai_enhanced_title?: string;

    // Set-aside step data
    inferred_set_aside?: string;
    standardized_set_aside?: string;

    // Common fields
    skipped?: boolean;
    [key: string]: unknown; // For additional data
  };
}

// Progress tracking for enhancement operations
export interface EnhancementProgress {
  titles?: EnhancementStepData;
  values?: EnhancementStepData;
  naics?: EnhancementStepData;
  set_asides?: EnhancementStepData;
}

// Full enhancement state
export interface EnhancementState {
  status: 'idle' | 'queued' | 'processing' | 'completed' | 'failed';
  queuePosition?: number;
  currentStep?: string;
  progress: EnhancementProgress;
  error?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedTimeRemaining?: number;
}

// Individual prospect enhancement state
export interface ProspectEnhancementState {
  queueItemId?: string;
  status: 'idle' | 'queued' | 'processing' | 'completed' | 'failed';
  queuePosition?: number;
  estimatedTimeRemaining?: number;
  currentStep?: string;
  progress?: EnhancementProgress;
  error?: string;
  startedAt?: string;
  completedAt?: string;
}

// Unified enhancement state map
export type UnifiedEnhancementState = {
  [prospect_id: string]: ProspectEnhancementState;
};

// LLM parsed result types
export interface ValuesResult {
  estimated_value_single?: string;
  estimated_value_min?: string;
  estimated_value_max?: string;
}


export interface NaicsResult {
  naics?: string;
  naics_description?: string;
  naics_source?: string;
}

export interface TitlesResult {
  ai_enhanced_title?: string;
}

export interface SetAsidesResult {
  inferred_set_aside?: string;
  standardized_set_aside?: string;
}

export type LLMParsedResult =
  | ValuesResult
  | NaicsResult
  | TitlesResult
  | SetAsidesResult
  | Record<string, unknown>;
