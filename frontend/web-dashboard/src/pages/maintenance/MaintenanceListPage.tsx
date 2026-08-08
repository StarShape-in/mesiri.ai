import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Wrench, Download, Plus, RotateCw, Search, Filter, 
  Calendar, CheckCircle2, Clock, AlertTriangle, FileText, 
  DollarSign, Truck, Edit2, Trash2, ExternalLink, ShieldAlert,
  Building2, Gauge, Layers, ChevronDown, Eye,
  ChevronsUpDown, ArrowUp, LayoutGrid, List, Phone, Database
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuLabel, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from '@/components/ui/dropdown-menu';

import { maintenanceService, MaintenanceRecord, CreateMaintenancePayload, MaintenanceType, MaintenanceStatus } from '@/services/maintenanceService';
import { vehicleService } from '@/services/vehicleService';
import { exportToCSV } from '@/utils/exportUtils';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';
import { cn } from '@/lib/utils';

export default function MaintenanceListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search, 300);
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, statusFilter, typeFilter]);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<MaintenanceRecord | null>(null);
  const [recordToDelete, setRecordToDelete] = useState<MaintenanceRecord | null>(null);

  // Form states
  const [formData, setFormData] = useState<CreateMaintenancePayload>({
    vehicle_id: '',
    workshop_name: '',
    workshop_contact: '',
    maintenance_type: 'Routine',
    status: 'Completed',
    start_date: new Date().toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
    work_done: '',
    odometer_reading: 0,
    cost: 0,
    invoice_number: '',
    remarks: '',
  });
  const [formError, setFormError] = useState('');

  // Queries
  const { data: maintenanceRes, isLoading, refetch } = useQuery({
    queryKey: ['maintenance', debouncedSearch, statusFilter, typeFilter, page],
    queryFn: () => maintenanceService.getAll({
      search: debouncedSearch || undefined,
      status: statusFilter !== 'all' ? statusFilter : undefined,
      maintenance_type: typeFilter !== 'all' ? typeFilter : undefined,
      page,
      per_page: 25,
    }),
  });

  const { data: vehiclesRes } = useQuery({
    queryKey: ['vehicles'],
    queryFn: () => vehicleService.getAll({ per_page: 100 }),
  });

  const records = maintenanceRes?.data || [];
  const kpis = maintenanceRes?.kpis || {
    total_cost: 0,
    active_count: 0,
    scheduled_count: 0,
    completed_count: 0,
    renewal_cost: 0,
  };

  const vehicles = vehiclesRes?.data || [];

  // Mutations
  const createMutation = useMutation({
    mutationFn: (payload: CreateMaintenancePayload) => maintenanceService.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['maintenance'] });
      setIsModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.error?.message || 'Failed to save maintenance record.');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: any }) => maintenanceService.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['maintenance'] });
      setIsModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.error?.message || 'Failed to update maintenance record.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => maintenanceService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['maintenance'] });
      setRecordToDelete(null);
    },
  });

  const resetForm = () => {
    setEditingRecord(null);
    setFormData({
      vehicle_id: vehicles[0]?.id || '',
      workshop_name: '',
      workshop_contact: '',
      maintenance_type: 'Routine',
      status: 'Completed',
      start_date: new Date().toISOString().split('T')[0],
      end_date: new Date().toISOString().split('T')[0],
      work_done: '',
      odometer_reading: 0,
      cost: 0,
      invoice_number: '',
      remarks: '',
    });
    setFormError('');
  };

  const handleOpenCreateModal = () => {
    resetForm();
    if (vehicles.length > 0) {
      setFormData(prev => ({ ...prev, vehicle_id: vehicles[0].id }));
    }
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (rec: MaintenanceRecord) => {
    setEditingRecord(rec);
    setFormData({
      vehicle_id: rec.vehicleId,
      workshop_name: rec.workshop_name,
      workshop_contact: rec.workshop_contact || '',
      maintenance_type: rec.maintenance_type,
      status: rec.status,
      start_date: rec.start_date ? rec.start_date.split('T')[0] : '',
      end_date: rec.end_date ? rec.end_date.split('T')[0] : '',
      work_done: rec.work_done || '',
      odometer_reading: rec.odometer_reading || 0,
      cost: rec.cost || 0,
      invoice_number: rec.invoice_number || '',
      remarks: rec.remarks || '',
    });
    setFormError('');
    setIsModalOpen(true);
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.vehicle_id) {
      setFormError('Please select a vehicle.');
      return;
    }
    if (!formData.workshop_name.trim()) {
      setFormError('Workshop name is required.');
      return;
    }

    if (editingRecord) {
      updateMutation.mutate({ id: editingRecord.id, payload: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleExport = () => {
    const exportData = records.map(r => ({
      ID: r.id,
      Vehicle: r.vehicle?.plate_number || 'N/A',
      Ref_ID: r.vehicle?.ref_id || 'N/A',
      Maintenance_Type: r.maintenance_type,
      Status: r.status,
      Start_Date: r.start_date ? new Date(r.start_date).toLocaleDateString() : '',
      End_Date: r.end_date ? new Date(r.end_date).toLocaleDateString() : '',
      Cost_SAR: r.cost,
      Workshop: r.workshop_name,
      Contact: r.workshop_contact || '',
      Odometer_km: r.odometer_reading,
      Work_Done: r.work_done || '',
      Invoice_No: r.invoice_number || '',
      Remarks: r.remarks || '',
    }));
    exportToCSV(exportData, `vehicle_maintenance_report_${new Date().toISOString().split('T')[0]}`);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'In_Progress':
      case 'In Progress':
        return <Badge className="bg-amber-50 text-amber-700 border-amber-200 font-bold">IN PROGRESS</Badge>;
      case 'Scheduled':
        return <Badge className="bg-blue-50 text-blue-700 border-blue-200 font-bold">SCHEDULED</Badge>;
      case 'Completed':
        return <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 font-bold">COMPLETED</Badge>;
      case 'Cancelled':
        return <Badge className="bg-rose-50 text-rose-700 border-rose-200 font-bold">CANCELLED</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getTypeBadge = (type: string) => {
    switch (type) {
      case 'Renewal':
        return <Badge className="bg-purple-50 text-purple-700 border-purple-200 font-bold">RENEWAL / ISTIMARA</Badge>;
      case 'Repair':
        return <Badge className="bg-rose-50 text-rose-700 border-rose-200 font-bold">REPAIR</Badge>;
      case 'Inspection':
        return <Badge className="bg-indigo-50 text-indigo-700 border-indigo-200 font-bold">INSPECTION</Badge>;
      case 'Emergency':
        return <Badge className="bg-amber-50 text-amber-700 border-amber-200 font-bold">EMERGENCY</Badge>;
      default:
        return <Badge className="bg-slate-100 text-slate-700 border-slate-200 font-bold">ROUTINE SERVICE</Badge>;
    }
  };

  return (
    <DashboardLayout active="Vehicles" title="Vehicle Maintenance">
      <div className="px-4 sm:px-6 pb-6 space-y-6 animate-fade-in max-w-[1400px] mx-auto w-full">

        {/* ── 1. Top Header Bar & Actions ─────────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[11px] font-extrabold text-slate-700 dark:text-slate-300 flex items-center gap-1.5 select-none">
              <Building2 className="w-3.5 h-3.5 text-indigo-500" />
              <span>MERCON Logistics</span>
              <ChevronsUpDown className="w-3 h-3 text-slate-400" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  Vehicle Maintenance & Renewals
                </h1>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Log service history, renewal expenses, work done details, and workshop maintenance schedules.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
            >
              <Download className="w-3.5 h-3.5 text-slate-500" />
              Export CSV
            </Button>

            <Button
              size="sm"
              onClick={handleOpenCreateModal}
              className="h-9 gap-1.5 text-xs font-bold bg-[#E8450F] hover:bg-[#d03c0b] text-white shadow-sm shadow-[#E8450F]/20"
            >
              <Plus className="w-4 h-4" />
              Schedule Maintenance
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => refetch()}
              className="h-9 w-9 p-0 text-slate-500 hover:text-slate-700"
              title="Refresh Data"
            >
              <RotateCw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* ── 2. Instrument-Panel KPI Cards ───────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {/* Card 1: Total Expense Cost */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs p-4 relative overflow-hidden">
            <div className="flex items-center justify-between pb-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                Total Maintenance Expense
              </span>
              <div className="w-8 h-8 rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-600 flex items-center justify-center">
                <DollarSign size={16} />
              </div>
            </div>
            <div className="text-2xl font-mono font-black text-slate-900 dark:text-slate-100">
              SAR {kpis.total_cost.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 font-semibold mt-1 flex items-center gap-1">
              <span className="text-rose-500 font-bold flex items-center gap-0.5">
                <ArrowUp className="w-3 h-3 text-rose-500" />
                Operational Cost
              </span>
              <span>• {records.length} records</span>
            </div>
          </Card>

          {/* Card 2: Active Maintenance */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs p-4 relative overflow-hidden">
            <div className="flex items-center justify-between pb-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                In-Progress Service
              </span>
              <div className="w-8 h-8 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-amber-600 flex items-center justify-center">
                <Wrench size={16} />
              </div>
            </div>
            <div className="text-2xl font-mono font-black text-amber-600 dark:text-amber-400">
              {kpis.active_count} Vehicles
            </div>
            <div className="text-[11px] text-slate-500 font-semibold mt-1">
              Currently in workshop repair
            </div>
          </Card>

          {/* Card 3: Renewals & Scheduled */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs p-4 relative overflow-hidden">
            <div className="flex items-center justify-between pb-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                Renewals & Scheduled
              </span>
              <div className="w-8 h-8 rounded-xl bg-purple-50 dark:bg-purple-950/40 text-purple-600 flex items-center justify-center">
                <Calendar size={16} />
              </div>
            </div>
            <div className="text-2xl font-mono font-black text-purple-600 dark:text-purple-400">
              {kpis.scheduled_count} Scheduled
            </div>
            <div className="text-[11px] text-slate-500 font-semibold mt-1">
              Renewal cost: SAR {kpis.renewal_cost.toLocaleString()}
            </div>
          </Card>

          {/* Card 4: Completed Services */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs p-4 relative overflow-hidden">
            <div className="flex items-center justify-between pb-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                Completed Repairs
              </span>
              <div className="w-8 h-8 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center">
                <CheckCircle2 size={16} />
              </div>
            </div>
            <div className="text-2xl font-mono font-black text-emerald-600 dark:text-emerald-400">
              {kpis.completed_count} Records
            </div>
            <div className="text-[11px] text-slate-500 font-semibold mt-1">
              Fully serviced & verified
            </div>
          </Card>

        </div>

        {/* ── 3. Toolbar & Control Bar ────────────────────────────────────── */}
        <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 rounded-2xl shadow-2xs">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            
            {/* Search Input */}
            <div className="relative flex-1 w-full">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Search vehicle plate, workshop, invoice, or work done..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 text-xs h-9 bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700"
              />
            </div>

            {/* Filter Dropdowns */}
            <div className="flex items-center gap-2.5 w-full sm:w-auto flex-wrap">
              
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="h-9 text-xs w-[140px] bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="In_Progress">In Progress</SelectItem>
                  <SelectItem value="Scheduled">Scheduled</SelectItem>
                  <SelectItem value="Completed">Completed</SelectItem>
                  <SelectItem value="Cancelled">Cancelled</SelectItem>
                </SelectContent>
              </Select>

              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="h-9 text-xs w-[160px] bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                  <SelectValue placeholder="Maintenance Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="Routine">Routine Service</SelectItem>
                  <SelectItem value="Repair">Repair</SelectItem>
                  <SelectItem value="Inspection">Inspection</SelectItem>
                  <SelectItem value="Renewal">Renewal / Istimara</SelectItem>
                  <SelectItem value="Emergency">Emergency</SelectItem>
                </SelectContent>
              </Select>

              {/* Segmented View Switcher */}
              <div className="flex items-center p-1 bg-slate-100 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
                <button
                  onClick={() => setViewMode('list')}
                  className={cn(
                    "px-2.5 py-1 text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5",
                    viewMode === 'list' ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xs" : "text-slate-500 hover:text-slate-900"
                  )}
                >
                  <List className="w-3.5 h-3.5" />
                  List
                </button>
                <button
                  onClick={() => setViewMode('grid')}
                  className={cn(
                    "px-2.5 py-1 text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5",
                    viewMode === 'grid' ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xs" : "text-slate-500 hover:text-slate-900"
                  )}
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  Grid
                </button>
              </div>

            </div>

          </div>
        </Card>

        {/* ── 4. Data Table Ledger & Empty States ─────────────────────────── */}
        <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs overflow-hidden">
          
          <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-indigo-500" />
              <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Maintenance Ledger
              </CardTitle>
            </div>
            <span className="text-xs font-mono font-bold text-slate-400">
              {records.length} records found
            </span>
          </CardHeader>

          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-12 text-center text-slate-400 animate-pulse text-xs font-semibold">
                Loading maintenance service records...
              </div>
            ) : records.length === 0 ? (
              <div className="p-16 flex flex-col items-center justify-center text-center">
                <div className="w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 mb-3">
                  <FileText className="w-8 h-8" />
                </div>
                <h3 className="text-base font-extrabold text-slate-900 dark:text-slate-100">
                  No Maintenance Records Found
                </h3>
                <p className="text-xs text-slate-500 max-w-sm mt-1 mb-4">
                  There are no service, repair, or renewal logs matching your search filter criteria.
                </p>
                <Button size="sm" onClick={handleOpenCreateModal} className="text-xs font-bold bg-[#E8450F] text-white">
                  + Schedule First Service
                </Button>
              </div>
            ) : viewMode === 'list' ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                      <th className="px-5 py-3.5">Vehicle / Ref</th>
                      <th className="px-5 py-3.5">Type</th>
                      <th className="px-5 py-3.5">Start Date</th>
                      <th className="px-5 py-3.5">End Date</th>
                      <th className="px-5 py-3.5">Expense (SAR)</th>
                      <th className="px-5 py-3.5">Workshop / Contact</th>
                      <th className="px-5 py-3.5">Work Done / Details</th>
                      <th className="px-5 py-3.5">Status</th>
                      <th className="px-5 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {records.map((r) => (
                      <tr key={r.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                        
                        {/* Vehicle info */}
                        <td 
                          className="px-5 py-4 cursor-pointer hover:underline"
                          onClick={() => navigate(`/maintenance/${r.id}`)}
                        >
                          <div className="font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                            <Truck className="w-3.5 h-3.5 text-indigo-500" />
                            {r.vehicle?.plate_number || 'TRK-UNKNOWN'}
                          </div>
                          <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                            {r.vehicle?.ref_id || 'Ref N/A'} • {r.odometer_reading ? `${r.odometer_reading.toLocaleString()} km` : '0 km'}
                          </div>
                        </td>

                        {/* Type */}
                        <td className="px-5 py-4">
                          {getTypeBadge(r.maintenance_type)}
                        </td>

                        {/* Dates */}
                        <td className="px-5 py-4 font-mono font-medium text-slate-700 dark:text-slate-300">
                          {r.start_date ? new Date(r.start_date).toLocaleDateString() : r.service_date ? new Date(r.service_date).toLocaleDateString() : 'N/A'}
                        </td>

                        <td className="px-5 py-4 font-mono font-medium text-slate-700 dark:text-slate-300">
                          {r.end_date ? new Date(r.end_date).toLocaleDateString() : '—'}
                        </td>

                        {/* Cost */}
                        <td className="px-5 py-4 font-mono font-extrabold text-rose-600 dark:text-rose-400 text-sm">
                          SAR {(r.cost || 0).toLocaleString()}
                        </td>

                        {/* Workshop */}
                        <td className="px-5 py-4">
                          <div className="font-semibold text-slate-800 dark:text-slate-200">
                            {r.workshop_name}
                          </div>
                          {r.workshop_contact && (
                            <div className="text-[10px] text-slate-400 font-mono mt-0.5 flex items-center gap-1">
                              <Phone className="w-3 h-3 text-slate-400" />
                              {r.workshop_contact}
                            </div>
                          )}
                        </td>

                        {/* Work Done */}
                        <td className="px-5 py-4 max-w-[220px]">
                          <p className="text-slate-700 dark:text-slate-300 truncate font-medium" title={r.work_done || r.remarks || ''}>
                            {r.work_done || r.remarks || 'Standard Service Maintenance'}
                          </p>
                          {r.invoice_number && (
                            <span className="text-[9px] font-mono text-slate-400 block mt-0.5">
                              Inv: {r.invoice_number}
                            </span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="px-5 py-4">
                          {getStatusBadge(r.status)}
                        </td>

                        {/* Actions */}
                        <td className="px-5 py-4 text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm" className="h-8 px-2 text-xs font-semibold gap-1">
                                Actions <ChevronDown className="w-3 h-3 text-slate-400" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-40 text-xs font-medium">
                              <DropdownMenuItem onClick={() => navigate(`/maintenance/${r.id}`)}>
                                <Eye className="w-3.5 h-3.5 mr-2 text-indigo-500" /> View Details
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => handleOpenEditModal(r)}>
                                <Edit2 className="w-3.5 h-3.5 mr-2 text-slate-500" /> Edit Log
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem onClick={() => setRecordToDelete(r)} className="text-rose-600 focus:text-rose-600">
                                <Trash2 className="w-3.5 h-3.5 mr-2 text-rose-500" /> Delete Record
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </td>

                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              /* Grid View */
              <div className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {records.map((r) => (
                  <Card key={r.id} className="border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 p-4 rounded-xl space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="font-extrabold text-sm text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                        <Truck className="w-4 h-4 text-indigo-500" />
                        {r.vehicle?.plate_number || 'TRK-UNKNOWN'}
                      </div>
                      {getStatusBadge(r.status)}
                    </div>

                    <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-200/60 dark:border-slate-700/60">
                      <div>{getTypeBadge(r.maintenance_type)}</div>
                      <div className="font-mono font-extrabold text-rose-600 dark:text-rose-400">
                        SAR {(r.cost || 0).toLocaleString()}
                      </div>
                    </div>

                    <div className="text-xs space-y-1 text-slate-600 dark:text-slate-300">
                      <p><strong>Workshop:</strong> {r.workshop_name}</p>
                      <p><strong>Start:</strong> {r.start_date ? new Date(r.start_date).toLocaleDateString() : 'N/A'}</p>
                      <p><strong>End:</strong> {r.end_date ? new Date(r.end_date).toLocaleDateString() : '—'}</p>
                      <p className="line-clamp-2"><strong>Work Done:</strong> {r.work_done || r.remarks || 'N/A'}</p>
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-200/60 dark:border-slate-700/60">
                      <Button size="sm" variant="outline" onClick={() => handleOpenEditModal(r)} className="h-7 text-xs">
                        Edit
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setRecordToDelete(r)} className="h-7 text-xs text-rose-600">
                        Delete
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {/* Pagination Controls */}
            {maintenanceRes?.meta && maintenanceRes.meta.total_pages > 1 && (
              <div className="px-5 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 flex items-center justify-between text-xs">
                <span className="text-slate-500 font-medium">
                  Showing page <strong className="text-slate-900 dark:text-slate-100">{maintenanceRes.meta.page}</strong> of <strong className="text-slate-900 dark:text-slate-100">{maintenanceRes.meta.total_pages}</strong> ({maintenanceRes.meta.total} records)
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={page <= 1}
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    className="h-8 px-3 text-xs"
                  >
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={page >= maintenanceRes.meta.total_pages}
                    onClick={() => setPage(p => p + 1)}
                    className="h-8 px-3 text-xs"
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </CardContent>

        </Card>

      </div>

      {/* ── 5. Create / Edit Maintenance Modal ─────────────────────────── */}
      <Dialog open={isModalOpen} onOpenChange={(open) => !open && setIsModalOpen(false)}>
        <DialogContent className="max-w-xl rounded-2xl p-0 overflow-hidden border-slate-200 dark:border-slate-800 max-h-[90vh] flex flex-col">
          
          <DialogHeader className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 shrink-0">
            <DialogTitle className="text-base font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Wrench className="w-5 h-5 text-[#E8450F]" />
              {editingRecord ? 'Edit Maintenance Record' : 'Schedule New Maintenance'}
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-500 mt-1">
              Enter vehicle maintenance details, start/end dates, renewal expense, and work done description.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleFormSubmit} className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
            
            {formError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs font-bold text-rose-700 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              
              {/* Vehicle Selection */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Vehicle Asset *</Label>
                <Select
                  value={formData.vehicle_id}
                  onValueChange={(val) => setFormData(prev => ({ ...prev, vehicle_id: val }))}
                >
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue placeholder="Select Vehicle" />
                  </SelectTrigger>
                  <SelectContent>
                    {vehicles.map((v) => (
                      <SelectItem key={v.id} value={v.id}>
                        {v.plate_number} ({v.ref_id || 'Ref N/A'})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Maintenance Type */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Maintenance Type *</Label>
                <Select
                  value={formData.maintenance_type}
                  onValueChange={(val: MaintenanceType) => setFormData(prev => ({ ...prev, maintenance_type: val }))}
                >
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue placeholder="Select Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Routine">Routine Service</SelectItem>
                    <SelectItem value="Repair">Repair</SelectItem>
                    <SelectItem value="Inspection">Inspection</SelectItem>
                    <SelectItem value="Renewal">Renewal / Istimara</SelectItem>
                    <SelectItem value="Emergency">Emergency</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Status */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Maintenance Status *</Label>
                <Select
                  value={formData.status}
                  onValueChange={(val: MaintenanceStatus) => setFormData(prev => ({ ...prev, status: val }))}
                >
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue placeholder="Select Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Scheduled">Scheduled</SelectItem>
                    <SelectItem value="In_Progress">In Progress</SelectItem>
                    <SelectItem value="Completed">Completed</SelectItem>
                    <SelectItem value="Cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Expense Cost */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Cost / Renewal Expense (SAR) *</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.cost}
                  onChange={(e) => setFormData(prev => ({ ...prev, cost: parseFloat(e.target.value) || 0 }))}
                  placeholder="0.00"
                  className="h-9 text-xs"
                />
              </div>

              {/* Start Date */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Start Date ("When Put") *</Label>
                <Input
                  type="date"
                  value={formData.start_date}
                  onChange={(e) => setFormData(prev => ({ ...prev, start_date: e.target.value }))}
                  className="h-9 text-xs"
                />
              </div>

              {/* End Date */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">End Date ("When Ends")</Label>
                <Input
                  type="date"
                  value={formData.end_date || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, end_date: e.target.value }))}
                  className="h-9 text-xs"
                />
              </div>

              {/* Workshop Name */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Workshop / Service Center *</Label>
                <Input
                  value={formData.workshop_name}
                  onChange={(e) => setFormData(prev => ({ ...prev, workshop_name: e.target.value }))}
                  placeholder="e.g. Al-Riyadh Heavy Fleet Service"
                  className="h-9 text-xs"
                />
              </div>

              {/* Workshop Contact */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Workshop Contact Phone</Label>
                <Input
                  value={formData.workshop_contact || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, workshop_contact: e.target.value }))}
                  placeholder="+966 5x xxx xxxx"
                  className="h-9 text-xs"
                />
              </div>

              {/* Odometer Reading */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Odometer Reading (km)</Label>
                <Input
                  type="number"
                  value={formData.odometer_reading}
                  onChange={(e) => setFormData(prev => ({ ...prev, odometer_reading: parseFloat(e.target.value) || 0 }))}
                  placeholder="184500"
                  className="h-9 text-xs"
                />
              </div>

              {/* Invoice Number */}
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Invoice Ref Number</Label>
                <Input
                  value={formData.invoice_number || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, invoice_number: e.target.value }))}
                  placeholder="INV-9921"
                  className="h-9 text-xs"
                />
              </div>

            </div>

            {/* Work Done Details */}
            <div className="space-y-1.5 pt-2">
              <Label className="text-xs font-bold">Work Done Details ("What All Was Done") *</Label>
              <textarea
                value={formData.work_done || ''}
                onChange={(e) => setFormData(prev => ({ ...prev, work_done: e.target.value }))}
                placeholder="Specify all repairs, replaced parts, engine oil specs, brake pad renewals, Istimara renewals..."
                rows={3}
                className="w-full p-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs focus:ring-2 focus:ring-[#E8450F]"
              />
            </div>

            {/* Remarks */}
            <div className="space-y-1.5">
              <Label className="text-xs font-bold">Additional Remarks / Notes</Label>
              <Input
                value={formData.remarks || ''}
                onChange={(e) => setFormData(prev => ({ ...prev, remarks: e.target.value }))}
                placeholder="Internal notes or next service recommendations"
                className="h-9 text-xs"
              />
            </div>

            <DialogFooter className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-2 shrink-0">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setIsModalOpen(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="text-xs bg-[#E8450F] hover:bg-[#d03c0b] text-white font-bold px-4"
              >
                {createMutation.isPending || updateMutation.isPending ? 'Saving...' : editingRecord ? 'Update Record' : 'Save Maintenance'}
              </Button>
            </DialogFooter>

          </form>
        </DialogContent>
      </Dialog>

      {/* ── 6. Delete Confirmation Modal ───────────────────────────────── */}
      <Dialog open={!!recordToDelete} onOpenChange={(open) => !open && setRecordToDelete(null)}>
        <DialogContent className="max-w-md rounded-2xl p-0 overflow-hidden border-slate-200 dark:border-slate-800">
          <DialogHeader className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-rose-50/50 dark:bg-rose-950/20">
            <div className="flex items-center gap-2 text-rose-600">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <DialogTitle className="text-base font-extrabold">Delete Maintenance Record</DialogTitle>
            </div>
            <DialogDescription className="text-xs text-slate-500 mt-1">
              Are you sure you want to delete this maintenance record for vehicle <strong className="text-slate-900 dark:text-slate-100">{recordToDelete?.vehicle?.plate_number}</strong>?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="px-6 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setRecordToDelete(null)}
              className="text-xs"
            >
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={deleteMutation.isPending}
              onClick={() => recordToDelete && deleteMutation.mutate(recordToDelete.id)}
              className="text-xs bg-rose-600 hover:bg-rose-700 text-white font-bold px-4"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </DashboardLayout>
  );
}
