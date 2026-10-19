import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { useTimezoneDate } from '@/hooks/useTimezoneDate';
import { useEnhancementQueueService } from '@/hooks/api/useEnhancementQueueService';
import { getStatusColor } from '@/utils/statusUtils';
import { PlayIcon, StopIcon, ChevronDownIcon, ChevronRightIcon } from '@radix-ui/react-icons';

type EnhancementType = 'all' | 'values' | 'naics' | 'titles' | 'set_asides';

export function AIEnrichment() {
  const [enhancementType, setEnhancementType] = useState<EnhancementType>('all');
  const [skipExisting, setSkipExisting] = useState<'skip' | 'fill'>('skip');
  const [expandedOutputs, setExpandedOutputs] = useState<Set<number>>(new Set());

  const { formatLastProcessed, formatUserDate } = useTimezoneDate();

  const {
    enrichmentStatus: status,
    iterativeProgress: progress,
    llmOutputs,
    isLoadingEnrichment: isLoadingStatus,
    isLoadingLLMOutputs: isLoadingOutputs,
    startIterative,
    stopIterative,
    isStartingIterative,
    isStoppingIterative
  } = useEnhancementQueueService({
    llmOutputsType: enhancementType
  });

  const isProcessing = progress?.status === 'processing' || progress?.status === 'stopping';

  const handleStart = () => {
    startIterative({
      enhancement_type: enhancementType,
      skip_existing: skipExisting === 'skip'
    });
  };

  const handleStop = () => {
    stopIterative();
  };

  // Removed local formatDate function - using timezone-aware formatting

  const toggleOutputExpanded = (outputId: number) => {
    setExpandedOutputs(prev => {
      const newSet = new Set(prev);
      if (newSet.has(outputId)) {
        newSet.delete(outputId);
      } else {
        newSet.add(outputId);
      }
      return newSet;
    });
  };


  return (
    <div className="space-y-6">
      {/* Top row: Status Overview and Controls side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Status Overview - Takes up 3/4 of the space */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="flex items-center">
              AI Enrichment Status
              {status?.total_prospects && (
                <div className="ml-auto text-sm font-normal text-gray-600">
                  {status.processed_prospects.toLocaleString()} of {status.total_prospects.toLocaleString()} processed
                </div>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingStatus ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-600"></div>
              </div>
            ) : status ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* NAICS Coverage */}
                <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                  <h4 className="font-semibold text-blue-800 mb-2">NAICS Classification</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span>Original:</span>
                      <span className="font-medium">{status.naics_coverage.original.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>AI Classified:</span>
                      <span className="font-medium text-blue-700">{status.naics_coverage.llm_inferred.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between border-t border-blue-300 pt-1 font-medium">
                      <span>Coverage:</span>
                      <span>{status.naics_coverage.total_percentage.toFixed(1)}%</span>
                    </div>
                  </div>
                </div>

                {/* Value Parsing */}
                <div className="bg-green-50 p-4 rounded-lg border border-green-200">
                  <h4 className="font-semibold text-green-800 mb-2">Value Parsing</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span>Parsed Values:</span>
                      <span className="font-medium text-green-700">{status.value_parsing.parsed_count.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between border-t border-green-300 pt-1 font-medium">
                      <span>Coverage:</span>
                      <span>{status.value_parsing.total_percentage.toFixed(1)}%</span>
                    </div>
                  </div>
                </div>

                {/* Set-Aside Standardization */}
                <div className="bg-orange-50 p-4 rounded-lg border border-orange-200">
                  <h4 className="font-semibold text-orange-800 mb-2">Set-Aside Standardization</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span>Standardized Set-Asides:</span>
                      <span className="font-medium text-orange-700">{status.set_aside_standardization.standardized_count.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between border-t border-orange-300 pt-1 font-medium">
                      <span>Coverage:</span>
                      <span>{status.set_aside_standardization.total_percentage.toFixed(1)}%</span>
                    </div>
                  </div>
                </div>

                {/* Title Enhancement */}
                <div className="bg-purple-50 p-4 rounded-lg border border-purple-200">
                  <h4 className="font-semibold text-purple-800 mb-2">Title Enhancement</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span>Enhanced Titles:</span>
                      <span className="font-medium text-purple-700">{status.title_enhancement?.enhanced_count?.toLocaleString() || '0'}</span>
                    </div>
                    <div className="flex justify-between border-t border-purple-300 pt-1 font-medium">
                      <span>Coverage:</span>
                      <span>{status.title_enhancement?.total_percentage?.toFixed(1) || '0.0'}%</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-red-600">Failed to load AI enrichment status</div>
            )}

            {status?.last_processed && (
              <div className="mt-4 text-sm text-gray-600 border-t pt-4">
                <div className="flex justify-between">
                  <span>Last processed:</span>
                  <span>{formatLastProcessed(status.last_processed)}</span>
                </div>
                {status.model_version && (
                  <div className="flex justify-between">
                    <span>Model version:</span>
                    <span className="font-mono">{status.model_version}</span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
        {/* Right Column: AI Enrichment Controls - Takes up 1/4 of the space */}
        <Card>
          <CardHeader>
            <CardTitle>Controls</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Enhancement Type Selection */}
              <div className="space-y-2">
                <Label htmlFor="enhancement-type">Enhancement Type</Label>
                <Select
                  value={enhancementType}
                  onValueChange={(value: EnhancementType) => setEnhancementType(value)}
                  disabled={isProcessing}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Enhancements</SelectItem>
                    <SelectItem value="values">Value Parsing</SelectItem>
                    <SelectItem value="naics">NAICS Classification</SelectItem>
                    <SelectItem value="titles">Title Enhancement</SelectItem>
                    <SelectItem value="set_asides">Set-Aside Standardization</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Skip Existing Selection */}
              <div className="space-y-2">
                <Label>Processing Mode</Label>
                <div className="space-y-2">
                  <label className="flex items-center space-x-2">
                    <input
                      type="radio"
                      name="processing-mode"
                      value="skip"
                      checked={skipExisting === 'skip'}
                      onChange={(e) => setSkipExisting(e.target.value as 'skip' | 'fill')}
                      disabled={isProcessing}
                      className="h-4 w-4 text-blue-600"
                    />
                    <span className="text-sm font-normal cursor-pointer">
                      Skip existing AI data
                    </span>
                  </label>
                  <label className="flex items-center space-x-2">
                    <input
                      type="radio"
                      name="processing-mode"
                      value="fill"
                      checked={skipExisting === 'fill'}
                      onChange={(e) => setSkipExisting(e.target.value as 'skip' | 'fill')}
                      disabled={isProcessing}
                      className="h-4 w-4 text-blue-600"
                    />
                    <span className="text-sm font-normal cursor-pointer">
                      Replace existing AI data
                    </span>
                  </label>
                </div>
              </div>

              <div className="space-y-2">
                {!isProcessing ? (
                  <Button
                    onClick={handleStart}
                    disabled={isStartingIterative}
                    className="w-full bg-green-600 hover:bg-green-700 text-white"
                  >
                    <PlayIcon className="mr-2 h-4 w-4 text-white" />
                    Start Enhancement
                  </Button>
                ) : (
                  <Button
                    onClick={handleStop}
                    disabled={isStoppingIterative || progress?.status === 'stopping'}
                    variant="destructive"
                    className="w-full bg-red-600 hover:bg-red-700 text-white disabled:bg-gray-400 disabled:text-gray-200"
                  >
                    <StopIcon className="mr-2 h-4 w-4 text-white" />
                    {progress?.status === 'stopping' ? 'Stopping...' : 'Stop Enhancement'}
                  </Button>
                )}
              </div>

              {/* Progress Display */}
              {progress && (progress.status === 'processing' || progress.processed > 0) && (
                <div className="space-y-3">
                  {/* Progress Bar */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className={`font-medium ${getStatusColor(progress.status)}`}>
                        Status: {progress.status.charAt(0).toUpperCase() + progress.status.slice(1)}
                      </span>
                      <span className="text-gray-600">
                        {progress.processed.toLocaleString()} / {progress.total.toLocaleString()}
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div
                        className="bg-blue-600 h-3 rounded-full transition-all duration-500"
                        style={{ width: `${progress.percentage}%` }}
                      />
                    </div>
                    <div className="text-center text-sm font-medium">
                      {progress.percentage.toFixed(1)}% Complete
                    </div>
                  </div>

                  {/* Current Processing Info */}
                  {progress.current_prospect && progress.status === 'processing' && (
                    <div className="bg-blue-50 border border-blue-200 p-3 rounded-lg">
                      <div className="text-sm">
                        <span className="font-medium text-blue-800">Currently processing: </span>
                        <span className="text-blue-700">{progress.current_prospect.title}</span>
                      </div>
                    </div>
                  )}

                  {/* Errors */}
                  {progress?.errors && progress.errors.length > 0 && (
                    <div className="bg-red-50 border border-red-200 p-3 rounded-lg">
                      <div className="text-sm text-red-800">
                        <span className="font-medium">Errors encountered: </span>
                        {progress?.errors?.length || 0} prospect(s) failed
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Error Messages */}
              {progress?.error_message && (
                <div className="text-red-600 text-sm">
                  Error: {progress.error_message}
                </div>
              )}

              {/* Success Messages */}
              {progress?.status === 'completed' && (
                <div className="bg-green-50 border border-green-200 p-3 rounded-lg">
                  <div className="text-green-800 font-medium">Enhancement completed successfully!</div>
                  <div className="text-green-700 text-sm mt-1">
                    Processed all {progress.processed} available records
                  </div>
                </div>
              )}

              {progress?.status === 'stopped' && (
                <div className="bg-yellow-50 border border-yellow-200 p-3 rounded-lg">
                  <div className="text-yellow-800 font-medium">Enhancement stopped</div>
                  <div className="text-yellow-700 text-sm mt-1">
                    Processed {progress.processed} records before stopping
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Full width LLM Output Log below */}
      <Card>
        <CardHeader>
          <CardTitle>LLM Output Log</CardTitle>
        </CardHeader>
        <CardContent>
            {isLoadingOutputs ? (
              <div className="flex items-center justify-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-600"></div>
              </div>
            ) : llmOutputs && llmOutputs.length > 0 ? (
              <div className="space-y-3 max-h-[700px] overflow-y-auto">
                {llmOutputs.map((output) => {
                  const isExpanded = expandedOutputs.has(output.id);
                  return (
                    <div key={output.id} className={`border rounded-lg p-3 ${output.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                      {/* Header with basic info */}
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="p-0 h-auto"
                              onClick={() => toggleOutputExpanded(output.id)}
                            >
                              {isExpanded ? <ChevronDownIcon className="h-4 w-4" /> : <ChevronRightIcon className="h-4 w-4" />}
                            </Button>
                            <div className="text-sm">
                              <span className="font-medium">{output.prospect_title || 'Unknown Prospect'}</span>
                              <span className="text-gray-500 ml-2">({output.enhancement_type})</span>
                            </div>
                          </div>

                          {/* Quick summary of result when collapsed */}
                          {!isExpanded && output.parsed_result && (
                            <div className="ml-6 mt-1 text-xs text-gray-600">
                              {output.enhancement_type === 'naics' && 'code' in output.parsed_result && (
                                <span>NAICS: {String(output.parsed_result.code)} - {'description' in output.parsed_result ? String(output.parsed_result.description) : ''}</span>
                              )}
                              {output.enhancement_type === 'values' && 'single' in output.parsed_result && (
                                <span>Value: ${Number(output.parsed_result.single).toLocaleString()}</span>
                              )}
                              {output.enhancement_type === 'titles' && 'enhanced_title' in output.parsed_result && (
                                <span>Enhanced Title: {String(output.parsed_result.enhanced_title)}</span>
                              )}
                              {output.enhancement_type === 'set_asides' && 'standardized_set_aside' in output.parsed_result && (
                                <span>Set-Aside: {String(output.parsed_result.standardized_set_aside)}</span>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {output.processing_time && (
                            <span className="text-xs text-gray-500">{output.processing_time.toFixed(2)}s</span>
                          )}
                          <span className="text-xs text-gray-500">{formatUserDate(output.timestamp, 'datetime')}</span>
                        </div>
                      </div>

                      {/* Expandable details */}
                      {isExpanded && (
                        <div className="mt-3 space-y-2">
                          {/* LLM Response */}
                          <div className="text-sm">
                            <span className="font-medium">Response:</span>
                            <pre className="mt-1 p-2 bg-white rounded border text-xs overflow-x-auto max-h-32 overflow-y-auto">
                              {output.response}
                            </pre>
                          </div>

                          {/* Parsed Result */}
                          {output.parsed_result && (
                            <div className="text-sm">
                              <span className="font-medium">Parsed Result:</span>
                              <pre className="mt-1 p-2 bg-white rounded border text-xs overflow-x-auto">
                                {JSON.stringify(output.parsed_result, null, 2)}
                              </pre>
                            </div>
                          )}

                          {/* Error Message */}
                          {output.error_message && (
                            <div className="text-sm text-red-600">
                              <span className="font-medium">Error:</span> {output.error_message}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                No LLM outputs yet. Start an enhancement to see outputs here.
              </div>
            )}
          </CardContent>
      </Card>
    </div>
  );
}
