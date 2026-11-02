import { flexRender, Table as ReactTable } from '@tanstack/react-table';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Prospect } from '@/types/prospects';

interface ProspectTableProps {
  table: ReactTable<Prospect>;
  prospects: Prospect[];
  isLoading: boolean;
  isFetching: boolean;
  onRowClick: (prospect: Prospect) => void;
}

export function ProspectTable({
  table,
  prospects,
  isLoading,
  isFetching,
  onRowClick
}: ProspectTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="text-sm text-gray-600">Loading prospects...</p>
        </div>
      </div>
    );
  }

  if (!prospects || prospects.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <p className="text-lg font-medium text-gray-900 mb-2">No prospects found</p>
          <p className="text-sm text-gray-600">Try adjusting your filters or check back later.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`h-[464px] overflow-y-auto overflow-x-auto rounded-lg border border-gray-200 shadow-sm transition-opacity duration-500 ease-in-out ${isFetching && !isLoading ? 'opacity-80' : 'opacity-100'}`}>
      <Table className="min-w-full divide-y divide-gray-200 table-fixed">
        {/* TableHeader with a softer, custom shadow */}
        <TableHeader className="sticky top-0 z-10 bg-gray-50 shadow-[0_2px_8px_rgba(0,0,0,0.08)]">
          {table.getHeaderGroups().map(headerGroup => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <TableHead
                  key={header.id}
                  className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider whitespace-nowrap"
                  style={{ width: header.getSize() !== 0 ? header.getSize() : undefined }}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody className="bg-white divide-y divide-gray-200">
          {table.getRowModel().rows.map((row, rowIndex) => {
            const isRecentlyUpdated = false; // Animation removed for performance

            return (
              <TableRow
                key={row.id}
                className={`transition-all duration-300 ease-in-out hover:bg-gray-100 cursor-pointer ${
                  rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'
                } data-[state=selected]:bg-blue-50 data-[state=selected]:hover:bg-blue-100 ${
                  isRecentlyUpdated ? 'animate-pulse bg-gradient-to-r from-green-50 to-blue-50 border-l-4 border-l-blue-500 shadow-lg scale-[1.01]' : ''
                }`}
                onClick={() => onRowClick(row.original)}
                style={{
                  animation: isRecentlyUpdated ? 'highlightUpdate 2s ease-in-out' : undefined
                }}
              >
                {row.getVisibleCells().map(cell => (
                  <TableCell
                    key={cell.id}
                    className="px-6 py-4 whitespace-nowrap text-sm text-gray-800 align-top overflow-hidden"
                    style={{
                      width: cell.column.getSize() !== 0 ? cell.column.getSize() : undefined,
                      maxWidth: cell.column.getSize() !== 0 ? cell.column.getSize() : undefined
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
