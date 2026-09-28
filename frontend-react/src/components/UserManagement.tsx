import { useState } from 'react';
import { useIsSuperAdmin } from '@/hooks/api/useAuth';
import { useAdminUsers, useUpdateUserRole } from '@/hooks/api/useAdmin';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Search, Users, Shield, Crown } from 'lucide-react';
import { useError } from '@/hooks/useError';
import { User } from '@/types/api';
import { ConfirmationDialog } from '@/components/ui/ConfirmationDialog';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

export default function UserManagement() {
  const isSuperAdmin = useIsSuperAdmin();
  const { handleError } = useError();
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | 'user' | 'admin' | 'super_admin'>('all');
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    userId: number;
    newRole: 'user' | 'admin';
    userName: string;
  } | null>(null);

  // Hooks must be called unconditionally
  const { data: usersData, isLoading: usersLoading } = useAdminUsers({ page: 1, per_page: 100 });
  const updateUserRoleMutation = useUpdateUserRole();

  // Only allow super admins to access this component
  if (!isSuperAdmin) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">Access Denied</h1>
          <p className="text-gray-600">You need super admin privileges to access user management.</p>
        </div>
      </div>
    );
  }

  const users = usersData?.data?.users || [];

  // Filter users based on search and role filter
  const filteredUsers = users.filter((user: User) => {
    const matchesSearch = user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         user.first_name.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesRole = roleFilter === 'all' || user.role === roleFilter;

    return matchesSearch && matchesRole;
  });

  const handleRoleChange = (userId: number, newRole: 'user' | 'admin', userName: string) => {
    setConfirmDialog({
      isOpen: true,
      userId,
      newRole,
      userName
    });
  };

  const confirmRoleChange = async () => {
    if (!confirmDialog) return;

    try {
      await updateUserRoleMutation.mutateAsync({
        userId: confirmDialog.userId,
        data: { role: confirmDialog.newRole }
      });

      setConfirmDialog(null);
    } catch (error) {
      handleError(error, { fallbackMessage: 'Failed to update user role' });
    }
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'super_admin':
        return <Badge variant="destructive" className="bg-purple-600"><Crown className="w-3 h-3 mr-1" />Super Admin</Badge>;
      case 'admin':
        return <Badge variant="default" className="bg-blue-600"><Shield className="w-3 h-3 mr-1" />Admin</Badge>;
      case 'user':
        return <Badge variant="secondary"><Users className="w-3 h-3 mr-1" />User</Badge>;
      default:
        return <Badge variant="outline">{role}</Badge>;
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (usersLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            User Management
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <Input
                placeholder="Search users by email or name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={roleFilter} onValueChange={(value: 'all' | 'user' | 'admin' | 'super_admin') => setRoleFilter(value)}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Filter by role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                <SelectItem value="user">Users</SelectItem>
                <SelectItem value="admin">Admins</SelectItem>
                <SelectItem value="super_admin">Super Admins</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Last Login</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.map((user: User) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.email}</TableCell>
                    <TableCell>{user.first_name}</TableCell>
                    <TableCell>{getRoleBadge(user.role)}</TableCell>
                    <TableCell>{formatDate(user.created_at)}</TableCell>
                    <TableCell>
                      {user.last_login_at ? formatDate(user.last_login_at) : 'Never'}
                    </TableCell>
                    <TableCell>
                      {user.role === 'super_admin' ? (
                        <span className="text-sm text-gray-500">Protected</span>
                      ) : (
                        <Select
                          value={user.role}
                          onValueChange={(newRole: 'user' | 'admin') =>
                            handleRoleChange(user.id, newRole, user.first_name)
                          }
                          disabled={updateUserRoleMutation.isPending}
                        >
                          <SelectTrigger className="w-32">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="user">User</SelectItem>
                            <SelectItem value="admin">Admin</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {filteredUsers.length === 0 && (
            <div className="text-center py-8">
              <p className="text-gray-500">No users found matching your criteria.</p>
            </div>
          )}

          <div className="mt-4 text-sm text-gray-600">
            <p>Total Users: {users.length}</p>
            <p>Showing: {filteredUsers.length} users</p>
          </div>
        </CardContent>
      </Card>

      <ConfirmationDialog
        open={confirmDialog?.isOpen || false}
        onOpenChange={(open) => !open && setConfirmDialog(null)}
        onConfirm={confirmRoleChange}
        title="Confirm Role Change"
        description={
          confirmDialog ? (
            `Are you sure you want to change ${confirmDialog.userName}'s role to ${confirmDialog.newRole}?`
          ) : ''
        }
        confirmLabel="Update Role"
        loading={updateUserRoleMutation.isPending}
      />
    </div>
  );
}
