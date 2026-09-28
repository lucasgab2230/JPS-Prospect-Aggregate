// Updated Prospect interface based on backend model
export interface Prospect {
  id: string; // Primary key, string (UUID)
  native_id: string | null; // From source system
  title: string; // Main title/name of the prospect
  ai_enhanced_title: string | null; // NEW: AI-enhanced title
  description: string | null;
  agency: string | null;
  naics: string | null;
  naics_description: string | null; // NEW: NAICS description
  naics_source: string | null; // NEW: 'original', 'llm_inferred', 'llm_enhanced'
  estimated_value: string | null; // Represented as string in to_dict
  est_value_unit: string | null;
  estimated_value_text: string | null; // NEW: Original value as text
  estimated_value_min: string | null; // NEW: LLM-parsed minimum
  estimated_value_max: string | null; // NEW: LLM-parsed maximum
  estimated_value_single: string | null; // NEW: LLM best estimate
  release_date: string | null; // ISO date string
  award_date: string | null; // ISO date string
  award_fiscal_year: number | null;
  // Animation properties for real-time updates
  _recentlyUpdated?: string;
  _updateTimestamp?: number;
  place_city: string | null;
  place_state: string | null;
  place_country: string | null;
  contract_type: string | null;
  set_aside: string | null;
  set_aside_standardized: string | null; // NEW: Standardized set-aside code (e.g., 'SMALL_BUSINESS')
  set_aside_standardized_label: string | null; // NEW: Human-readable set-aside label
  primary_contact_email: string | null; // NEW: LLM-extracted email
  primary_contact_name: string | null; // NEW: LLM-extracted name
  loaded_at: string | null; // ISO datetime string
  ollama_processed_at: string | null; // NEW: When LLM processing completed
  ollama_model_version: string | null; // NEW: Which LLM version was used
  enhancement_status: string | null; // NEW: 'idle', 'in_progress', 'failed'
  enhancement_started_at: string | null; // NEW: When enhancement started
  enhancement_user_id: number | null; // NEW: User ID who started enhancement
  extra: Record<string, unknown> | null; // JSON object
  source_id: number | null;
  source_name: string | null; // Name of the data source
}

export enum ProspectStatus {
  DRAFT = 'Draft',
  SUBMITTED = 'Submitted',
  REVIEW = 'In Review',
  APPROVED = 'Approved',
  REJECTED = 'Rejected',
}

export interface ProspectStatistics {
  data: {
    total: number;
    approved: number;
    pending: number;
    rejected: number;
  };
}

export interface ProspectFilters {
  status?: ProspectStatus;
  dataSourceIds?: number[];  // Changed to array for multiple selection
  startDate?: string;
  endDate?: string;
  search?: string;
  keywords?: string;
  naics?: string;
  agency?: string;
}

// Query data structure for prospects
export interface ProspectsQueryData {
  data: Prospect[];
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
  };
}
