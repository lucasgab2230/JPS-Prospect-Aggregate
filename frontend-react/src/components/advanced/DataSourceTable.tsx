import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { LoadingButton } from '@/components/ui/LoadingButton';
import { Button } from '@/components/ui';
import { useTimezoneDate } from '@/hooks/useTimezoneDate';
import { getStatusColor } from '@/utils/statusUtils';
import { DataSource } from '@/types';

interface DataSourceTableProps {
  dataSources: DataSource[];
  onRunScraper: (sourceId: number) => void;
  onClearData: (id: number, sourceName: string) => void;
  getScraperButtonState: (source: DataSource) => {
    buttonText: string;
    isLoading: boolean;
    isDisabled: boolean;
    isApiCallInProgress: boolean;
    isScraperWorking: boolean;
  };
  clearDataMutation: {
    isPending: boolean;
    variables: unknown;
  };
}


export function DataSourceTable({
  dataSources,
  onRunScraper,
  onClearData,
  getScraperButtonState,
  clearDataMutation,
}: DataSourceTableProps) {
  const { formatUserDate } = useTimezoneDate();

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Description</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Last Scraped</TableHead>
            <TableHead>Prospects</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {dataSources.map((source: DataSource) => {
            const { buttonText, isLoading, isDisabled, isScraperWorking } = getScraperButtonState(source);

            return (
              <TableRow key={source.id}>
                <TableCell className="font-medium">{source.name}</TableCell>
                <TableCell className="text-sm text-gray-600">{source.description}</TableCell>
                <TableCell>
                  <span className={`font-medium ${getStatusColor(source.status)}`}>
                    {(() => {
                      // Format status display
                      const statusText = source.status.charAt(0).toUpperCase() + source.status.slice(1);

                      // For completed status, show how long ago if we have last_checked
                      if (source.status === 'completed' && source.last_checked) {
                        const timeAgo = formatUserDate(source.last_checked, 'relative');
                        return `${statusText} (${timeAgo})`;
                      }

                      return statusText;
                    })()}
                    {isScraperWorking && (
                      <span className="ml-2 inline-flex h-2 w-2 rounded-full bg-blue-400 animate-pulse"></span>
                    )}
                  </span>
                </TableCell>
                <TableCell className="text-sm">
                  {source.last_scraped ? formatUserDate(source.last_scraped, 'datetime') : 'Never'}
                </TableCell>
                <TableCell>{source.prospectCount}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <LoadingButton
                      size="sm"
                      onClick={() => onRunScraper(source.id)}
                      isLoading={isLoading}
                      loadingText={buttonText}
                      disabled={isDisabled}
                      className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400"
                    >
                      {buttonText}
                    </LoadingButton>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onClearData(source.id, source.name)}
                      disabled={clearDataMutation.isPending && clearDataMutation.variables === source.id}
                      className="border-orange-500 text-orange-600 hover:bg-orange-50"
                    >
                      {clearDataMutation.isPending && clearDataMutation.variables === source.id ? 'Clearing...' : 'Clear Data'}
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
