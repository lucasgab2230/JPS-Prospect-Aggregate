import { useState } from 'react';
import { useIsAdmin, useIsSuperAdmin } from '@/hooks/api';
import { useAdminDecisions, useAdminDecisionStats, useExportDecisions, useAdminUsers } from '@/hooks/api/useAdmin';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Download, Users, BarChart3, FileText, Settings } from 'lucide-react';
import { useError } from '@/hooks/useError';
import { GoNoGoDecision, UserWithStats } from '@/types/api';
import UserManagement from '@/components/UserManagement';

export default function AdminDecisions() {
  const isAdmin = useIsAdmin();
  const isSuperAdmin = useIsSuperAdmin();
  const { handleError } = useError();
  const [decisionFilter, setDecisionFilter] = useState<'go' | 'no-go' | 'all'>('all');
  const [selectedUserId, setSelectedUserId] = useState<number | undefined>();

  // Call hooks before any conditional returns
  const { data: decisionsData, isLoading: decisionsLoading } = useAdminDecisions({
    page: 1,
    per_page: 50,
    decision: decisionFilter === 'all' ? undefined : decisionFilter,
    user_id: selectedUserId,
  });

  const { data: statsData } = useAdminDecisionStats();
  const { data: usersData, isLoading: usersLoading } = useAdminUsers({ page: 1, per_page: 100 });
  const exportMutation = useExportDecisions();

  // Redirect if not admin
  if (!isAdmin) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">Access Denied</h1>
          <p className="text-gray-600">You need admin privileges to access this page.</p>
        </div>
      </div>
    );
  }

  const handleExport = async () => {
    try {
      const result = await exportMutation.mutateAsync();

      // Convert to CSV and download
      if (result.data?.decisions) {
        const headers = [
          // Decision fields
          'Decision ID', 'Decision', 'Reason', 'Decision Created At', 'Decision Updated At',

          // User fields
          'User ID', 'User Email', 'User Name',

          // Prospect identification
          'Prospect ID', 'Prospect Native ID',

          // Prospect basic info
          'Prospect Title', 'AI Enhanced Title', 'Description', 'Agency',

          // NAICS classification
          'NAICS Code', 'NAICS Description', 'NAICS Source',

          // Financial information
          'Estimated Value', 'Est Value Unit', 'Estimated Value Text',
          'Estimated Value Min', 'Estimated Value Max', 'Estimated Value Single',

          // Important dates
          'Release Date', 'Award Date', 'Award Fiscal Year',

          // Location information
          'Place City', 'Place State', 'Place Country',

          // Contract details
          'Contract Type', 'Set Aside',

          // Contact information
          'Primary Contact Email', 'Primary Contact Name',

          // Processing metadata
          'Loaded At', 'Ollama Processed At', 'Ollama Model Version',
          'Enhancement Status', 'Enhancement Started At', 'Enhancement User ID'
        ];

        const escapeCSV = (text: string) => `"${(text || '').replace(/"/g, '""')}"`;

        const csvContent = [
          headers.join(','),
          ...result.data.decisions.map(decision => [
            // Decision fields
            decision.decision_id,
            decision.decision,
            escapeCSV(decision.reason),
            decision.decision_created_at,
            decision.decision_updated_at,

            // User fields
            decision.user_id,
            decision.user_email,
            decision.user_name,

            // Prospect identification
            decision.prospect_id,
            escapeCSV(decision.prospect_native_id),

            // Prospect basic info
            escapeCSV(decision.prospect_title),
            escapeCSV(decision.prospect_ai_enhanced_title),
            escapeCSV(decision.prospect_description),
            escapeCSV(decision.prospect_agency),

            // NAICS classification
            escapeCSV(decision.prospect_naics),
            escapeCSV(decision.prospect_naics_description),
            escapeCSV(decision.prospect_naics_source),

            // Financial information
            escapeCSV(decision.prospect_estimated_value),
            escapeCSV(decision.prospect_est_value_unit),
            escapeCSV(decision.prospect_estimated_value_text),
            escapeCSV(decision.prospect_estimated_value_min),
            escapeCSV(decision.prospect_estimated_value_max),
            escapeCSV(decision.prospect_estimated_value_single),

            // Important dates
            decision.prospect_release_date,
            decision.prospect_award_date,
            decision.prospect_award_fiscal_year,

            // Location information
            escapeCSV(decision.prospect_place_city),
            escapeCSV(decision.prospect_place_state),
            escapeCSV(decision.prospect_place_country),

            // Contract details
            escapeCSV(decision.prospect_contract_type),
            escapeCSV(decision.prospect_set_aside),

            // Contact information
            escapeCSV(decision.prospect_primary_contact_email),
            escapeCSV(decision.prospect_primary_contact_name),

            // Processing metadata
            decision.prospect_loaded_at,
            decision.prospect_ollama_processed_at,
            escapeCSV(decision.prospect_ollama_model_version),
            escapeCSV(decision.prospect_enhancement_status),
            decision.prospect_enhancement_started_at,
            decision.prospect_enhancement_user_id
          ].join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `admin-decisions-export-${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      handleError(error, {
        context: { operation: 'exportDecisions' },
        fallbackMessage: 'Failed to export decisions'
      });
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
          <p className="text-gray-600 mt-2">View and manage all Go/No-Go decisions</p>
        </div>
        <Button onClick={handleExport} disabled={exportMutation.isPending}>
          <Download className="h-4 w-4 mr-2" />
          {exportMutation.isPending ? 'Exporting...' : 'Export All'}
        </Button>
      </div>

      {/* Statistics Cards */}
      {statsData?.data && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Decisions</CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{statsData.data.overall.total_decisions}</div>
              <p className="text-xs text-muted-foreground">
                {statsData.data.overall.recent_decisions_30d} in last 30 days
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Go Decisions</CardTitle>
              <BarChart3 className="h-4 w-4 text-green-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {statsData.data.overall.go_decisions}
              </div>
              <p className="text-xs text-muted-foreground">
                {statsData.data.overall.go_percentage}% of all decisions
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">No-Go Decisions</CardTitle>
              <BarChart3 className="h-4 w-4 text-red-600" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">
                {statsData.data.overall.nogo_decisions}
              </div>
              <p className="text-xs text-muted-foreground">
                {(100 - statsData.data.overall.go_percentage).toFixed(1)}% of all decisions
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Users</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{statsData.data.by_user.length}</div>
              <p className="text-xs text-muted-foreground">With decisions</p>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="decisions" className="space-y-4">
        <TabsList>
          <TabsTrigger value="decisions">All Decisions</TabsTrigger>
          <TabsTrigger value="users">User Analytics</TabsTrigger>
          {isSuperAdmin && (
            <TabsTrigger value="user-management">
              <Settings className="w-4 h-4 mr-2" />
              User Management
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="decisions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Decision Management</CardTitle>
              <CardDescription>
                View and filter all Go/No-Go decisions across all users
              </CardDescription>

              <div className="flex space-x-4">
                <Select value={decisionFilter} onValueChange={(value: 'go' | 'no-go' | 'all') => setDecisionFilter(value)}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Filter by decision" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Decisions</SelectItem>
                    <SelectItem value="go">Go Only</SelectItem>
                    <SelectItem value="no-go">No-Go Only</SelectItem>
                  </SelectContent>
                </Select>

                <Select
                  value={selectedUserId?.toString() || 'all'}
                  onValueChange={(value) => setSelectedUserId(value === 'all' ? undefined : parseInt(value))}
                >
                  <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="Filter by user" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Users</SelectItem>
                    {usersData?.data?.users.map((user) => (
                      <SelectItem key={user.id} value={user.id.toString()}>
                        {user.first_name} ({user.email})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent>
              {decisionsLoading ? (
                <div>Loading decisions...</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Prospect</TableHead>
                      <TableHead>Decision</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Date</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {decisionsData?.data?.decisions.map((decision: GoNoGoDecision) => (
                      <TableRow key={decision.id}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{decision.user?.first_name}</div>
                            <div className="text-sm text-gray-500">{decision.user?.email}</div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="max-w-xs">
                            <div className="font-medium truncate" title={decision.prospect_title}>
                              {decision.prospect_title}
                            </div>
                            <div className="text-sm text-gray-500">{decision.prospect_id}</div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={decision.decision === 'go' ? 'default' : 'destructive'}>
                            {decision.decision.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-xs">
                          <div className="truncate" title={decision.reason || ''}>
                            {decision.reason || 'No reason provided'}
                          </div>
                        </TableCell>
                        <TableCell>
                          {new Date(decision.created_at).toLocaleDateString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>User Analytics</CardTitle>
              <CardDescription>
                View user activity and decision statistics
              </CardDescription>
            </CardHeader>
            <CardContent>
              {usersLoading ? (
                <div>Loading user data...</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Total Decisions</TableHead>
                      <TableHead>Go Decisions</TableHead>
                      <TableHead>No-Go Decisions</TableHead>
                      <TableHead>Member Since</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {usersData?.data?.users.map((user: UserWithStats) => (
                      <TableRow key={user.id}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{user.first_name}</div>
                            <div className="text-sm text-gray-500">{user.email}</div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                            {user.role.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell>{user.decision_stats.total_decisions}</TableCell>
                        <TableCell>
                          <span className="text-green-600 font-medium">
                            {user.decision_stats.go_decisions}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className="text-red-600 font-medium">
                            {user.decision_stats.nogo_decisions}
                          </span>
                        </TableCell>
                        <TableCell>
                          {new Date(user.created_at).toLocaleDateString()}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {isSuperAdmin && (
          <TabsContent value="user-management">
            <UserManagement />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
