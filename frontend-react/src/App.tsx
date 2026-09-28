import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Navigation } from './components/layout';
import { AuthProvider } from './components/AuthProvider';
import { AuthGuard } from './components/AuthGuard';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProspectEnhancementProvider } from './contexts/ProspectEnhancementContext';
import { TimezoneProvider } from './contexts/TimezoneContext';
import { ToastProvider } from './contexts/ToastContext';
import { useAuth } from './components/AuthProvider';

// Lazy load pages
const Prospects = lazy(() => import('./pages/Prospects'));
const DataSources = lazy(() => import('./pages/DataSources'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const DirectDatabaseAccess = lazy(() => import('./pages/DirectDatabaseAccess'));
const Advanced = lazy(() => import('./pages/Advanced'));
const AdminDecisions = lazy(() => import('./pages/AdminDecisions'));

// Loading fallback - replaced complex skeleton with simple text
const PageSkeleton = () => <div className="flex justify-center items-center min-h-[80vh] text-xl text-muted-foreground">Loading page...</div>;

// Create a client with optimized defaults for auth queries
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Global defaults for all queries
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 minutes for most data
    },
  },
});

// Wrapper component to pass user data to TimezoneProvider
function AppWithProviders() {
  const { user } = useAuth();

  return (
    <TimezoneProvider user={user}>
      <ToastProvider>
        <ProspectEnhancementProvider>
          <Router>
            <AuthGuard>
              <div className="min-h-screen bg-background transition-colors duration-200">
                <Navigation />
                <Suspense fallback={<PageSkeleton />}>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/prospects" element={<Prospects />} />
                    <Route path="/data-sources" element={<DataSources />} />
                    <Route path="/database" element={<DirectDatabaseAccess />} />
                    <Route path="/advanced" element={<Advanced />} />
                    <Route path="/admin" element={<AdminDecisions />} />
                    <Route path="*" element={<div>Page Not Found</div>} />
                  </Routes>
                </Suspense>
              </div>
            </AuthGuard>
          </Router>
        </ProspectEnhancementProvider>
      </ToastProvider>
    </TimezoneProvider>
  );
}

function App() {
  // App component loaded
  // Effect to toggle .dark class on <html> based on OS/browser preference
  useEffect(() => {
    // Ensure the .dark class is not present if we're forcing light mode
    document.documentElement.classList.remove('dark');
  }, []);

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <AppWithProviders />
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
