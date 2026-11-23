export interface ScriptParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'choice';
  required?: boolean;
  default?: string;
  description?: string;
  choices?: string[];
}

export interface Script {
  id: string;
  name: string;
  description: string;
  script_path: string;
  category: string;
  parameters?: ScriptParameter[];
  dangerous?: boolean;
  requires_confirmation?: boolean;
  timeout?: number;
}

export interface ExecuteScriptParams {
  scriptId: string;
  parameters: Record<string, string | number | boolean>;
}

export interface ExecutionResult {
  id: string;
  script_id: string;
  script_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'error';
  output?: string[];
  error?: string;
  started_at?: string;
  parameters?: Record<string, string | number | boolean>;
  command?: string;
}
