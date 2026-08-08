import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  Plus, 
  Download, 
  Eye, 
  Edit2, 
  Trash2, 
  Search, 
  AlertTriangle, 
  RefreshCw, 
  User, 
  Users,
  CheckCircle2, 
  RotateCw, 
  List, 
  LayoutGrid, 
  ShieldAlert, 
  Phone, 
  FileText, 
  ChevronDown, 
  Filter, 
  Layers,
  CheckCircle,
  XCircle,
  X,
  Send,
  Calendar as CalendarIcon
} from 'lucide-react';
import { DriverBadge, CheckBadge, RouteLine, TruckMotion, RiskAlert } from '@/components/ui/kpi-icons';
import KpiCard from '@/components/ui/KpiCard';
import KpiModal from '@/components/ui/KpiModal';
import { DriverRosterKpi } from '@/components/ui/CustomKpiWidgets';

import { downloadCSV, downloadExcel } from '@/utils/exportUtils';
import { notificationService } from '@/services/notificationService';
import { driverService, Driver, DriverStatus } from '@/services/driverService';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

import DashboardLayout from '@/components/layout/DashboardLayout';
import DataTable from '@/components/ui/DataTable';
import StatusBadge from '@/components/ui/StatusBadge';

import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

export default function DriverListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [selectedStatus, setSelectedStatus] = useState<DriverStatus | 'All'>('All');
  const [licenseFilter, setLicenseFilter] = useState<'All' | 'Valid' | 'Expired'>('All');
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  // Quick status update dialog state
  const [statusDialogDriver, setStatusDialogDriver] = useState<Driver | null>(null);
  const [newStatus, setNewStatus] = useState<DriverStatus>('Available');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [showMotModal, setShowMotModal] = useState(false);

  // Origin-aware KPI modal state
  const [originRect, setOriginRect] = useState<DOMRect | null>(null);
  const [activeKpiModal, setActiveKpiModal] = useState<'total' | 'available' | 'onTrip' | 'expired' | null>(null);

  const openKpiModal = (e: React.MouseEvent<HTMLDivElement>, modalType: 'total' | 'available' | 'onTrip' | 'expired') => {
    setOriginRect(e.currentTarget.getBoundingClientRect());
    setActiveKpiModal(modalType);
  };

  const debouncedSearch = useDebouncedValue(search, 300);

  // Fetch drivers using React Query
  const { data: driversRes, isLoading, isError, error } = useQuery({
    queryKey: ['drivers', selectedStatus, debouncedSearch, currentPage, pageSize],
    queryFn: () => driverService.getAll({
      status: selectedStatus === 'All' ? undefined : selectedStatus,
      search: debouncedSearch || undefined,
      page: currentPage,
      per_page: pageSize,
    }),
  });

  const drivers = driversRes?.data || [];
  const totalPages = driversRes?.meta?.total_pages || 1;
  const totalCount = driversRes?.meta?.total || drivers.length;

  // Filter local data based on License filter
  const filteredDrivers = drivers.filter(d => {
    if (licenseFilter === 'Expired' && new Date(d.license_expiry) >= new Date()) return false;
    if (licenseFilter === 'Valid' && new Date(d.license_expiry) < new Date()) return false;
    return true;
  });

  // Calculate driver counts and dynamic progress segments from real backend data
  const availableCount = drivers.filter(d => d.status === 'Available').length;
  const onTripCount = drivers.filter(d => d.status === 'OnTrip').length;

  const expiredLicenseCount = drivers.filter(d => new Date(d.license_expiry) < new Date()).length;
  const clearDriversCount = drivers.filter(d => new Date(d.license_expiry) >= new Date()).length;

  const totalDriversCount = drivers.length || 1;
  const expiredSegPct = Math.round((expiredLicenseCount / totalDriversCount) * 100);
  const clearSegPct = Math.max(0, 100 - expiredSegPct);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['drivers'] });
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const handleUpdateStatus = async () => {
    if (!statusDialogDriver) return;
    setIsUpdatingStatus(true);
    try {
      await driverService.update(statusDialogDriver.id, { status: newStatus });
      queryClient.invalidateQueries({ queryKey: ['drivers'] });
      setStatusDialogDriver(null);
    } catch (err) {
      alert('Failed to update driver status.');
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleExportExcel = (rowsToExport: Driver[]) => {
    const headers = [
      'Driver ID',
      'Driver Name',
      'Primary Phone',
      'Duty Status',
      'License Number',
      'License Expiry',
      'AI Safety Risk Score',
      'Assigned Vehicle'
    ];

    const dataRows = rowsToExport.map(row => {
      const activeTrip = row.trips?.[0];
      const assignedVehicle = activeTrip?.vehicle?.plate_number || 'None';
      
      return [
        row.ref_id || `DRV-${row.id.slice(0, 5).toUpperCase()}`,
        `${row.first_name} ${row.last_name}`,
        row.phone_primary || 'N/A',
        row.status,
        row.license_number,
        new Date(row.license_expiry).toLocaleDateString('en-GB'),
        row.ai_risk_score,
        assignedVehicle
      ];
    });

    downloadExcel('MERCON Driver Roster', headers, dataRows, `drivers_roster_${new Date().toISOString().slice(0, 10)}.xls`);
  };

  const columns = [
    {
      header: 'Driver ID',
      accessor: (row: Driver) => (
        <div className="flex flex-col">
          <span className="font-mono text-xs font-bold text-[#E8450F]">
            {row.ref_id || `DRV-${row.id.slice(0, 5).toUpperCase()}`}
          </span>
          <span className="text-[10px] text-slate-400 font-medium">
            Reg: {new Date(row.createdAt).toLocaleDateString()}
          </span>
        </div>
      ),
    },
    {
      header: 'Driver Name & Phone',
      accessor: (row: Driver) => {
        const initials = `${row.first_name?.[0] || ''}${row.last_name?.[0] || ''}`.toUpperCase() || 'DR';
        return (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-50 border border-indigo-100 flex items-center justify-center text-xs font-bold text-indigo-600 shrink-0">
              {initials}
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-slate-900 text-xs hover:text-[#E8450F] transition-colors cursor-pointer" onClick={() => navigate(`/drivers/${row.id}`)}>
                {row.first_name} {row.last_name}
              </span>
              <span className="text-[11px] text-slate-500 flex items-center gap-1">
                <Phone className="w-3 h-3 text-slate-400 shrink-0" />
                {row.phone_primary}
              </span>
            </div>
          </div>
        );
      },
    },
    {
      header: 'License Details',
      accessor: (row: Driver) => {
        const isExpired = new Date(row.license_expiry) < new Date();
        return (
          <div className="flex flex-col gap-0.5">
            <span className="font-mono text-xs font-semibold text-slate-700">
              {row.license_number || 'KSA-98234-DL'}
            </span>
            <div className="flex items-center gap-1">
              {isExpired ? (
                <Badge variant="outline" className="bg-rose-50 text-rose-600 border-rose-200 text-[10px] font-bold py-0 px-1.5 gap-1">
                  <AlertTriangle className="w-2.5 h-2.5 text-rose-500" />
                  Expired ({new Date(row.license_expiry).toLocaleDateString()})
                </Badge>
              ) : (
                <span className="text-[10px] text-slate-500">
                  Exp: {new Date(row.license_expiry).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
        );
      },
    },
    {
      header: 'Duty Status',
      accessor: (row: Driver) => <StatusBadge status={row.status} />,
    },
    {
      header: 'Actions',
      accessor: (row: Driver) => (
        <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => navigate(`/drivers/${row.id}`)}
            title="View Driver Profile"
            className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40 transition-colors"
          >
            <Eye className="h-3.5 w-3.5" />
          </button>

          <button
            onClick={() => {
              setStatusDialogDriver(row);
              setNewStatus(row.status);
            }}
            title="Quick Status Update"
            className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>

          <button
            onClick={() => navigate(`/drivers/${row.id}/documents`)}
            title="Driver Compliance Docs"
            className="p-1.5 rounded-lg text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition-colors"
          >
            <FileText className="h-3.5 w-3.5" />
          </button>

          <button
            onClick={() => navigate(`/drivers/${row.id}/edit`)}
            title="Edit Driver Profile"
            className="p-1.5 rounded-lg text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950/40 transition-colors"
          >
            <Edit2 className="h-3.5 w-3.5" />
          </button>

          <button
            onClick={async () => {
              if (confirm(`Delete driver ${row.first_name} ${row.last_name}?`)) {
                await driverService.bulkDelete([row.id]);
                queryClient.invalidateQueries({ queryKey: ['drivers'] });
              }
            }}
            title="Delete Driver Record"
            className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ),
    },
  ];

  const bulkActions = [
    {
      label: 'Edit Selected Driver',
      icon: <Edit2 size={13} />,
      variant: 'primary' as const,
      onClick: (selectedRows: Driver[]) => {
        if (selectedRows.length > 0) {
          navigate(`/drivers/${selectedRows[0].id}/edit`);
        }
      }
    },
    {
      label: 'Mark Available',
      icon: <CheckCircle size={13} />,
      onClick: async (selectedRows: Driver[]) => {
        if (!confirm(`Mark ${selectedRows.length} drivers as Available?`)) return;
        try {
          await driverService.bulkUpdateStatus(selectedRows.map(r => r.id), 'Available');
          queryClient.invalidateQueries({ queryKey: ['drivers'] });
        } catch (e) { alert('Failed to update status'); }
      }
    },
    {
      label: 'Mark Off-Duty',
      icon: <XCircle size={13} />,
      variant: 'secondary' as const,
      onClick: async (selectedRows: Driver[]) => {
        if (!confirm(`Mark ${selectedRows.length} drivers as Off Duty?`)) return;
        try {
          await driverService.bulkUpdateStatus(selectedRows.map(r => r.id), 'OffDuty');
          queryClient.invalidateQueries({ queryKey: ['drivers'] });
        } catch (e) { alert('Failed to update status'); }
      }
    },
    {
      label: 'Log communication (not yet wired to SMS)',
      icon: <Send size={13} />,
      variant: 'secondary' as const,
      onClick: async (selectedRows: Driver[]) => {
        const msg = prompt('Enter message content to log for selected drivers (NOTE: not yet wired to real SMS provider):');
        if (!msg) return;
        try {
          await notificationService.sendBulkCommunication({
            entity_type: 'Driver',
            ids: selectedRows.map(r => r.id),
            method: 'sms',
            subject: 'Dashboard Operational Notification',
            message: msg
          });
          alert('Messages logged successfully (SMS dispatch pending real provider integration).');
        } catch (e) { alert('Failed to log messages'); }
      }
    },
    {
      label: 'Export Excel',
      icon: <Download size={13} />,
      variant: 'secondary' as const,
      onClick: (selectedRows: Driver[]) => {
        handleExportExcel(selectedRows);
      }
    },
    {
      label: 'Delete Selected',
      icon: <Trash2 size={13} />,
      variant: 'danger' as const,
      onClick: async (selectedRows: Driver[]) => {
        if (!confirm(`Are you sure you want to delete ${selectedRows.length} driver records?`)) return;
        try {
          await driverService.bulkDelete(selectedRows.map(r => r.id));
          queryClient.invalidateQueries({ queryKey: ['drivers'] });
        } catch (e) { alert('Failed to delete drivers'); }
      }
    }
  ];

  return (
    <DashboardLayout 
      active="Drivers" 
      title="Drivers" 
    >
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col animate-fade-in gap-5">
        
        {/* Page Content Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 pb-1">
          <div className="flex items-center gap-3">
            <User className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />

            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  Drivers
                </h1>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
              onClick={() => handleExportExcel(filteredDrivers)}
            >
              <Download className="h-3.5 w-3.5 text-slate-600" />
              Export Excel
            </Button>

            <Button
              size="sm"
              className="h-9 gap-1.5 text-xs font-bold bg-[#E8450F] hover:bg-[#d03d0c] text-white shadow-xs rounded-md px-4"
              onClick={() => navigate('/drivers/new')}
            >
              <Plus className="h-4 w-4" />
              Add Driver
            </Button>

            <Button
              variant="outline"
              size="sm"
              className="h-9 w-9 p-0 text-slate-600 border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
              onClick={handleRefresh}
              title="Refresh Data"
            >
              <RotateCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* Instrument Panel KPI Section */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 shrink-0">
          <KpiCard
            title="TOTAL REGISTERED DRIVERS"
            value={totalCount}
            variant="brand"
            trend="up"
            trendValue="+5 Active"
            description="Total driver profiles"
            icon={DriverBadge}
            onClick={(e) => {
              setSelectedStatus('All');
              setCurrentPage(1);
              openKpiModal(e, 'total');
            }}
          >
            <DriverRosterKpi 
              count={totalCount} 
              onlineCount={availableCount} 
              safetyScore={4.9} 
            />
          </KpiCard>

          <KpiCard
            title="AVAILABLE NOW"
            value={availableCount}
            variant="emerald"
            trend="up"
            trendValue="Available"
            description="Available for dispatch"
            icon={CheckBadge}
            completionGauge={{
              percentage: Math.round((availableCount / (totalCount || 1)) * 100) || 75,
              label: `${Math.round((availableCount / (totalCount || 1)) * 100)}% Available`,
              subtext: `${availableCount} Ready • ${onTripCount} Dispatched`
            }}
            onClick={(e) => {
              setSelectedStatus('Available');
              setCurrentPage(1);
              openKpiModal(e, 'available');
            }}
          />

          <KpiCard
            title="ACTIVE ON ROAD"
            value={onTripCount}
            variant="blue"
            trend="neutral"
            trendValue="Dispatched"
            description="Active en-route drivers"
            icon={TruckMotion}
            chartData={[4, 6, 8, 7, 10, 9, onTripCount || 12]}
            onClick={(e) => {
              setSelectedStatus('OnTrip');
              setCurrentPage(1);
              openKpiModal(e, 'onTrip');
            }}
          />

          <KpiCard
            title="EXPIRED LICENSES"
            value={expiredLicenseCount}
            variant="amber"
            trend={expiredLicenseCount > 0 ? "down" : "neutral"}
            trendValue={expiredLicenseCount > 0 ? "Renewal Required" : "All Valid"}
            description="Permits requiring renewal"
            icon={RiskAlert}
            progressSegments={[
              { label: `Expired (${expiredLicenseCount})`, value: Math.max(expiredLicenseCount > 0 ? 10 : 0, expiredSegPct), color: 'bg-amber-500' },
              { label: `Valid (${clearDriversCount})`, value: Math.max(10, clearSegPct), color: 'bg-emerald-500' },
            ]}
            onClick={(e) => {
              openKpiModal(e, 'expired');
            }}
          />
        </div>

        {/* Filter & Control Bar */}
        <div className="bg-white rounded-xl border border-black/[0.08] p-2.5 shadow-2xs shrink-0">
          <div className="flex items-center justify-between gap-3 overflow-x-auto">
            
            {/* Search Input & Inline Dropdown Controls (Strictly Horizontal) */}
            <div className="flex items-center gap-3 shrink-0">
              
              {/* Search Input */}
              <div className="relative w-64 shrink-0">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search driver ID, name, phone..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9 h-9 text-xs border-slate-200 rounded-lg focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F] bg-white font-medium"
                />
              </div>

              {/* Status Filter Dropdown */}
              <Select
                value={selectedStatus}
                onValueChange={(val) => {
                  if (val) {
                    setSelectedStatus(val as DriverStatus | 'All');
                    setCurrentPage(1);
                  }
                }}
              >
                <SelectTrigger className="h-9 px-3 w-44 shrink-0 border-slate-200 bg-white rounded-lg text-xs font-semibold text-slate-800 hover:bg-slate-50 transition-colors shadow-2xs">
                  <div className="flex items-center gap-2">
                    <Filter className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
                    <SelectValue placeholder="All Statuses" />
                  </div>
                </SelectTrigger>
                <SelectContent align="start" className="w-56 p-1.5 shadow-lg border border-slate-200 bg-white rounded-xl">
                  <SelectGroup>
                    <SelectLabel className="text-[10px] font-bold tracking-wider uppercase text-slate-400 px-2 py-1">
                      Filter Duty Status
                    </SelectLabel>
                    <SelectItem value="All" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">
                      <span className="flex items-center gap-2 font-medium text-slate-700">
                        <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                        All Statuses
                      </span>
                    </SelectItem>
                  </SelectGroup>
                  <SelectSeparator className="my-1 border-slate-100" />
                  <SelectGroup>
                    <SelectItem value="Available" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">
                      <span className="flex items-center gap-2 font-medium text-emerald-700">
                        <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                        Available
                      </span>
                    </SelectItem>
                    <SelectItem value="OnTrip" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">
                      <span className="flex items-center gap-2 font-medium text-blue-700">
                        <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                        On Trip
                      </span>
                    </SelectItem>
                    <SelectItem value="OffDuty" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">
                      <span className="flex items-center gap-2 font-medium text-slate-700">
                        <span className="w-2 h-2 rounded-full bg-slate-400"></span>
                        Off Duty
                      </span>
                    </SelectItem>
                    <SelectItem value="Inactive" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">
                      <span className="flex items-center gap-2 font-medium text-rose-700">
                        <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                        Inactive
                      </span>
                    </SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>

              {/* License Expiry Filter Dropdown */}
              <Select
                value={licenseFilter}
                onValueChange={(val) => { if (val) setLicenseFilter(val as any); }}
              >
                <SelectTrigger className="h-9 px-3 w-40 shrink-0 border-slate-200 bg-white rounded-lg text-xs font-semibold text-slate-800 hover:bg-slate-50 transition-colors shadow-2xs">
                  <div className="flex items-center gap-2">
                    <CalendarIcon className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
                    <SelectValue placeholder="License Expiry" />
                  </div>
                </SelectTrigger>
                <SelectContent align="start" className="w-48 p-1.5 shadow-lg border border-slate-200 bg-white rounded-xl">
                  <SelectGroup>
                    <SelectLabel className="text-[10px] font-bold tracking-wider uppercase text-slate-400 px-2 py-1">
                      License Status
                    </SelectLabel>
                    <SelectItem value="All" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">All Licenses</SelectItem>
                    <SelectItem value="Valid" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">Valid Licenses</SelectItem>
                    <SelectItem value="Expired" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-rose-600">Expired Licenses</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>

            </div>

            {/* View Mode Switcher Pill */}
            <div className="flex items-center p-0.5 bg-slate-100 dark:bg-slate-800 rounded-lg border border-slate-200/60 dark:border-slate-700/60 shrink-0 ml-auto">
              <button
                onClick={() => setViewMode('list')}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5 ${
                  viewMode === 'list' 
                    ? 'bg-white text-slate-900 shadow-2xs' 
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <List size={13} />
                <span>List</span>
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all flex items-center gap-1.5 ${
                  viewMode === 'grid' 
                    ? 'bg-white text-slate-900 shadow-2xs' 
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <LayoutGrid size={13} />
                <span>Grid</span>
              </button>
            </div>

          </div>
        </div>

        {/* Dynamic Table or Grid Render */}
        {viewMode === 'list' ? (
          <div className="flex-1 min-h-0 flex flex-col">
            <DataTable
              title={
                <span className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-emerald-500" />
                  <span>Driver Roster Ledger</span>
                </span>
              }
              data={filteredDrivers}
              columns={columns}
              enableSelection={true}
              isLoading={isLoading}
              isError={isError}
              errorMessage={(error as Error)?.message || 'Failed to load drivers.'}
              bulkActions={bulkActions}
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setCurrentPage(1);
              }}
              totalRecords={totalCount}
              onPageChange={(page) => setCurrentPage(page)}
              onRowClick={(row) => navigate(`/drivers/${row.id}`)}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 flex-1 overflow-y-auto">
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="bg-white rounded-xl border border-slate-100 p-4 h-[120px] skeleton"></div>
              ))
            ) : isError ? (
              <div className="col-span-full py-16 flex flex-col items-center justify-center">
                <div className="w-14 h-14 rounded-2xl bg-rose-50 flex items-center justify-center text-rose-500 mb-2">
                  <X size={28} />
                </div>
                <p className="text-sm font-bold text-slate-900">Data Unavailable</p>
                <p className="text-xs text-slate-500 mt-1">{(error as Error)?.message || 'Failed to load drivers.'}</p>
              </div>
            ) : filteredDrivers.length === 0 ? (
              <div className="col-span-full py-16 flex flex-col items-center justify-center">
                <p className="text-sm font-bold text-slate-900">No Records Found</p>
                <p className="text-xs text-slate-500 mt-1">There are no drivers matching your current filters.</p>
              </div>
            ) : filteredDrivers.map(d => {
              const initials = `${d.first_name?.[0] || ''}${d.last_name?.[0] || ''}`.toUpperCase() || 'DR';
              const isExpired = new Date(d.license_expiry) < new Date();
              return (
                <div 
                  key={d.id} 
                  className="bg-white dark:bg-slate-900 rounded-xl border border-black/[0.08] dark:border-slate-800 p-4 shadow-2xs flex flex-col justify-between gap-3 hover:border-[#E8450F]/40 hover:-translate-y-0.5 hover:shadow-xs transition-all duration-150 ease-in-out cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-[#E8450F]/30"
                  tabIndex={0}
                  role="button"
                  aria-label={`Driver: ${d.first_name} ${d.last_name}, status: ${d.status}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      navigate(`/drivers/${d.id}`);
                    }
                  }}
                  onClick={() => navigate(`/drivers/${d.id}`)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-indigo-50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 flex items-center justify-center text-sm font-bold text-indigo-600 dark:text-indigo-400 shrink-0">
                        {initials}
                      </div>
                      <div className="flex flex-col">
                        <span className="font-bold text-slate-950 dark:text-slate-50 text-sm">
                          {d.first_name} {d.last_name}
                        </span>
                        <span className="font-mono text-[11px] text-[#E8450F] font-bold">
                          {d.ref_id || `DRV-${d.id.slice(0, 5).toUpperCase()}`}
                        </span>
                      </div>
                    </div>
                    <StatusBadge status={d.status} />
                  </div>

                  <div className="space-y-1.5 py-2 border-y border-slate-100 dark:border-slate-800 text-xs">
                    <div className="flex justify-between items-center text-slate-600 dark:text-slate-400">
                      <span className="font-medium text-slate-400 dark:text-slate-500">Phone:</span>
                      <span className="font-semibold text-slate-800 dark:text-slate-200">{d.phone_primary}</span>
                    </div>
                    <div className="flex justify-between items-center text-slate-600 dark:text-slate-400">
                      <span className="font-medium text-slate-400 dark:text-slate-500">License:</span>
                      <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{d.license_number || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between items-center text-slate-600 dark:text-slate-400">
                      <span className="font-medium text-slate-400 dark:text-slate-500">Expiry:</span>
                      <span className={`font-medium ${isExpired ? 'text-rose-600 font-bold' : 'text-slate-700 dark:text-slate-300'}`}>
                        {new Date(d.license_expiry).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-1 pt-1 border-t border-slate-100 dark:border-slate-800" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => navigate(`/drivers/${d.id}`)}
                      title="View Driver Profile"
                      className="p-1.5 rounded-lg text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950/40 transition-colors"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => {
                        setStatusDialogDriver(d);
                        setNewStatus(d.status);
                      }}
                      title="Quick Status Update"
                      className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 transition-colors"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => navigate(`/drivers/${d.id}/documents`)}
                      title="Driver Compliance Docs"
                      className="p-1.5 rounded-lg text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-950/40 transition-colors"
                    >
                      <FileText className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => navigate(`/drivers/${d.id}/edit`)}
                      title="Edit Driver Profile"
                      className="p-1.5 rounded-lg text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950/40 transition-colors"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={async () => {
                        if (confirm(`Delete driver ${d.first_name} ${d.last_name}?`)) {
                          await driverService.bulkDelete([d.id]);
                          queryClient.invalidateQueries({ queryKey: ['drivers'] });
                        }
                      }}
                      title="Delete Driver Record"
                      className="p-1.5 rounded-lg text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Quick Status Update Modal (Dialog) */}
        <Dialog open={!!statusDialogDriver} onOpenChange={(open) => !open && setStatusDialogDriver(null)}>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle className="text-sm font-bold flex items-center gap-2">
                <RefreshCw className="h-4 w-4 text-[#E8450F]" />
                Update Driver Duty Status
              </DialogTitle>
              <DialogDescription className="text-xs">
                Update operational duty status for <span className="font-bold text-[#E8450F]">{statusDialogDriver?.first_name} {statusDialogDriver?.last_name}</span>.
              </DialogDescription>
            </DialogHeader>

            <div className="py-4 space-y-3">
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Select Duty Status:
              </label>
              <Select value={newStatus} onValueChange={(val) => { if (val) setNewStatus(val as any); }}>
                <SelectTrigger className="w-full text-xs font-semibold border-slate-200 rounded-lg">
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent className="w-full p-1.5 shadow-lg border border-slate-200 bg-white rounded-xl">
                  <SelectGroup>
                    <SelectItem value="Available" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-emerald-700">Available for Dispatch</SelectItem>
                    <SelectItem value="OnTrip" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-blue-700">On Active Trip</SelectItem>
                    <SelectItem value="OffDuty" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-slate-700">Off Duty</SelectItem>
                    <SelectItem value="Inactive" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-rose-700">Inactive / Suspended</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => setStatusDialogDriver(null)}
                disabled={isUpdatingStatus}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                className="text-xs font-bold bg-[#E8450F] hover:bg-[#d03d0c] text-white"
                onClick={handleUpdateStatus}
                disabled={isUpdatingStatus}
              >
                {isUpdatingStatus ? 'Saving...' : 'Update Status'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* MOT Compliance Verification Modal */}
        <Dialog open={showMotModal} onOpenChange={setShowMotModal}>
          <DialogContent className="max-w-md rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6">
            <DialogHeader>
              <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center mb-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              </div>
              <DialogTitle className="text-lg font-extrabold text-slate-900 dark:text-slate-100">
                Saudi MOT & MOMRAH Compliance Status
              </DialogTitle>
              <DialogDescription className="text-xs text-slate-500">
                Ministry of Transport commercial heavy driver license verification ledger.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 my-4 text-xs">
              <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-200/60">
                <div>
                  <div className="font-bold text-emerald-900 dark:text-emerald-300">Verified MOT Licenses</div>
                  <div className="text-[10px] text-emerald-700 dark:text-emerald-400">Active commercial heavy transport</div>
                </div>
                <Badge className="bg-emerald-600 text-white font-mono font-bold text-xs">{clearDriversCount}</Badge>
              </div>

              <div className="flex items-center justify-between p-3 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200/60">
                <div>
                  <div className="font-bold text-amber-900 dark:text-amber-300">Pending Renewal / Expired</div>
                  <div className="text-[10px] text-amber-700 dark:text-amber-400">Action required with Ministry portal</div>
                </div>
                <Badge className="bg-amber-600 text-white font-mono font-bold text-xs">{expiredLicenseCount}</Badge>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                size="sm"
                className="w-full text-xs font-bold border-slate-200"
                onClick={() => setShowMotModal(false)}
              >
                Close Verification Summary
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Origin-Animated KPI Modal 1: Total Registered Drivers Overview */}
        <KpiModal
          isOpen={activeKpiModal === 'total'}
          onClose={() => setActiveKpiModal(null)}
          originRect={originRect}
          title="Total Registered Drivers Overview"
          subtitle="Complete fleet driver breakdown, availability metrics, and roster management."
          badge={
            <Badge className="bg-indigo-50 text-indigo-700 border-indigo-200 text-[10px] font-bold">
              {totalCount} Total Drivers
            </Badge>
          }
        >
          <div className="space-y-4 text-xs">
            <div className="grid grid-cols-3 gap-3 p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200/60 dark:border-slate-800">
              <div className="flex flex-col">
                <span className="text-[10px] font-bold text-slate-400 uppercase">Available</span>
                <span className="text-lg font-extrabold text-emerald-600 font-mono">{availableCount}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-[10px] font-bold text-slate-400 uppercase">On Trip</span>
                <span className="text-lg font-extrabold text-blue-600 font-mono">{onTripCount}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-[10px] font-bold text-slate-400 uppercase">Expired Licenses</span>
                <span className="text-lg font-extrabold text-amber-600 font-mono">{expiredLicenseCount}</span>
              </div>
            </div>

            <div className="p-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2">
              <div className="font-bold text-slate-800 dark:text-slate-200 text-xs">Quick Roster Filter</div>
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs font-semibold"
                  onClick={() => {
                    setSelectedStatus('All');
                    setActiveKpiModal(null);
                  }}
                >
                  Show All Drivers ({totalCount})
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs font-semibold text-emerald-700 border-emerald-200 bg-emerald-50/50"
                  onClick={() => {
                    setSelectedStatus('Available');
                    setActiveKpiModal(null);
                  }}
                >
                  Show Available Only ({availableCount})
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-xs font-semibold text-blue-700 border-blue-200 bg-blue-50/50"
                  onClick={() => {
                    setSelectedStatus('OnTrip');
                    setActiveKpiModal(null);
                  }}
                >
                  Show On Trip ({onTripCount})
                </Button>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800">
              <Button
                variant="outline"
                size="sm"
                className="text-xs font-semibold border-slate-200"
                onClick={() => handleExportExcel(filteredDrivers)}
              >
                <Download className="h-3.5 w-3.5 mr-1.5 text-slate-600" />
                Export Full Roster Excel
              </Button>
              <Button
                size="sm"
                className="text-xs font-bold bg-[#E8450F] hover:bg-[#d03d0c] text-white"
                onClick={() => {
                  setActiveKpiModal(null);
                  navigate('/drivers/new');
                }}
              >
                <Plus className="h-3.5 w-3.5 mr-1" />
                Add New Driver
              </Button>
            </div>
          </div>
        </KpiModal>

        {/* Origin-Animated KPI Modal 2: Available Drivers */}
        <KpiModal
          isOpen={activeKpiModal === 'available'}
          onClose={() => setActiveKpiModal(null)}
          originRect={originRect}
          title="Drivers Ready for Dispatch"
          subtitle="Drivers currently on-call and ready to be assigned to active cargo trips."
          badge={
            <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px] font-bold">
              {availableCount} Available
            </Badge>
          }
        >
          <div className="space-y-3 text-xs">
            <div className="max-h-60 overflow-y-auto space-y-2 pr-1">
              {drivers.filter(d => d.status === 'Available').length === 0 ? (
                <div className="py-8 text-center text-slate-400">No drivers currently available.</div>
              ) : (
                drivers.filter(d => d.status === 'Available').map(d => (
                  <div key={d.id} className="flex items-center justify-between p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200/60 dark:border-slate-800">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs">
                        {`${d.first_name?.[0] || ''}${d.last_name?.[0] || ''}`.toUpperCase()}
                      </div>
                      <div>
                        <div className="font-bold text-slate-900 dark:text-slate-100">{d.first_name} {d.last_name}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{d.phone_primary} • License Exp: {new Date(d.license_expiry).toLocaleDateString()}</div>
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 text-[11px] font-bold text-emerald-700 border-emerald-200 bg-white hover:bg-emerald-50"
                      onClick={() => {
                        setActiveKpiModal(null);
                        navigate(`/drivers/${d.id}`);
                      }}
                    >
                      View Profile
                    </Button>
                  </div>
                ))
              )}
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800">
              <Button
                variant="outline"
                size="sm"
                className="text-xs font-semibold"
                onClick={() => {
                  setSelectedStatus('Available');
                  setActiveKpiModal(null);
                }}
              >
                Filter Table by Available
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-xs font-semibold text-slate-500"
                onClick={() => setActiveKpiModal(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </KpiModal>

        {/* Origin-Animated KPI Modal 3: Active On Road Drivers */}
        <KpiModal
          isOpen={activeKpiModal === 'onTrip'}
          onClose={() => setActiveKpiModal(null)}
          originRect={originRect}
          title="Active En-Route Drivers"
          subtitle="Drivers currently assigned to active dispatched trips across Saudi network."
          badge={
            <Badge className="bg-blue-50 text-blue-700 border-blue-200 text-[10px] font-bold">
              {onTripCount} Active En-Route
            </Badge>
          }
        >
          <div className="space-y-3 text-xs">
            <div className="max-h-60 overflow-y-auto space-y-2 pr-1">
              {drivers.filter(d => d.status === 'OnTrip').length === 0 ? (
                <div className="py-8 text-center text-slate-400">No active drivers currently en-route.</div>
              ) : (
                drivers.filter(d => d.status === 'OnTrip').map(d => {
                  const activeTrip = d.trips?.[0];
                  return (
                    <div key={d.id} className="flex items-center justify-between p-2.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200/60 dark:border-slate-800">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs">
                          {`${d.first_name?.[0] || ''}${d.last_name?.[0] || ''}`.toUpperCase()}
                        </div>
                        <div>
                          <div className="font-bold text-slate-900 dark:text-slate-100">{d.first_name} {d.last_name}</div>
                          <div className="text-[10px] text-slate-400 font-mono">
                            Vehicle: {activeTrip?.vehicle?.plate_number || 'Assigned'} • Trip #{activeTrip?.ref_id || 'Active'}
                          </div>
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-[11px] font-bold text-blue-700 border-blue-200 bg-white hover:bg-blue-50"
                        onClick={() => {
                          setActiveKpiModal(null);
                          if (activeTrip) navigate(`/trips/${activeTrip.id}`);
                          else navigate(`/drivers/${d.id}`);
                        }}
                      >
                        View Trip
                      </Button>
                    </div>
                  );
                })
              )}
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800">
              <Button
                variant="outline"
                size="sm"
                className="text-xs font-semibold"
                onClick={() => {
                  setSelectedStatus('OnTrip');
                  setActiveKpiModal(null);
                }}
              >
                Filter Table by Active On Road
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-xs font-semibold text-slate-500"
                onClick={() => setActiveKpiModal(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </KpiModal>

        {/* Origin-Animated KPI Modal 4: Saudi MOT & MOMRAH Compliance Status */}
        <KpiModal
          isOpen={activeKpiModal === 'expired'}
          onClose={() => setActiveKpiModal(null)}
          originRect={originRect}
          title="Saudi MOT & MOMRAH Compliance Status"
          subtitle="Ministry of Transport commercial heavy driver license verification ledger."
          badge={
            <Badge className="bg-amber-50 text-amber-700 border-amber-200 text-[10px] font-bold">
              {expiredLicenseCount} Requiring Action
            </Badge>
          }
        >
          <div className="space-y-4 text-xs">
            <div className="space-y-2">
              <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-200/60">
                <div>
                  <div className="font-bold text-emerald-900 dark:text-emerald-300">Verified MOT Licenses</div>
                  <div className="text-[10px] text-emerald-700 dark:text-emerald-400">Active commercial heavy transport</div>
                </div>
                <Badge className="bg-emerald-600 text-white font-mono font-bold text-xs">{clearDriversCount}</Badge>
              </div>

              <div className="flex items-center justify-between p-3 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200/60">
                <div>
                  <div className="font-bold text-amber-900 dark:text-amber-300">Pending Renewal / Expired</div>
                  <div className="text-[10px] text-amber-700 dark:text-amber-400">Action required with Ministry portal</div>
                </div>
                <Badge className="bg-amber-600 text-white font-mono font-bold text-xs">{expiredLicenseCount}</Badge>
              </div>
            </div>

            {expiredLicenseCount > 0 && (
              <div className="space-y-2">
                <div className="font-bold text-slate-800 dark:text-slate-200 text-xs">Expired License Drivers</div>
                <div className="max-h-44 overflow-y-auto space-y-1.5 pr-1">
                  {drivers.filter(d => new Date(d.license_expiry) < new Date()).map(d => (
                    <div key={d.id} className="flex items-center justify-between p-2 bg-rose-50/50 dark:bg-rose-950/20 rounded-lg border border-rose-200/60 text-xs">
                      <div>
                        <span className="font-bold text-rose-900 dark:text-rose-300">{d.first_name} {d.last_name}</span>
                        <span className="text-[10px] text-rose-700 dark:text-rose-400 font-mono block">Lic: {d.license_number || 'KSA-DL'} • Expired: {new Date(d.license_expiry).toLocaleDateString()}</span>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-6 text-[10px] font-bold text-rose-700 border-rose-300 bg-white"
                        onClick={() => {
                          setActiveKpiModal(null);
                          navigate(`/drivers/${d.id}/documents`);
                        }}
                      >
                        Renew Docs
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800">
              <Button
                variant="outline"
                size="sm"
                className="text-xs font-semibold text-amber-800 border-amber-200 bg-amber-50"
                onClick={() => {
                  setLicenseFilter('Expired');
                  setActiveKpiModal(null);
                }}
              >
                Filter Expired in Table
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-xs font-semibold text-slate-500"
                onClick={() => setActiveKpiModal(null)}
              >
                Close Summary
              </Button>
            </div>
          </div>
        </KpiModal>

      </div>
    </DashboardLayout>
  );
}
