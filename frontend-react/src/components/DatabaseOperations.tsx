import { useState } from 'react';
import { Button, Card, CardContent, CardHeader, CardTitle } from '@/components/ui';
import {
  useDatabaseStatus,
  useDatabaseBackups,
  useRebuildDatabase,
  useInitializeDatabase,
  useResetDatabase,
  useCreateBackup,
  useRestoreBackup
} from '@/hooks/api/useDatabase';
import { DatabaseBackup } from '@/types';

export function DatabaseOperations() {
  const [isConfirmingReset, setIsConfirmingReset] = useState(false);

  const { data: status, isLoading: statusLoading } = useDatabaseStatus();
  const { data: backups, isLoading: backupsLoading } = useDatabaseBackups();

  const { mutate: rebuildDatabase, isPending: isRebuilding } = useRebuildDatabase();
  const { mutate: initializeDatabase, isPending: isInitializing } = useInitializeDatabase();
  const { mutate: resetDatabase, isPending: isResetting } = useResetDatabase();
  const { mutate: createBackup, isPending: isBackingUp } = useCreateBackup();
  const { mutate: restoreBackup, isPending: isRestoring } = useRestoreBackup();

  const handleRebuild = () => {
    rebuildDatabase();
  };

  const handleInitialize = () => {
    initializeDatabase();
  };

  const handleReset = () => {
    if (!isConfirmingReset) {
      setIsConfirmingReset(true);
      return;
    }

    resetDatabase(undefined, {
      onSuccess: () => {
        // Intentionally empty
        setIsConfirmingReset(false);
      },
      onError: (_error: Error) => {
        setIsConfirmingReset(false);
      }
    });
  };

  const handleCreateBackup = () => {
    createBackup();
  };

  const handleRestoreBackup = (backupId: string) => {
    restoreBackup({ backupId });
  };

  const isLoading = statusLoading || backupsLoading || isRebuilding ||
                    isInitializing || isResetting || isBackingUp || isRestoring;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Database Operations</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Database Status */}
        {status && (
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-sm text-muted-foreground">Database Size</p>
              <p className="text-lg font-semibold">{status.size}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Last Backup</p>
              <p className="text-lg font-semibold">{status.lastBackup || 'Never'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Uptime</p>
              <p className="text-lg font-semibold">{status.uptime}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Health</p>
              <p className="text-lg font-semibold">{status.health}</p>
            </div>
          </div>
        )}

        {/* Operation Buttons */}
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={handleRebuild}
            disabled={isLoading}
          >
            {isRebuilding ? 'Rebuilding...' : 'Rebuild Database'}
          </Button>
          <Button
            onClick={handleInitialize}
            disabled={isLoading}
          >
            {isInitializing ? 'Initializing...' : 'Initialize Database'}
          </Button>
          <Button
            onClick={handleCreateBackup}
            disabled={isLoading}
            variant="outline"
          >
            {isBackingUp ? 'Creating Backup...' : 'Create Backup'}
          </Button>
        </div>

        {/* Reset Confirmation */}
        {isConfirmingReset ? (
          <div className="border border-red-600 bg-red-50 dark:bg-red-900/20 rounded-md p-4">
            <h4 className="font-semibold text-red-800 dark:text-red-400 mb-1">Warning</h4>
            <div className="text-sm text-red-700 dark:text-red-300">
              This will permanently delete all data. Are you sure?
              <div className="flex gap-2 mt-2">
                <Button
                  variant="destructive"
                  onClick={handleReset}
                  disabled={isLoading}
                >
                  {isResetting ? 'Resetting...' : 'Confirm Reset'}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setIsConfirmingReset(false)}
                  disabled={isLoading}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <Button
            variant="destructive"
            onClick={handleReset}
            disabled={isLoading}
          >
            Reset Everything
          </Button>
        )}

        {/* Backups List */}
        {backups && backups.length > 0 && (
          <div className="mt-4">
            <h3 className="text-lg font-semibold mb-2">Available Backups</h3>
            <div className="space-y-2">
              {backups.map((backup: DatabaseBackup) => (
                <div
                  key={backup.id}
                  className="flex items-center justify-between p-2 border rounded"
                >
                  <div>
                    <p className="font-medium">{new Date(backup.timestamp).toLocaleString()}</p>
                    <p className="text-sm text-muted-foreground">{backup.size}</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleRestoreBackup(backup.id)}
                    disabled={isRestoring}
                  >
                    {isRestoring ? 'Restoring...' : 'Restore'}
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
