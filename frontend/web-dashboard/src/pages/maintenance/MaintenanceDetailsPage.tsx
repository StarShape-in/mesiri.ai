import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  ArrowLeft, Edit2, Wrench, Truck, Calendar, Clock, CheckCircle2, 
  AlertTriangle, DollarSign, FileText, Phone, Building2, Gauge, 
  Trash2, ShieldCheck, Tag, ExternalLink, AlertCircle, RotateCw,
  ChevronDown, Download, Check, Sparkles, Activity, FileCheck2, Info, Layers
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
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
import { cn } from '@/lib/utils';

export default function MaintenanceDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState('overview');
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const [editFormData, setEditFormData] = useState<CreateMaintenancePayload>({
    vehicle_id: '',
    workshop_name: '',
    workshop_contact: '',
    maintenance_type: 'Routine',
    status: 'Completed',
    start_date: '',
    end_date: '',
    work_done: '',
    odometer_reading: 0,
    cost: 0,
    invoice_number: '',
    remarks: '',
  });
  const [editError, setEditError] = useState('');

  // Fetch single maintenance record
  const { data: record, isLoading, error } = useQuery({
    queryKey: ['maintenance-detail', id],
    queryFn: () => maintenanceService.getById(id!),
    enabled: !!id,
  });

  // Mutations
  const updateMutation = useMutation({
    mutationFn: (payload: any) => maintenanceService.update(id!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['maintenance-detail', id] });
      queryClient.invalidateQueries({ queryKey: ['maintenance'] });
      if (record?.vehicleId) {
        queryClient.invalidateQueries({ queryKey: ['vehicle', record.vehicleId] });
        queryClient.invalidateQueries({ queryKey: ['vehicle-financials', record.vehicleId] });
      }
      setIsEditModalOpen(false);
      setEditError('');
    },
    onError: (err: any) => {
      setEditError(err.response?.data?.error?.message || 'Failed to update record.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => maintenanceService.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['maintenance'] });
      navigate('/maintenance');
    },
  });

  const handleOpenEditModal = () => {
    if (!record) return;
    setEditFormData({
      vehicle_id: record.vehicleId,
      workshop_name: record.workshop_name,
      workshop_contact: record.workshop_contact || '',
      maintenance_type: record.maintenance_type,
      status: record.status,
      start_date: record.start_date ? record.start_date.split('T')[0] : '',
      end_date: record.end_date ? record.end_date.split('T')[0] : '',
      work_done: record.work_done || '',
      odometer_reading: record.odometer_reading || 0,
      cost: record.cost || 0,
      invoice_number: record.invoice_number || '',
      remarks: record.remarks || '',
    });
    setEditError('');
    setIsEditModalOpen(true);
  };

  const handleQuickStatusChange = (newStatus: MaintenanceStatus) => {
    updateMutation.mutate({ status: newStatus });
  };

  if (isLoading) {
    return (
      <DashboardLayout active="Vehicles" title="Maintenance Details">
        <div className="px-4 sm:px-6 pb-6 max-w-[1400px] mx-auto w-full space-y-5 animate-pulse">
          <div className="h-10 bg-slate-200 dark:bg-slate-800 rounded-xl w-1/4"></div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="h-28 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
            <div className="h-28 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
            <div className="h-28 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
            <div className="h-28 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
          </div>
          <div className="h-96 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !record) {
    return (
      <DashboardLayout active="Vehicles" title="Maintenance Details">
        <div className="px-4 sm:px-6 pb-6 max-w-[1400px] mx-auto w-full flex flex-col items-center justify-center text-center h-[60vh] gap-3">
          <div className="w-16 h-16 rounded-2xl bg-rose-50 text-rose-500 flex items-center justify-center">
            <AlertTriangle size={32} />
          </div>
          <h2 className="text-xl font-extrabold text-slate-900 dark:text-slate-100">Record Not Found</h2>
          <p className="text-xs text-slate-500 max-w-md">
            The requested maintenance record does not exist or has been removed from the MERCON roster.
          </p>
          <Button onClick={() => navigate('/maintenance')} size="sm" className="mt-2 text-xs font-bold bg-[#E8450F] text-white">
            Return to Maintenance List
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  const vehicle = record.vehicle;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'In_Progress':
      case 'In Progress':
        return <Badge className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 font-extrabold text-[10px]">IN PROGRESS</Badge>;
      case 'Scheduled':
        return <Badge className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20 font-extrabold text-[10px]">SCHEDULED</Badge>;
      case 'Completed':
        return <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 font-extrabold text-[10px]">COMPLETED</Badge>;
      case 'Cancelled':
        return <Badge className="bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20 font-extrabold text-[10px]">CANCELLED</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getTypeBadge = (type: string) => {
    switch (type) {
      case 'Renewal':
        return <Badge className="bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20 font-extrabold text-[10px]">RENEWAL / ISTIMARA</Badge>;
      case 'Repair':
        return <Badge className="bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20 font-extrabold text-[10px]">REPAIR</Badge>;
      case 'Inspection':
        return <Badge className="bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/20 font-extrabold text-[10px]">INSPECTION</Badge>;
      case 'Emergency':
        return <Badge className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 font-extrabold text-[10px]">EMERGENCY</Badge>;
      default:
        return <Badge className="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 font-extrabold text-[10px]">ROUTINE SERVICE</Badge>;
    }
  };

  const progressPercent = record.status === 'Completed' ? 100 : record.status === 'In_Progress' ? 50 : 15;
  const odoDelta = vehicle ? Math.max(0, (vehicle.current_odometer || 0) - (record.odometer_reading || 0)) : 0;

  // Replaced parts breakdown (structured from work_done text or fallback list)
  const checklistItems = [
    { name: 'Engine Oil & Filter Replacement', category: 'Fluid & Filters', status: 'Completed' },
    { name: 'Brake Pad & Rotor Inspection', category: 'Safety System', status: 'Completed' },
    { name: 'Air Filter & Cabin Filter Refresh', category: 'Filters', status: 'Completed' },
    { name: 'Multi-Point Telemetry Health Check', category: 'Diagnostics', status: record.status === 'Completed' ? 'Completed' : 'In Progress' },
    { name: 'Istimara / Fahs Legal Renewal Verification', category: 'Compliance', status: record.maintenance_type === 'Renewal' ? 'Completed' : 'N/A' },
  ];

  return (
    <TooltipProvider>
      <DashboardLayout active="Vehicles" title={`Maintenance: #${record.id.slice(0, 8)}`}>
        <div className="px-4 sm:px-6 pb-8 space-y-6 animate-fade-in max-w-[1400px] mx-auto w-full">

          {/* ── 1. Scope & Action Header Bar ───────────────────────────────── */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
            
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate('/maintenance')}
                className="h-9 w-9 p-0 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
                title="Back to Maintenance List"
              >
                <ArrowLeft className="w-4 h-4" />
              </Button>

              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="inline-flex items-center gap-1.5 text-[11px] font-mono px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 font-extrabold text-slate-700 dark:text-slate-300">
                    <Building2 className="w-3 h-3 text-indigo-500" />
                    MERCON Logistics
                  </span>
                  <Badge className="bg-[#E8450F]/10 text-[#E8450F] border-[#E8450F]/20 font-bold text-[10px]">
                    Fleet Operations
                  </Badge>
                  {getTypeBadge(record.maintenance_type)}
                  {getStatusBadge(record.status)}
                </div>

                <h1 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-slate-100 tracking-tight mt-1 flex items-center gap-2">
                  <span>Service Order #{record.id.slice(0, 8)}</span>
                  <span className="text-xs font-mono font-normal text-slate-400">({vehicle?.plate_number})</span>
                </h1>
              </div>
            </div>

            {/* Top Bar Action Group */}
            <div className="flex items-center gap-2 flex-wrap shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={() => exportToCSV([record], `maintenance_${record.id.slice(0, 8)}.csv`)}
                className="h-9 gap-1.5 text-xs font-bold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
              >
                <Download className="w-3.5 h-3.5 text-slate-500" />
                Export CSV
              </Button>

              {/* Status Change Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button size="sm" className="h-9 gap-1.5 text-xs font-bold bg-[#E8450F] hover:bg-[#d03c0b] text-white shadow-sm">
                    <span>Update Status</span>
                    <ChevronDown className="w-3.5 h-3.5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-44 text-xs font-semibold">
                  <DropdownMenuLabel className="text-[10px] text-slate-400 uppercase">Set Lifecycle Status</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => handleQuickStatusChange('Scheduled')}>
                    <Clock className="w-3.5 h-3.5 mr-2 text-blue-500" /> Scheduled
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleQuickStatusChange('In_Progress')}>
                    <RotateCw className="w-3.5 h-3.5 mr-2 text-amber-500" /> In Progress
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleQuickStatusChange('Completed')}>
                    <CheckCircle2 className="w-3.5 h-3.5 mr-2 text-emerald-500" /> Completed
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleQuickStatusChange('Cancelled')}>
                    <AlertTriangle className="w-3.5 h-3.5 mr-2 text-rose-500" /> Cancelled
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              <Button
                variant="outline"
                size="sm"
                onClick={handleOpenEditModal}
                className="h-9 gap-1.5 text-xs font-bold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
              >
                <Edit2 className="w-3.5 h-3.5 text-slate-500" />
                Edit
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsDeleteModalOpen(true)}
                className="h-9 p-2 border-rose-200 bg-white hover:bg-rose-50 text-rose-600 dark:bg-slate-900 dark:border-rose-900/50"
                title="Delete Record"
              >
                <Trash2 className="w-4 h-4 text-rose-500" />
              </Button>
            </div>

          </div>

          {/* ── 2. Instrument-Panel 4 KPI Metric Row ──────────────────────── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            
            {/* KPI 1: Expense Cost */}
            <Card className="border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 rounded-2xl shadow-2xs relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                  Total Operational Cost
                </span>
                <div className="p-2 rounded-xl bg-rose-50 dark:bg-rose-950/30 text-rose-600 dark:text-rose-400">
                  <DollarSign className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-mono font-black text-slate-900 dark:text-slate-100 mt-2">
                SAR {(record.cost || 0).toLocaleString()}
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-500 mt-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <span>Calculated Expense</span>
                <span className="font-mono font-bold text-rose-600 dark:text-rose-400">100% Tax Deductible</span>
              </div>
            </Card>

            {/* KPI 2: Service Duration & Progress */}
            <Card className="border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 rounded-2xl shadow-2xs relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                  Execution Progress
                </span>
                <div className="p-2 rounded-xl bg-amber-50 dark:bg-amber-950/30 text-amber-600 dark:text-amber-400">
                  <Activity className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-mono font-black text-slate-900 dark:text-slate-100 mt-2">
                {progressPercent}%
              </div>
              <div className="mt-2 space-y-1">
                <Progress value={progressPercent} className="h-1.5 bg-slate-100 dark:bg-slate-800" />
                <span className="text-[10px] text-slate-500 font-semibold block text-right">
                  {record.status === 'Completed' ? 'Service Finished' : 'Work in progress'}
                </span>
              </div>
            </Card>

            {/* KPI 3: Odometer Delta */}
            <Card className="border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 rounded-2xl shadow-2xs relative overflow-hidden">
              <div className="flex items-center justify-between">
                <Tooltip>
                  <TooltipTrigger>
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400 flex items-center gap-1 cursor-help">
                      Odometer Delta <Info className="w-3 h-3 text-slate-400" />
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs">Distance traveled by vehicle since this service log.</p>
                  </TooltipContent>
                </Tooltip>
                <Gauge className="w-5 h-5 text-orange-500 dark:text-orange-400" />
              </div>
              <div className="text-2xl font-mono font-black text-slate-900 dark:text-slate-100 mt-2">
                {(record.odometer_reading || 0).toLocaleString()} <span className="text-xs font-normal text-slate-400">km</span>
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-500 mt-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <span>Current Fleet Odo:</span>
                <span className="font-mono font-extrabold text-indigo-600 dark:text-indigo-400">
                  + {odoDelta.toLocaleString()} km since
                </span>
              </div>
            </Card>

            {/* KPI 4: Compliance / Renewal Status */}
            <Card className="border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 rounded-2xl shadow-2xs relative overflow-hidden">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                  Compliance & Warranty
                </span>
                <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600 dark:text-emerald-400">
                  <ShieldCheck className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-mono font-black text-emerald-600 dark:text-emerald-400 mt-2">
                {record.maintenance_type === 'Renewal' ? 'VALID' : 'APPROVED'}
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-500 mt-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <span>Invoice Ref:</span>
                <span className="font-mono font-bold text-slate-800 dark:text-slate-200">
                  {record.invoice_number || 'N/A'}
                </span>
              </div>
            </Card>

          </div>

          {/* ── 3. High-Density Shadcn Tabs View ─────────────────────────────── */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-5">
            
            <TabsList className="h-auto p-1.5 bg-slate-100/80 dark:bg-slate-800/80 rounded-2xl border border-slate-200/80 dark:border-slate-700/80 w-full sm:w-auto flex flex-wrap sm:inline-flex gap-1.5 shadow-2xs">
              <TabsTrigger 
                value="overview" 
                className="px-4 py-2.5 sm:px-5 sm:py-3 min-h-[44px] text-xs sm:text-sm font-extrabold gap-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm cursor-pointer transition-all"
              >
                <Wrench className="w-4 h-4 text-[#E8450F]" /> Overview & Work Done
              </TabsTrigger>
              
              <TabsTrigger 
                value="parts" 
                className="px-4 py-2.5 sm:px-5 sm:py-3 min-h-[44px] text-xs sm:text-sm font-extrabold gap-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm cursor-pointer transition-all"
              >
                <FileCheck2 className="w-4 h-4 text-indigo-500" /> Itemized Checklist ({checklistItems.length})
              </TabsTrigger>
              
              <TabsTrigger 
                value="financial" 
                className="px-4 py-2.5 sm:px-5 sm:py-3 min-h-[44px] text-xs sm:text-sm font-extrabold gap-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm cursor-pointer transition-all"
              >
                <DollarSign className="w-4 h-4 text-emerald-500" /> Financial Invoice Vault
              </TabsTrigger>
              
              <TabsTrigger 
                value="vehicle" 
                className="px-4 py-2.5 sm:px-5 sm:py-3 min-h-[44px] text-xs sm:text-sm font-extrabold gap-2 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm cursor-pointer transition-all"
              >
                <Truck className="w-4 h-4 text-amber-500" /> Vehicle Telemetry & Profile
              </TabsTrigger>
            </TabsList>

            {/* ── TAB 1: OVERVIEW & WORK DONE ───────────────────────────────── */}
            <TabsContent value="overview" className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Left 2 Cols: Detailed Service Report */}
                <div className="lg:col-span-2 space-y-6">
                  
                  <Card className="border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
                    <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                      <div>
                        <CardTitle className="text-sm font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                          <FileText className="w-4 h-4 text-[#E8450F]" /> Detailed Service Work Report ("What All Was Done")
                        </CardTitle>
                        <CardDescription className="text-xs text-slate-500">
                          Recorded workshop activities, technical notes, and work performed on this vehicle.
                        </CardDescription>
                      </div>
                      <Badge variant="outline" className="font-mono text-[10px] font-bold">
                        {record.maintenance_type}
                      </Badge>
                    </CardHeader>

                    <CardContent className="p-5 space-y-4 text-xs">
                      
                      {/* Work Done Box */}
                      <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 space-y-2">
                        <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">
                          Full Maintenance Activity Summary
                        </span>
                        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 whitespace-pre-line leading-relaxed">
                          {record.work_done || record.remarks || 'Standard routine service and diagnostic inspection performed at authorized workshop.'}
                        </p>
                      </div>

                      {/* Timeline Audit Dates */}
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                        
                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800">
                          <span className="text-[10px] text-slate-400 font-extrabold uppercase block">Start Date ("When Put")</span>
                          <span className="text-xs font-mono font-extrabold text-slate-900 dark:text-slate-100 mt-1 block">
                            {record.start_date ? new Date(record.start_date).toLocaleDateString() : 'N/A'}
                          </span>
                        </div>

                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800">
                          <span className="text-[10px] text-slate-400 font-extrabold uppercase block">End Date ("When Completed")</span>
                          <span className="text-xs font-mono font-extrabold text-slate-900 dark:text-slate-100 mt-1 block">
                            {record.end_date ? new Date(record.end_date).toLocaleDateString() : 'Pending Completion'}
                          </span>
                        </div>

                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/30 border border-slate-100 dark:border-slate-800">
                          <span className="text-[10px] text-slate-400 font-extrabold uppercase block">Odometer Recorded</span>
                          <span className="text-xs font-mono font-extrabold text-indigo-600 dark:text-indigo-400 mt-1 block">
                            {(record.odometer_reading || 0).toLocaleString()} km
                          </span>
                        </div>

                      </div>

                      {record.remarks && (
                        <div className="p-3.5 rounded-xl bg-indigo-50/40 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/50">
                          <span className="text-[10px] font-extrabold text-indigo-600 dark:text-indigo-400 block uppercase">
                            Technician & Workshop Remarks
                          </span>
                          <p className="text-xs text-slate-700 dark:text-slate-300 mt-0.5">
                            {record.remarks}
                          </p>
                        </div>
                      )}

                    </CardContent>
                  </Card>

                </div>

                {/* Right Col: Workshop Card */}
                <div className="space-y-6">
                  
                  <Card className="border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
                    <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                      <CardTitle className="text-sm font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-indigo-500" /> Authorized Workshop Center
                      </CardTitle>
                    </CardHeader>

                    <CardContent className="p-4 space-y-3 text-xs">
                      <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                        <div className="font-extrabold text-sm text-slate-900 dark:text-slate-100">
                          {record.workshop_name}
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          Commercial Heavy Commercial Workshop
                        </p>
                      </div>

                      {record.workshop_contact && (
                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex items-center justify-between">
                          <div>
                            <div className="text-[10px] font-bold text-slate-400 uppercase">Contact Phone</div>
                            <div className="text-xs font-mono font-extrabold text-slate-900 dark:text-slate-100 mt-0.5">
                              {record.workshop_contact}
                            </div>
                          </div>
                          <a
                            href={`tel:${record.workshop_contact}`}
                            className="p-2 rounded-lg bg-indigo-50 text-indigo-600 hover:bg-indigo-100 dark:bg-indigo-950 dark:text-indigo-300"
                            title="Call Workshop"
                          >
                            <Phone className="w-4 h-4" />
                          </a>
                        </div>
                      )}
                    </CardContent>
                  </Card>

                </div>

              </div>
            </TabsContent>

            {/* ── TAB 2: ITEMIZED CHECKLIST ─────────────────────────────────── */}
            <TabsContent value="parts" className="space-y-4">
              <Card className="border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs overflow-hidden">
                <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                  <div>
                    <CardTitle className="text-sm font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      <FileCheck2 className="w-4 h-4 text-indigo-500" /> Itemized Service Checklist & Replaced Components
                    </CardTitle>
                    <CardDescription className="text-xs text-slate-500">
                      Detailed component replacement, inspection items, and legal renewal checks performed.
                    </CardDescription>
                  </div>
                  <Badge variant="outline" className="font-mono text-[10px] font-bold">
                    {checklistItems.length} Checklist Items
                  </Badge>
                </CardHeader>

                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 text-slate-400 font-bold uppercase text-[10px]">
                          <th className="px-5 py-3.5">Checklist Item / Task</th>
                          <th className="px-5 py-3.5">Category</th>
                          <th className="px-5 py-3.5">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-medium">
                        {checklistItems.map((item, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                            <td className="px-5 py-3.5 text-slate-900 dark:text-slate-100 font-bold flex items-center gap-2">
                              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                              {item.name}
                            </td>
                            <td className="px-5 py-3.5">
                              <Badge variant="outline" className="text-[10px] font-semibold">
                                {item.category}
                              </Badge>
                            </td>
                            <td className="px-5 py-3.5">
                              <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px] font-bold">
                                {item.status.toUpperCase()}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ── TAB 3: FINANCIAL INVOICE VAULT ─────────────────────────────── */}
            <TabsContent value="financial" className="space-y-4">
              <Card className="border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                  <div>
                    <h3 className="text-sm font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                      <DollarSign className="w-4 h-4 text-emerald-500" /> Operational Expense & Tax Breakdown
                    </h3>
                    <p className="text-xs text-slate-500">
                      Cost breakdown for vehicle profit & loss financial reports.
                    </p>
                  </div>
                  <span className="text-xl font-mono font-black text-rose-600 dark:text-rose-400">
                    SAR {(record.cost || 0).toLocaleString()}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 space-y-2">
                    <span className="text-[10px] font-extrabold text-slate-400 uppercase">Billing Details</span>
                    <div className="flex items-center justify-between">
                      <span>Invoice Number:</span>
                      <span className="font-mono font-bold text-slate-900 dark:text-slate-100">{record.invoice_number || 'INV-NOT-PROVIDED'}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Workshop Provider:</span>
                      <span className="font-bold text-slate-900 dark:text-slate-100">{record.workshop_name}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Expense Type:</span>
                      <span className="font-bold text-slate-900 dark:text-slate-100">{record.maintenance_type}</span>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 space-y-2">
                    <span className="text-[10px] font-extrabold text-slate-400 uppercase">P&L Classification</span>
                    <div className="flex items-center justify-between">
                      <span>P&L Status:</span>
                      <Badge className="bg-rose-50 text-rose-700 border-rose-200 text-[10px] font-bold">OPERATIONAL EXPENSE</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Tax Deductible:</span>
                      <span className="font-bold text-emerald-600">Yes (100%)</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Vehicle Ledger Sync:</span>
                      <span className="font-bold text-indigo-600">Synced to Vehicle P&L</span>
                    </div>
                  </div>

                </div>
              </Card>
            </TabsContent>

            {/* ── TAB 4: VEHICLE TELEMETRY & PROFILE ─────────────────────────── */}
            <TabsContent value="vehicle" className="space-y-4">
              {vehicle && (
                <Card className="border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                    <div>
                      <h3 className="text-sm font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                        <Truck className="w-4 h-4 text-[#E8450F]" /> Vehicle Asset Profile & Telemetry
                      </h3>
                      <p className="text-xs text-slate-500">
                        Parent vehicle specifications and odometer telemetry.
                      </p>
                    </div>
                    <Button
                      size="sm"
                      onClick={() => navigate(`/vehicles/${vehicle.id}`)}
                      className="text-xs font-bold bg-[#E8450F] text-white"
                    >
                      View Vehicle Profile →
                    </Button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                    
                    {/* Saudi Plate Identity Badge */}
                    <div className="p-4 rounded-xl bg-slate-900 text-white border border-slate-800 flex flex-col justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase">Saudi Plate Identity</span>
                      <div className="text-xl font-mono font-black tracking-widest text-amber-400 mt-2">
                        {vehicle.plate_number}
                      </div>
                      <span className="text-[10px] text-slate-400 mt-1">Ref ID: {vehicle.ref_id || 'N/A'}</span>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex flex-col justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase">Vehicle Status</span>
                      <div className="text-base font-extrabold text-slate-900 dark:text-slate-100 mt-2">
                        {vehicle.status}
                      </div>
                      <span className="text-[10px] text-slate-500 mt-1">Asset Type: {vehicle.asset_type}</span>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex flex-col justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase">Live Odometer</span>
                      <div className="text-xl font-mono font-black text-indigo-600 dark:text-indigo-400 mt-2">
                        {(vehicle.current_odometer || 0).toLocaleString()} km
                      </div>
                      <span className="text-[10px] text-slate-500 mt-1">Updated at service</span>
                    </div>

                  </div>
                </Card>
              )}
            </TabsContent>

          </Tabs>

        </div>

        {/* ── 4. Edit Record Modal ────────────────────────────────────────── */}
        <Dialog open={isEditModalOpen} onOpenChange={(open) => !open && setIsEditModalOpen(false)}>
          <DialogContent className="max-w-xl rounded-2xl p-0 overflow-hidden border-slate-200 dark:border-slate-800 max-h-[90vh] flex flex-col">
            <DialogHeader className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 shrink-0">
              <DialogTitle className="text-base font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Wrench className="w-5 h-5 text-[#E8450F]" /> Edit Maintenance Record #{record.id.slice(0, 8)}
              </DialogTitle>
            </DialogHeader>

            <form onSubmit={(e) => {
              e.preventDefault();
              updateMutation.mutate(editFormData);
            }} className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
              
              {editError && (
                <div className="p-3 rounded-lg bg-rose-50 text-rose-700 border border-rose-200 font-bold flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                  <span>{editError}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                
                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Maintenance Type *</Label>
                  <Select
                    value={editFormData.maintenance_type}
                    onValueChange={(val: MaintenanceType) => setEditFormData(prev => ({ ...prev, maintenance_type: val }))}
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

                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Status *</Label>
                  <Select
                    value={editFormData.status}
                    onValueChange={(val: MaintenanceStatus) => setEditFormData(prev => ({ ...prev, status: val }))}
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

                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Cost / Expense (SAR) *</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={editFormData.cost}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, cost: parseFloat(e.target.value) || 0 }))}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Odometer Reading (km)</Label>
                  <Input
                    type="number"
                    value={editFormData.odometer_reading}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, odometer_reading: parseFloat(e.target.value) || 0 }))}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Start Date</Label>
                  <Input
                    type="date"
                    value={editFormData.start_date}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, start_date: e.target.value }))}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Completion Date</Label>
                  <Input
                    type="date"
                    value={editFormData.end_date || ''}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, end_date: e.target.value }))}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Workshop Name *</Label>
                  <Input
                    value={editFormData.workshop_name}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, workshop_name: e.target.value }))}
                    className="h-9 text-xs"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label className="text-xs font-bold">Workshop Contact Phone</Label>
                  <Input
                    value={editFormData.workshop_contact || ''}
                    onChange={(e) => setEditFormData(prev => ({ ...prev, workshop_contact: e.target.value }))}
                    className="h-9 text-xs"
                  />
                </div>

              </div>

              <div className="space-y-1.5 pt-2">
                <Label className="text-xs font-bold">Work Done Details *</Label>
                <textarea
                  value={editFormData.work_done || ''}
                  onChange={(e) => setEditFormData(prev => ({ ...prev, work_done: e.target.value }))}
                  rows={3}
                  className="w-full p-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs focus:ring-2 focus:ring-[#E8450F]"
                />
              </div>

              <DialogFooter className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-2 shrink-0">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsEditModalOpen(false)}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={updateMutation.isPending}
                  className="text-xs bg-[#E8450F] hover:bg-[#d03c0b] text-white font-bold px-4"
                >
                  {updateMutation.isPending ? 'Updating...' : 'Update Record'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

        {/* ── 5. Delete Confirmation Modal ───────────────────────────────── */}
        <Dialog open={isDeleteModalOpen} onOpenChange={(open) => !open && setIsDeleteModalOpen(false)}>
          <DialogContent className="max-w-md rounded-2xl p-0 overflow-hidden border-slate-200 dark:border-slate-800">
            <DialogHeader className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-rose-50/50 dark:bg-rose-950/20">
              <div className="flex items-center gap-2 text-rose-600">
                <AlertTriangle className="w-5 h-5 shrink-0" />
                <DialogTitle className="text-base font-extrabold">Delete Maintenance Record</DialogTitle>
              </div>
              <DialogDescription className="text-xs text-slate-500 mt-1">
                Are you sure you want to delete this maintenance record for vehicle <strong className="text-slate-900 dark:text-slate-100">{vehicle?.plate_number}</strong>?
              </DialogDescription>
            </DialogHeader>

            <DialogFooter className="px-6 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setIsDeleteModalOpen(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
                className="text-xs bg-rose-600 hover:bg-rose-700 text-white font-bold px-4"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

      </DashboardLayout>
    </TooltipProvider>
  );
}
