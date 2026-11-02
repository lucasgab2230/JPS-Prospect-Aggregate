/**
 * Get the appropriate CSS class for a given status
 */
export function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
    case 'success':
      return 'text-green-600';
    case 'failed':
    case 'error':
      return 'text-red-600';
    case 'working':
    case 'in_progress':
    case 'processing':
      return 'text-blue-600';
    case 'stopping':
      return 'text-orange-600';
    case 'pending':
    case 'stopped':
      return 'text-yellow-600';
    case 'ready':
      return 'text-gray-500';
    default:
      return 'text-gray-600';
  }
}

/**
 * Format scraper results for display
 */
export function formatScraperResults(results: Array<{
  source_name: string;
  source_id: number;
  status: string;
  duration: number;
  message?: string;
  error?: string;
}>, totalDuration: number): { successCount: number; failedCount: number; message: string } {
  const failedScrapers = results.filter(r => r.error);
  const successCount = results.length - failedScrapers.length;

  const message = `${successCount}/${results.length} scrapers completed successfully in ${totalDuration}s${
    failedScrapers.length > 0 ? `. ${failedScrapers.length} failed.` : ''
  }`;

  return {
    successCount,
    failedCount: failedScrapers.length,
    message,
  };
}
