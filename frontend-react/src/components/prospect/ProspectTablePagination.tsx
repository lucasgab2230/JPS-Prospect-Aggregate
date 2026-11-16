import { Button } from "@/components/ui/button";

interface ProspectTablePaginationProps {
  currentPage: number;
  totalPages: number;
  total: number;
  itemsPerPage: number;
  onPageChange: (page: number) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
}

export function ProspectTablePagination({
  currentPage,
  totalPages,
  total,
  itemsPerPage,
  onPageChange,
  onPreviousPage,
  onNextPage
}: ProspectTablePaginationProps) {
  if (totalPages <= 1) return null;

  const renderPaginationItems = () => {
    const pageItems = [];

    // Previous Button
    pageItems.push(
      <Button
        key="prev"
        variant="outline"
        size="sm"
        onClick={onPreviousPage}
        disabled={currentPage === 1}
        className="h-8 px-2 sm:px-3 flex items-center gap-1"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
          <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
        <span className="hidden sm:inline">Previous</span>
      </Button>
    );

    // Page numbers logic
    if (totalPages <= 5) { // Show all pages if 5 or less
      for (let i = 1; i <= totalPages; i++) {
        pageItems.push(
          <Button
            key={i}
            variant={currentPage === i ? "default" : "outline"}
            size="sm"
            onClick={() => onPageChange(i)}
            className="h-8 min-w-[2rem] px-2"
          >
            {i}
          </Button>
        );
      }
    } else {
      // First page
      pageItems.push(
        <Button
          key={1}
          variant={currentPage === 1 ? "default" : "outline"}
          size="sm"
          onClick={() => onPageChange(1)}
          className="h-8 min-w-[2.5rem] px-3"
        >
          1
        </Button>
      );

      // Ellipsis after first page
      if (currentPage > 4) {
        pageItems.push(
          <span key="start-ellipsis" className="text-gray-400 px-2">...</span>
        );
      }

      // Middle pages - show fewer pages to avoid cramping
      let startPage, endPage;

      if (currentPage <= 3) {
        // Near the beginning
        startPage = 2;
        endPage = Math.min(4, totalPages - 1);
      } else if (currentPage >= totalPages - 2) {
        // Near the end
        startPage = Math.max(totalPages - 3, 2);
        endPage = totalPages - 1;
      } else {
        // In the middle
        startPage = currentPage - 1;
        endPage = currentPage + 1;
      }

      for (let i = startPage; i <= endPage; i++) {
        pageItems.push(
          <Button
            key={i}
            variant={currentPage === i ? "default" : "outline"}
            size="sm"
            onClick={() => onPageChange(i)}
            className="h-8 min-w-[2rem] px-2"
          >
            {i}
          </Button>
        );
      }

      // Ellipsis before last page
      if (currentPage < totalPages - 3) {
        pageItems.push(
          <span key="end-ellipsis" className="text-gray-400 px-2">...</span>
        );
      }

      // Last page
      pageItems.push(
        <Button
          key={totalPages}
          variant={currentPage === totalPages ? "default" : "outline"}
          size="sm"
          onClick={() => onPageChange(totalPages)}
          className="h-8 min-w-[2.5rem] px-3"
        >
          {totalPages}
        </Button>
      );
    }

    // Next Button
    pageItems.push(
      <Button
        key="next"
        variant="outline"
        size="sm"
        onClick={onNextPage}
        disabled={currentPage === totalPages}
        className="h-8 px-2 sm:px-3 flex items-center gap-1"
      >
        <span className="hidden sm:inline">Next</span>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
        </svg>
      </Button>
    );

    return pageItems;
  };

  return (
    <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
      <p className="text-sm font-medium text-gray-700">
        Showing <span className="font-semibold">{((currentPage - 1) * itemsPerPage + 1)}-{Math.min(currentPage * itemsPerPage, total)}</span> of <span className="font-semibold">{total.toLocaleString()}</span> results
      </p>
      <div className="flex items-center gap-2">
        {renderPaginationItems()}
      </div>
    </div>
  );
}
