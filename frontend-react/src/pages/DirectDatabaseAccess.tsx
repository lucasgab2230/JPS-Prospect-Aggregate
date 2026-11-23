import { useState } from 'react';
import { DataPageLayout } from '@/components/layout';
import { useExecuteQuery } from '@/hooks/api/useDatabase';
import { DatabaseOperations } from '@/components/DatabaseOperations';
import { Button } from '@/components/ui';
import { QueryResult } from '@/types';

export default function DirectDatabaseAccess() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { mutate: executeQuery, isPending: isLoading } = useExecuteQuery();

  const handleExecute = () => {
    if (!query.trim()) {
      setError('Please enter a query.');
      return;
    }
    executeQuery({ query: query.trim() }, {
      onSuccess: (data: QueryResult) => {
        setResults(data);
        setError(null);
      },
      onError: (error: Error) => {
        setResults(null);
        setError(error.message || 'Query execution failed');
      }
    });
  };

  const handleClear = () => {
    setQuery('');
    setResults(null);
    setError(null);
  };

  return (
    <DataPageLayout
      title="Direct Database Access"
      subtitle="Execute SQL queries directly on the database"
      data={results}
      loading={isLoading}
      error={error as Error | null}
      renderHeader={() => (
        <div role="alert" className="p-4 border border-yellow-400 bg-yellow-50 text-yellow-700 dark:border-yellow-500 dark:bg-yellow-900/20 dark:text-yellow-300 rounded">
          <h4 className="font-bold mb-1">Warning: Advanced Feature</h4>
          <p>
            This page allows direct SQL queries to the database. Use with caution as improper queries may damage your data.
            SELECT queries are recommended. Avoid INSERT, UPDATE, or DELETE operations unless you know what you're doing.
          </p>
        </div>
      )}
    >
      <div className="space-y-4">
        <div>
          <label htmlFor="query" className="block text-sm font-medium mb-1">
            SQL Query
          </label>
          <textarea
            id="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="SELECT * FROM proposals LIMIT 10;"
            className="h-32 font-mono w-full p-2 border border-gray-200 dark:border-gray-700 rounded resize-none focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>

        <div className="flex gap-2">
          <Button
            onClick={handleExecute}
            disabled={!query.trim() || isLoading}
          >
            {isLoading ? 'Executing...' : 'Execute Query'}
          </Button>
          <Button
            variant="outline"
            onClick={handleClear}
            disabled={!query && !results}
          >
            Clear
          </Button>
        </div>

        {results && (
          <div className="mt-4">
            <h3 className="text-lg font-semibold mb-2">Results</h3>
            <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded overflow-auto max-h-96 whitespace-pre-wrap break-all">
              {JSON.stringify(results, null, 2)}
            </pre>
          </div>
        )}

        <div>
          <DatabaseOperations />
        </div>
      </div>
    </DataPageLayout>
  );
}
