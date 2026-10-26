import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorDisplay } from '@/components/ui/ErrorDisplay';
import { Badge } from '@/components/ui/badge';
import { Play, AlertTriangle, Info } from 'lucide-react';
import { useTools } from '@/hooks/api/useTools';
import { ScriptExecutor } from './ScriptExecutor';
import type { Script } from '@/types/tools';

export function ToolsTab() {
  const { scripts, isLoading, error } = useTools();
  const [selectedScript, setSelectedScript] = useState<Script | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return <ErrorDisplay error={error} />;
  }

  const renderScriptCard = (script: Script) => (
    <Card
      key={script.id}
      className="cursor-pointer hover:shadow-lg transition-shadow"
      onClick={() => setSelectedScript(script)}
    >
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg flex items-center gap-2">
              {script.name}
              {script.dangerous && (
                <Badge variant="destructive" className="text-xs">
                  <AlertTriangle className="w-3 h-3 mr-1" />
                  Dangerous
                </Badge>
              )}
            </CardTitle>
            <CardDescription className="mt-1">{script.description}</CardDescription>
          </div>
          <Button size="sm" variant="ghost" className="ml-2">
            <Play className="w-4 h-4" />
          </Button>
        </div>
      </CardHeader>
      {script.parameters && script.parameters.length > 0 && (
        <CardContent>
          <div className="flex items-center gap-1 text-sm text-muted-foreground">
            <Info className="w-3 h-3" />
            <span>{script.parameters.length} parameter{script.parameters.length > 1 ? 's' : ''}</span>
          </div>
        </CardContent>
      )}
    </Card>
  );

  const renderCategory = (category: string, categoryScripts: Script[]) => (
    <div key={category} className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">{category}</h3>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {categoryScripts.map(renderScriptCard)}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Script Executor Modal */}
      {selectedScript && (
        <ScriptExecutor
          script={selectedScript}
          onClose={() => setSelectedScript(null)}
        />
      )}

      {/* Scripts List */}
      <div className="space-y-8">
        {scripts && Object.entries(scripts).map(([category, categoryScripts]) =>
          renderCategory(category, categoryScripts)
        )}
      </div>

      {/* Empty State */}
      {(!scripts || Object.keys(scripts).length === 0) && (
        <div className="text-center py-12">
          <p className="text-gray-500">No scripts available</p>
        </div>
      )}
    </div>
  );
}
