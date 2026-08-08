import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Edit2, Trash2, Shield, Download, Users, Truck, Eye } from 'lucide-react';
import { toast } from 'sonner';

import { downloadCSV } from '@/utils/exportUtils';
import DashboardLayout from '@/components/layout/DashboardLayout';
import DataTable from '@/components/ui/DataTable';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { authStore } from '@/store/authStore';
import { userService, UserDTO } from '@/services/userService';
import { driverService } from '@/services/driverService';
import UserModal from './components/UserModal';

type UserRow = {
  id: string;
  kind: 'user' | 'driver';
  name: string;
  contact: string;
  role: string;
  status: string;
  raw: UserDTO | null;
};

export default function UserManagementPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  const currentUser = authStore.getUser();
  const isAdmin = currentUser?.role === 'Admin';

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserDTO | null>(null);

  const { data: users = [], isLoading, isError, error } = useQuery({
    queryKey: ['users'],
    queryFn: userService.getUsers,
  });

  const { data: driversRes, isLoading: isDriversLoading } = useQuery({
    queryKey: ['drivers', 'for-user-management'],
    queryFn: () => driverService.getAll(),
    enabled: isAdmin,
  });

  const rows: UserRow[] = [
    ...users.map((u): UserRow => ({
      id: u.id,
      kind: 'user',
      name: u.name || '',
      contact: u.email || '',
      role: u.role,
      status: u.status || 'Active',
      raw: u,
    })),
    ...(isAdmin ? (driversRes?.data || []).map((d): UserRow => ({
      id: d.id,
      kind: 'driver',
      name: `${d.first_name} ${d.last_name}`.trim(),
      contact: d.phone_primary || '',
      role: 'Driver',
      status: d.isActive ? 'Active' : 'Inactive',
      raw: null,
    })) : []),
  ];

  const createMutation = useMutation({
    mutationFn: userService.createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User created successfully');
      setIsModalOpen(false);
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.error?.message || 'Failed to create user');
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => userService.updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User updated successfully');
      setIsModalOpen(false);
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.error?.message || 'Failed to update user');
    }
  });

  const deleteMutation = useMutation({
    mutationFn: userService.deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('User deactivated successfully');
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.error?.message || 'Failed to deactivate user');
    }
  });

  const handleSaveUser = (data: any) => {
    if (editingUser) {
      updateMutation.mutate({ id: editingUser.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleEdit = (user: UserDTO) => {
    setEditingUser(user);
    setIsModalOpen(true);
  };

  const handleDelete = (user: UserDTO) => {
    if (confirm(`Are you sure you want to deactivate ${user.name}?`)) {
      deleteMutation.mutate(user.id);
    }
  };

  const filteredRows = rows.filter(r =>
    r.name?.toLowerCase().includes(search.toLowerCase()) ||
    r.contact?.toLowerCase().includes(search.toLowerCase())
  );

  const columns = [
    {
      header: 'Name',
      accessor: (row: UserRow) => (
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[#F5F5F7] flex items-center justify-center text-[#E8450F] font-bold text-xs border border-black/[0.05]">
            {row.name?.substring(0, 2).toUpperCase() || 'U'}
          </div>
          <span className="font-semibold text-[#111]">{row.name}</span>
        </div>
      ),
    },
    {
      header: 'Contact',
      accessor: (row: UserRow) => (
        <span className="text-sm text-[#6E6E80]">{row.contact}</span>
      ),
    },
    {
      header: 'Role',
      accessor: (row: UserRow) => {
        let bg = 'bg-[#F5F5F7]', text = 'text-[#444]';
        if (row.role === 'Admin') { bg = 'bg-[#FEF2F2]'; text = 'text-[#DC2626]'; }
        else if (row.role === 'Operator') { bg = 'bg-[#EFF6FF]'; text = 'text-[#2563EB]'; }
        else if (row.role === 'Driver') { bg = 'bg-[#FFF7ED]'; text = 'text-[#C2410C]'; }

        return (
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${bg} ${text} inline-flex items-center gap-1`}>
            {row.role === 'Admin' && <Shield size={10} />}
            {row.role === 'Driver' && <Truck size={10} />}
            {row.role}
          </span>
        );
      },
    },
    {
      header: 'Status',
      accessor: (row: UserRow) => (
        <span className={`text-xs font-bold px-2 py-0.5 rounded ${
          row.status === 'Active' ? 'bg-[#F0FDF4] text-[#16A34A]' : 'bg-[#F5F5F7] text-[#6E6E80]'
        }`}>
          {row.status}
        </span>
      ),
    },
    ...(isAdmin ? [{
      header: 'Actions',
      accessor: (row: UserRow) => (
        row.kind === 'driver' ? (
          <div className="flex gap-1">
            <button
              onClick={() => navigate(`/drivers/${row.id}`)}
              title="View in Drivers module"
              className="w-7 h-7 rounded-lg bg-[#F5F5F7] hover:bg-[#EBEBEF] flex items-center justify-center transition-colors"
            >
              <Eye size={13} className="text-[#6E6E80]" />
            </button>
          </div>
        ) : (
          <div className="flex gap-1">
            <button
              onClick={() => handleEdit(row.raw as UserDTO)}
              className="w-7 h-7 rounded-lg bg-[#F5F5F7] hover:bg-[#EBEBEF] flex items-center justify-center transition-colors"
            >
              <Edit2 size={13} className="text-[#6E6E80]" />
            </button>
            <button
              onClick={() => handleDelete(row.raw as UserDTO)}
              className="w-7 h-7 rounded-lg bg-[#FEF2F2] hover:bg-[#FEE2E2] flex items-center justify-center transition-colors"
            >
              <Trash2 size={13} className="text-[#DC2626]" />
            </button>
          </div>
        )
      ),
    }] : []),
  ];

  return (
    <DashboardLayout
      active="Settings"
      title="Settings"
    >
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col animate-fade-in gap-5">

        {/* Page Content Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 pb-1">
          <div className="flex items-center gap-3">
            <Users className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />

            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  User Management
                </h1>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                {isAdmin
                  ? 'Manage admins, operators, and drivers across the platform.'
                  : 'View admins and operators across the platform.'}
              </p>
            </div>
          </div>

          {isAdmin && (
            <div className="flex items-center gap-2.5">
              <Button
                variant="outline"
                size="sm"
                className="h-9 gap-1.5 text-xs font-semibold border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
                onClick={() => navigate('/drivers/new')}
              >
                <Truck className="h-3.5 w-3.5 text-slate-600" />
                Add Driver
              </Button>

              <Button
                size="sm"
                className="h-9 gap-1.5 text-xs font-bold bg-[#E8450F] hover:bg-[#d03d0c] text-white shadow-xs rounded-md px-4"
                onClick={() => { setEditingUser(null); setIsModalOpen(true); }}
              >
                <Plus className="h-4 w-4" />
                Invite User
              </Button>
            </div>
          )}
        </div>

        <DataTable
          title={
            <span className="flex items-center gap-2">
              <Users className="w-4 h-4 text-violet-500" />
              <span>{isAdmin ? 'All Platform Users' : 'Admins & Operators'}</span>
            </span>
          }
          columns={columns}
          data={filteredRows}
          bulkActions={[
            {
              label: 'Export CSV',
              icon: <Download size={13} />,
              variant: 'secondary' as const,
              onClick: (selectedRows: UserRow[]) => {
                downloadCSV(selectedRows.map(({ raw, ...rest }) => rest), 'platform_users_export.csv');
              }
            }
          ]}
          enableSelection={true}
          isLoading={isLoading || isDriversLoading}
          isError={isError}
          errorMessage={(error as Error)?.message || 'Failed to load users.'}
          searchPlaceholder="Search by name, email, or phone..."
          searchValue={search}
          onSearchChange={setSearch}
        />
      </div>

      {isAdmin && (
        <UserModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSave={handleSaveUser}
          initialData={editingUser}
          isLoading={createMutation.isPending || updateMutation.isPending}
        />
      )}
    </DashboardLayout>
  );
}
