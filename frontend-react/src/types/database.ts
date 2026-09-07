/**
 * Type definitions for database operations
 */

// Database backup information
export interface DatabaseBackup {
  id: string;
  timestamp: string;
  size: string;
  name?: string;
}

// Database status information
export interface DatabaseStatus {
  size: string;
  lastBackup: string | null;
  uptime: string;
  health: string;
  tables?: number;
  records?: number;
}

// SQL query result
export interface QueryResult {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  rowCount: number;
  message?: string;
}

// Duplicate scan progress
export interface DuplicateScanProgress {
  status: 'in_progress' | 'completed' | 'error';
  message: string;
  current?: number;
  total?: number;
  percentage?: number;
  elapsed_time?: number;
  eta?: number;
  duplicates_found?: number;
  results?: unknown; // Results when scan is completed
}

// Scraper run response
export interface ScraperRunResponse {
  status: string;
  message: string;
  records_added?: number;
  duplicates_found?: number;
  errors?: string[];
}

// Filter state for advanced search
export interface AdvancedFilters {
  search: string;
  source: string;
  hasValue: boolean;
  hasContact: boolean;
  dateRange: string;
  naics?: string;
  estimatedValue?: string;
  decisionStatus?: string;
  myDecisionsOnly: boolean;
}
