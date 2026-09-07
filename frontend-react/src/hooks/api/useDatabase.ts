import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';


// --- Type Definitions (assuming these are representative) ---
export interface DatabaseStatus {
  status: string;
  lastBackup: string; // Should ideally be Date or ISO string
  size: string; // Or number, units should be clear
  health?: string;
  uptime?: string;
}

export interface DatabaseBackup {
  id: string;
  timestamp: string; // Should ideally be Date or ISO string
  size: string; // Or number, units should be clear
  status?: string;
}

export interface QueryResult {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  rowCount: number;
  executionTime?: number; // ms
  message?: string;
}

// --- API Call Functions (Placeholders) ---

async function fetchDatabaseStatusAPI(): Promise<DatabaseStatus> {
  // Fetching database status
  await new Promise(resolve => setTimeout(resolve, 300));
  return { status: 'Online', lastBackup: new Date().toISOString(), size: '1.2 GB', health: 'Good', uptime: '7 days' };
}

async function fetchDatabaseBackupsAPI(): Promise<DatabaseBackup[]> {
  // Fetching database backups
  await new Promise(resolve => setTimeout(resolve, 600));
  return [
    { id: 'backup-1', timestamp: new Date(Date.now() - 86400000).toISOString(), size: '1.2 GB', status: 'Completed' },
    { id: 'backup-2', timestamp: new Date(Date.now() - 172800000).toISOString(), size: '1.1 GB', status: 'Completed' },
  ];
}

async function rebuildDatabaseAPI(): Promise<void> {
  // Rebuilding database
  await new Promise(resolve => setTimeout(resolve, 2000));
}

async function initializeDatabaseAPI(): Promise<void> {
  // Initializing database
  await new Promise(resolve => setTimeout(resolve, 3000));
}

async function resetDatabaseAPI(): Promise<void> {
  // Resetting database
  await new Promise(resolve => setTimeout(resolve, 1500));
}

async function createBackupAPI(): Promise<DatabaseBackup> { // Assuming API returns the created backup info
  // Creating database backup
  await new Promise(resolve => setTimeout(resolve, 2500));
  return { id: `backup-${Date.now()}`, timestamp: new Date().toISOString(), size: '1.3 GB', status: 'Completed' };
}

async function restoreBackupAPI(_params: { backupId: string }): Promise<void> {
  // Restoring backup with id: ${params.backupId}
  await new Promise(resolve => setTimeout(resolve, 4000));
}

async function executeQueryAPI({ query }: { query: string }): Promise<QueryResult> {
  // Executing query
  await new Promise(resolve => setTimeout(resolve, 1000));
  if (query.toLowerCase().includes('error')) throw new Error('Simulated query error');
  return {
    columns: ['id', 'name', 'value'],
    rows: [
      { id: 1, name: 'Test', value: 100 },
      { id: 2, name: 'Sample', value: 200 }
    ],
    rowCount: 2,
    executionTime: 150,
    message: 'Query executed successfully'
  };
}

// --- React Query Keys ---
const dbQueryKeys = {
  all: () => ['database'] as const,
  status: () => [...dbQueryKeys.all(), 'status'] as const,
  backups: () => [...dbQueryKeys.all(), 'backups'] as const,
};

// --- React Query Hooks ---

export const useDatabaseStatus = () => {
  return useQuery({
    queryKey: dbQueryKeys.status(),
    queryFn: fetchDatabaseStatusAPI,
  });
};

export const useDatabaseBackups = () => {
  return useQuery({
    queryKey: dbQueryKeys.backups(),
    queryFn: fetchDatabaseBackupsAPI,
    placeholderData: keepPreviousData, // Added placeholderData for better UX
  });
};

export const useRebuildDatabase = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: rebuildDatabaseAPI,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dbQueryKeys.all() }); // Invalidate all DB related queries
    },
  });
};

export const useInitializeDatabase = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: initializeDatabaseAPI,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dbQueryKeys.all() });
    },
  });
};

export const useResetDatabase = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: resetDatabaseAPI,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dbQueryKeys.all() });
    },
  });
};

export const useCreateBackup = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createBackupAPI,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dbQueryKeys.backups() });
      // Optionally add the new backup to the cache immediately
      // queryClient.setQueryData(dbQueryKeys.backups(), (oldData: DatabaseBackup[] | undefined) =>
      //  [...(oldData || []), newBackup]
      // );
      queryClient.invalidateQueries({ queryKey: dbQueryKeys.status() }); // Backup might affect status
    },
  });
};

export const useRestoreBackup = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: restoreBackupAPI,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dbQueryKeys.all() });
    },
  });
};

export const useExecuteQuery = () => {
  // No cache invalidation by default for arbitrary queries,
  // but component might want to refetch specific data based on query type.
  return useMutation({
    mutationFn: executeQueryAPI,
  });
};
