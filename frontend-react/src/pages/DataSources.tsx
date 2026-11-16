import { DataPageLayout } from '@/components/layout';
import { useListDataSources, useDeleteDataSource } from '@/hooks/api/useDataSources';
import { DataSource } from '@/types';
import { Button } from '@/components/ui';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from '@/contexts/ToastContext';
import { useError } from '@/hooks/useError';

export default function DataSources() {
  const {
    data: dataSourcesData,
    isLoading,
    isError,
    error,
    refetch
  } = useListDataSources();

  const data = dataSourcesData?.data || [];
  const { showInfoToast } = useToast();
  const { handleError } = useError();

  const deleteMutation = useDeleteDataSource();

  const handleDelete = async (id: DataSource['id']) => {
    try {
      await deleteMutation.mutateAsync(id);
    } catch (err) {
      handleError(err, {
        context: { operation: 'deleteDataSource', dataSourceId: id },
        fallbackMessage: 'Failed to delete data source'
      });
    }
  };


  const pageError = isError ? (error as Error) : null;

  return (
    <DataPageLayout
      title="Data Sources"
      data={data ?? []}
      loading={isLoading}
      error={pageError}
      onRefresh={refetch}
    >
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : !data || data.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center">
                  No data sources found.
                </TableCell>
              </TableRow>
            ) : (
              data.map((source) => (
                <TableRow key={source.id}>
                  <TableCell className="font-medium">{source.name}</TableCell>
                  <TableCell>{source.type || 'N/A'}</TableCell>
                  <TableCell>{source.status || 'Unknown'}</TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => showInfoToast('Coming Soon', 'Edit functionality will be available in a future update.')}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDelete(source.id)}
                        disabled={deleteMutation.isPending && deleteMutation.variables === source.id}
                      >
                        {deleteMutation.isPending && deleteMutation.variables === source.id ? 'Deleting...' : 'Delete'}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </DataPageLayout>
  );
}
