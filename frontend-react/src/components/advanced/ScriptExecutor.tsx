import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { Play, X, AlertTriangle, CheckCircle, XCircle, Terminal } from 'lucide-react';
import { useConfirmationDialog } from '@/components/ui/ConfirmationDialog';
import { useExecuteScript } from '@/hooks/api/useTools';
import type { Script, ScriptParameter } from '@/types/tools';

interface ScriptExecutorProps {
  script: Script;
  onClose: () => void;
}

export function ScriptExecutor({ script, onClose }: ScriptExecutorProps) {
  const { confirm, ConfirmationDialog } = useConfirmationDialog();
  const [parameters, setParameters] = useState<Record<string, string | number | boolean>>({});
  const [output, setOutput] = useState<string[]>([]);
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'failed' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const executeScript = useExecuteScript();

  // Initialize default parameters
  useEffect(() => {
    if (script.parameters) {
      const defaults: Record<string, any> = {};
      script.parameters.forEach(param => {
        if (param.default !== undefined) {
          defaults[param.name] = param.default;
        }
      });
      setParameters(defaults);
    }
  }, [script]);

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const handleParameterChange = (name: string, value: string | number | boolean) => {
    setParameters(prev => ({ ...prev, [name]: value }));
  };

  const handleExecute = async () => {
    // Confirm dangerous operations
    if (script.requires_confirmation) {
      const confirmed = await confirm({
        title: 'Confirm Script Execution',
        description: `Are you sure you want to run "${script.name}"?`,
        details: script.dangerous ? [
          'This script performs dangerous operations.',
          'Make sure you understand what it does before proceeding.'
        ] : [],
        confirmLabel: 'Execute Script',
        variant: script.dangerous ? 'destructive' : 'default'
      });

      if (!confirmed) return;
    }

    // Reset state
    setOutput([]);
    setError(null);
    setStatus('running');

    try {
      // Execute script
      const result = await executeScript.mutateAsync({
        scriptId: script.id,
        parameters
      });

      if (result.data?.execution_id) {
        // Set up SSE connection for streaming output
        const eventSource = new EventSource(`/api/tools/stream/${result.data.execution_id}`);
        eventSourceRef.current = eventSource;

        eventSource.onmessage = (event) => {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'output':
              setOutput(prev => [...prev, data.line]);
              break;
            case 'status':
              setStatus(data.status);
              break;
            case 'error':
              setError(data.message);
              setStatus('error');
              break;
            case 'done':
              eventSource.close();
              break;
          }
        };

        eventSource.onerror = () => {
          setError('Connection lost');
          setStatus('error');
          eventSource.close();
        };
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute script');
      setStatus('failed');
    }
  };

  const handleClose = () => {
    // Close event source if active
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    onClose();
  };

  const renderParameter = (param: ScriptParameter) => {
    const value = parameters[param.name] ?? '';

    switch (param.type) {
      case 'boolean':
        return (
          <div key={param.name} className="flex items-center justify-between space-x-2">
            <Label htmlFor={param.name} className="flex-1">
              {param.description || param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Switch
              id={param.name}
              checked={value === 'true' || value === true}
              onCheckedChange={(checked) => handleParameterChange(param.name, checked ? 'true' : 'false')}
            />
          </div>
        );

      case 'choice':
        return (
          <div key={param.name} className="space-y-2">
            <Label htmlFor={param.name}>
              {param.description || param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Select value={String(value)} onValueChange={(val) => handleParameterChange(param.name, val)}>
              <SelectTrigger id={param.name}>
                <SelectValue placeholder="Select an option" />
              </SelectTrigger>
              <SelectContent>
                {param.choices?.map(choice => (
                  <SelectItem key={choice} value={choice}>{choice}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        );

      case 'number':
        return (
          <div key={param.name} className="space-y-2">
            <Label htmlFor={param.name}>
              {param.description || param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={param.name}
              type="number"
              value={String(value)}
              onChange={(e) => handleParameterChange(param.name, e.target.value)}
              placeholder={param.default ? `Default: ${param.default}` : undefined}
            />
          </div>
        );

      default:
        return (
          <div key={param.name} className="space-y-2">
            <Label htmlFor={param.name}>
              {param.description || param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={param.name}
              type="text"
              value={String(value)}
              onChange={(e) => handleParameterChange(param.name, e.target.value)}
              placeholder={param.default ? `Default: ${param.default}` : undefined}
            />
          </div>
        );
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <LoadingSpinner className="w-4 h-4" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
      case 'error':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Terminal className="w-4 h-4" />;
    }
  };

  return (
    <>
      <Dialog open onOpenChange={handleClose}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {script.name}
              {script.dangerous && (
                <Badge variant="destructive" className="text-xs">
                  <AlertTriangle className="w-3 h-3 mr-1" />
                  Dangerous
                </Badge>
              )}
            </DialogTitle>
            <DialogDescription>{script.description}</DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-4 py-4">
            {/* Parameters */}
            {script.parameters && script.parameters.length > 0 && (
              <div className="space-y-4">
                <h4 className="font-medium text-sm">Parameters</h4>
                <div className="space-y-3">
                  {script.parameters.map(renderParameter)}
                </div>
              </div>
            )}

            {/* Output */}
            {(output.length > 0 || status !== 'idle') && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <h4 className="font-medium text-sm">Output</h4>
                  {getStatusIcon()}
                  <Badge variant={status === 'completed' ? 'default' : status === 'running' ? 'secondary' : 'destructive'}>
                    {status}
                  </Badge>
                </div>
                <div
                  ref={outputRef}
                  className="bg-gray-900 text-gray-100 rounded-lg p-4 font-mono text-sm overflow-y-auto max-h-96"
                >
                  {output.map((line, index) => (
                    <div key={index} className="whitespace-pre-wrap">{line}</div>
                  ))}
                  {status === 'running' && output.length === 0 && (
                    <div className="text-gray-400">Waiting for output...</div>
                  )}
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              <X className="w-4 h-4 mr-2" />
              Close
            </Button>
            <Button
              onClick={handleExecute}
              disabled={status === 'running'}
              variant={script.dangerous ? 'destructive' : 'default'}
            >
              {status === 'running' ? (
                <>
                  <LoadingSpinner className="w-4 h-4 mr-2" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Execute
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {ConfirmationDialog}
    </>
  );
}
