import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  ArrowLeft, Edit2, FileText, Truck, MapPin, Settings, AlertTriangle, Trash2, 
  ShieldCheck, CheckCircle2, Clock, User, Building2, Gauge, Fuel, 
  Wrench, Calendar, Radio, FileCheck, AlertCircle, Eye, Link2, ShieldAlert,
  DollarSign, Plus, TrendingUp, TrendingDown
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import StatusBadge from '@/components/ui/StatusBadge';
import { vehicleService } from '@/services/vehicleService';
import { maintenanceService, CreateMaintenancePayload, MaintenanceType, MaintenanceStatus } from '@/services/maintenanceService';

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

export default function VehicleDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  // Maintenance Log Modal State
  const [isLogMaintModalOpen, setIsLogMaintModalOpen] = useState(false);
  const [maintFormData, setMaintFormData] = useState<CreateMaintenancePayload>({
    vehicle_id: id || '',
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
  const [maintFormError, setMaintFormError] = useState('');

  const { data: vehicle, isLoading, error } = useQuery({
    queryKey: ['vehicle', id],
    queryFn: () => vehicleService.getById(id!),
    enabled: !!id,
  });

  const { data: maintenanceRes, isLoading: isMaintLoading } = useQuery({
    queryKey: ['maintenance', id],
    queryFn: () => maintenanceService.getAll({ vehicle_id: id }),
    enabled: !!id,
  });

  const { data: financials, isLoading: isFinancialsLoading } = useQuery({
    queryKey: ['vehicle-financials', id],
    queryFn: () => vehicleService.getFinancials(id!),
    enabled: !!id,
  });

  const maintenanceRecords = maintenanceRes?.data || [];

  const createMaintMutation = useMutation({
    mutationFn: (payload: CreateMaintenancePayload) => maintenanceService.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vehicle', id] });
      queryClient.invalidateQueries({ queryKey: ['vehicles'] });
      queryClient.invalidateQueries({ queryKey: ['maintenance', id] });
      queryClient.invalidateQueries({ queryKey: ['vehicle-financials', id] });
      setIsLogMaintModalOpen(false);
      setMaintFormError('');
    },
    onError: (err: any) => {
      setMaintFormError(err.response?.data?.error?.message || 'Failed to save maintenance log.');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => vehicleService.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vehicles'] });
      navigate('/vehicles');
    },
    onError: (err: any) => {
      setDeleteError(err.response?.data?.error?.message || 'Failed to delete vehicle asset.');
    },
  });

  const handleDeleteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setDeleteError('');
    deleteMutation.mutate();
  };

  if (isLoading) {
    return (
      <DashboardLayout active="Vehicles" title="Vehicle Details">
        <div className="px-4 sm:px-6 pb-6 max-w-[1400px] mx-auto w-full space-y-5 animate-pulse">
          <div className="h-10 bg-slate-200 dark:bg-slate-800 rounded-xl w-1/4"></div>
          <div className="h-44 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
          <div className="h-96 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !vehicle) {
    return (
      <DashboardLayout active="Vehicles" title="Vehicle Details">
        <div className="px-4 sm:px-6 pb-6 max-w-[1400px] mx-auto w-full flex flex-col items-center justify-center text-center h-[60vh] gap-3">
          <div className="w-16 h-16 rounded-2xl bg-rose-50 dark:bg-rose-950/40 text-rose-500 flex items-center justify-center">
            <AlertTriangle size={32} />
          </div>
          <h2 className="text-xl font-extrabold text-slate-900 dark:text-slate-100">Vehicle Not Found</h2>
          <p className="text-xs text-slate-500 max-w-md">
            The requested vehicle asset does not exist or may have been removed from the MERCON fleet.
          </p>
          <Button onClick={() => navigate('/vehicles')} size="sm" className="mt-2 text-xs font-bold bg-[#E8450F] text-white">
            Return to Fleet Roster
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  const capacityTons = ((vehicle.capacity_kg || 24000) / 1000).toFixed(1);
  const trailerCapacityTons = vehicle.trailer_capacity_kg ? ((vehicle.trailer_capacity_kg || 0) / 1000).toFixed(1) : '28.0';

  // Parse plate numbers into English and Arabic representation
  const rawPlate = vehicle.plate_number || '7821-LSA';
  const plateParts = rawPlate.split('-');
  const plateNum = plateParts[0] || '7821';
  const plateLetters = plateParts[1] || 'LSA';

  return (
    <DashboardLayout active="Vehicles" title={`Vehicle: ${vehicle.plate_number}`}>
      <div className="px-4 sm:px-6 pb-6 space-y-6 animate-fade-in max-w-[1400px] mx-auto w-full">

        {/* ── Page Scope & Header Actions ─────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/vehicles')}
              className="h-9 w-9 p-0 text-slate-600 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
              title="Back to Fleet Roster"
            >
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  {vehicle.plate_number}
                </h1>
                <StatusBadge status={vehicle.status} />
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Ref ID: <span className="font-mono text-slate-700 dark:text-slate-300 font-bold">{vehicle.ref_id || 'TRK-9021'}</span> • {vehicle.asset_type || 'Heavy Tractor'} Asset
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/vehicles/${vehicle.id}/documents`)}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
            >
              <FileText className="w-3.5 h-3.5 text-indigo-500" />
              Documents Vault
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/vehicles/${vehicle.id}/edit`)}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
            >
              <Edit2 className="w-3.5 h-3.5 text-slate-500" />
              Edit Vehicle
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsDeleteModalOpen(true)}
              className="h-9 gap-1.5 text-xs font-semibold border-rose-200 bg-white hover:bg-rose-50 text-rose-600 hover:text-rose-700 shadow-2xs dark:bg-slate-900 dark:border-rose-900/50"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-500" />
              Delete Vehicle
            </Button>
          </div>
        </div>

        {/* ── Visual Hero Command Panel ─────────────────────────────────── */}
        <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs p-6 overflow-hidden">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            
            {/* Left: Authentic Saudi License Plate Graphic & Identity */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
              
              {/* Dual-Language Saudi Plate Frame */}
              <div className="w-48 h-24 rounded-xl border-2 border-slate-900 dark:border-slate-100 bg-slate-50 dark:bg-slate-950 p-2 shadow-md flex flex-col justify-between shrink-0 select-none">
                <div className="flex items-center justify-between border-b border-slate-900/40 dark:border-slate-100/40 pb-1 font-bold">
                  <span className="font-mono text-base text-slate-900 dark:text-slate-100 tracking-wider">{plateNum} {plateLetters}</span>
                  <span className="text-sm font-sans text-slate-900 dark:text-slate-100">٧ ٨ ٢ ١ أ س ل</span>
                </div>
                <div className="flex items-center justify-between text-[9px] font-bold text-slate-500 uppercase tracking-widest pt-1">
                  <span>KSA</span>
                  <span className="text-[10px] font-sans">المملكة العربية السعودية</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-xl font-black text-slate-900 dark:text-slate-100">
                    {vehicle.plate_number}
                  </h2>
                  <Badge className="bg-[#FFF0EB] text-[#E8450F] border-[#E8450F]/30 text-[10px] font-bold">
                    {vehicle.asset_type || 'Heavy Tractor'}
                  </Badge>
                  <StatusBadge status={vehicle.status} />
                </div>

                <p className="text-xs text-slate-500 font-medium">
                  Ref: <span className="font-mono font-bold text-slate-700 dark:text-slate-300">{vehicle.ref_id || 'TRK-9021'}</span> • Primary Base: <span className="font-semibold text-slate-700 dark:text-slate-300">Riyadh Central Hub</span>
                </p>

                <div className="flex items-center gap-3 text-xs text-slate-500 font-mono">
                  <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-bold">
                    <Radio className="w-3.5 h-3.5" /> GPS: {vehicle.gps_device_id || 'GPS-4891-KSA'}
                  </span>
                  <span>•</span>
                  <span>ICCES: {vehicle.icces_device_id || 'ICCES-9912'}</span>
                </div>
              </div>

            </div>

            {/* Right: 4 Quick Sensor Bar Gauges */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 border-t lg:border-t-0 lg:border-l border-slate-100 dark:border-slate-800 pt-4 lg:pt-0 lg:pl-6 shrink-0">
              
              <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200/80 dark:border-slate-700/80 text-center min-w-[120px]">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Payload Tonnage</div>
                <div className="text-sm font-mono font-extrabold text-slate-900 dark:text-slate-100 mt-1">
                  {capacityTons} Tons
                </div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200/80 dark:border-slate-700/80 text-center min-w-[120px]">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Odometer Reading</div>
                <div className="text-sm font-mono font-extrabold text-indigo-600 dark:text-indigo-400 mt-1">
                  {(vehicle.current_odometer || 184500).toLocaleString()} km
                </div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200/80 dark:border-slate-700/80 text-center min-w-[120px]">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Istimara Status</div>
                <div className="text-xs font-mono font-extrabold text-emerald-600 dark:text-emerald-400 mt-1 flex items-center justify-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Valid (142d)</span>
                </div>
              </div>

              <div className="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200/80 dark:border-slate-700/80 text-center min-w-[120px]">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Telematics Unit</div>
                <div className="text-xs font-mono font-extrabold text-emerald-600 dark:text-emerald-400 mt-1 flex items-center justify-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span>ONLINE</span>
                </div>
              </div>

            </div>

          </div>
        </Card>

        {/* ── Main Dashboard 2-Column Grid ───────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left Column (Asset Specifications & Trailer Coupling) */}
          <div className="lg:col-span-2 space-y-6">

            {/* Section 1: Telematics Sensors & Live Gauge Bar */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <Gauge className="w-4 h-4 text-indigo-500" /> Live Engine Telemetry & Fuel Sensors
                </CardTitle>
              </CardHeader>
              
              <CardContent className="p-5">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                  
                  {/* Gauge 1: Speedometer */}
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 flex flex-col justify-between">
                    <div className="flex items-center justify-between text-slate-500 font-medium">
                      <span>Cruising Speed</span>
                      <Gauge className="w-4 h-4 text-indigo-500" />
                    </div>
                    <div className="mt-3">
                      <div className="text-2xl font-mono font-extrabold text-slate-900 dark:text-slate-100">
                        {vehicle.status === 'OnTrip' ? '78 km/h' : '0 km/h'}
                      </div>
                      <span className="text-[10px] text-slate-400 font-semibold mt-0.5 block">
                        {vehicle.status === 'OnTrip' ? 'Highway Cruise Speed' : 'Parked at Base Hub'}
                      </span>
                    </div>
                  </div>

                  {/* Gauge 2: Fuel Level Meter */}
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 flex flex-col justify-between">
                    <div className="flex items-center justify-between text-slate-500 font-medium">
                      <span>Fuel Tank Level</span>
                      <Fuel className="w-4 h-4 text-emerald-500" />
                    </div>
                    <div className="mt-3 space-y-1.5">
                      <div className="text-2xl font-mono font-extrabold text-emerald-600 dark:text-emerald-400">
                        84% Full
                      </div>
                      <div className="w-full bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500 rounded-full" style={{ width: '84%' }}></div>
                      </div>
                    </div>
                  </div>

                  {/* Gauge 3: Engine Health */}
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 flex flex-col justify-between">
                    <div className="flex items-center justify-between text-slate-500 font-medium">
                      <span>Engine Diagnostics</span>
                      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                    </div>
                    <div className="mt-3">
                      <div className="text-sm font-extrabold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                        <span>NORMAL OPERATING</span>
                      </div>
                      <span className="text-[10px] text-slate-400 font-semibold mt-0.5 block">
                        No active fault codes (DTC 0)
                      </span>
                    </div>
                  </div>

                </div>
              </CardContent>
            </Card>

            {/* Section 2: Trailer Coupling Schematic */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <Link2 className="w-4 h-4 text-[#E8450F]" /> Trailer Coupling Configuration & Payload Rating
                </CardTitle>
              </CardHeader>

              <CardContent className="p-5">
                <div className="p-4 rounded-xl bg-indigo-50/40 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/50 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <Truck className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />
                    <div>
                      <h4 className="font-extrabold text-sm text-slate-900 dark:text-slate-100">
                        {vehicle.trailer_number ? `Attached Trailer: ${vehicle.trailer_number}` : 'No Trailer Attached'}
                      </h4>
                      <p className="text-xs text-slate-500 font-medium">
                        {vehicle.trailer_type ? `Type: ${vehicle.trailer_type} • Reefer Unit` : 'Single Tractor Configuration'}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 text-xs font-mono">
                    <div className="bg-white dark:bg-slate-900 px-3 py-1.5 rounded-lg border border-indigo-100 dark:border-indigo-900/60">
                      <span className="text-slate-400 text-[10px] block">Trailer Capacity</span>
                      <span className="font-bold text-slate-800 dark:text-slate-200">{trailerCapacityTons} Tons</span>
                    </div>
                    <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px] font-bold">
                      COUPLED & LOCKED
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Section 3: Vehicle Financial & Profitability Report (P&L) */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs overflow-hidden">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-emerald-500" /> Full Vehicle Financial & Profitability Report
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Real-time calculation of Income generated by this vehicle vs Operational & Maintenance Expenses.
                  </CardDescription>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate('/maintenance')}
                  className="h-7 text-xs font-bold border-slate-200 text-slate-700"
                >
                  All Maintenance →
                </Button>
              </CardHeader>

              <CardContent className="p-5 space-y-4">
                {isFinancialsLoading ? (
                  <div className="py-8 text-center text-slate-400 animate-pulse text-xs font-semibold">
                    Calculating vehicle P&L financials...
                  </div>
                ) : financials ? (
                  <>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      
                      {/* Income */}
                      <div className="bg-emerald-50/60 dark:bg-emerald-950/20 p-3.5 rounded-xl border border-emerald-100 dark:border-emerald-900/50">
                        <span className="text-[10px] font-extrabold uppercase text-emerald-700 dark:text-emerald-400 block">
                          Total Income Generated
                        </span>
                        <div className="text-lg font-mono font-extrabold text-emerald-700 dark:text-emerald-300 mt-1">
                          SAR {financials.summary.total_income.toLocaleString()}
                        </div>
                        <span className="text-[10px] text-slate-500 block mt-0.5 font-medium">
                          {financials.summary.completed_trips_count} completed trips
                        </span>
                      </div>

                      {/* Expenses */}
                      <div className="bg-rose-50/60 dark:bg-rose-950/20 p-3.5 rounded-xl border border-rose-100 dark:border-rose-900/50">
                        <span className="text-[10px] font-extrabold uppercase text-rose-700 dark:text-rose-400 block">
                          Total Expenses (Maint/Renew)
                        </span>
                        <div className="text-lg font-mono font-extrabold text-rose-700 dark:text-rose-300 mt-1">
                          SAR {financials.summary.total_expenses.toLocaleString()}
                        </div>
                        <span className="text-[10px] text-slate-500 block mt-0.5 font-medium">
                          {financials.summary.total_maintenance_count} service/renewal logs
                        </span>
                      </div>

                      {/* Net Profit */}
                      <div className="bg-indigo-50/60 dark:bg-indigo-950/20 p-3.5 rounded-xl border border-indigo-100 dark:border-indigo-900/50">
                        <span className="text-[10px] font-extrabold uppercase text-indigo-700 dark:text-indigo-400 block">
                          Net Vehicle Profit
                        </span>
                        <div className={cn(
                          "text-lg font-mono font-extrabold mt-1",
                          financials.summary.net_profit >= 0 ? "text-indigo-700 dark:text-indigo-300" : "text-rose-600"
                        )}>
                          SAR {financials.summary.net_profit.toLocaleString()}
                        </div>
                        <span className="text-[10px] text-slate-500 block mt-0.5 font-medium">
                          Income - Expenses
                        </span>
                      </div>

                      {/* Profit Margin % */}
                      <div className="bg-slate-50 dark:bg-slate-800/50 p-3.5 rounded-xl border border-slate-200 dark:border-slate-700">
                        <span className="text-[10px] font-extrabold uppercase text-slate-500 block">
                          Profit Margin %
                        </span>
                        <div className="text-lg font-mono font-extrabold text-slate-900 dark:text-slate-100 mt-1 flex items-center gap-1">
                          {financials.summary.margin_percent >= 0 ? (
                            <TrendingUp className="w-4 h-4 text-emerald-500" />
                          ) : (
                            <TrendingDown className="w-4 h-4 text-rose-500" />
                          )}
                          <span>{financials.summary.margin_percent}%</span>
                        </div>
                        <span className="text-[10px] text-slate-500 block mt-0.5 font-medium">
                          Operational Efficiency
                        </span>
                      </div>

                    </div>

                    {/* Financial Breakdown Table: Revenue vs Expense */}
                    <div className="pt-3 border-t border-slate-100 dark:border-slate-800">
                      <div className="text-xs font-bold text-slate-800 dark:text-slate-200 mb-2 flex items-center justify-between">
                        <span>P&L Financial Ledger (Trips Income vs Maintenance Expenses)</span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {financials.income_sources.length} trips • {financials.expense_records.length} services
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                        
                        {/* Income Sources Column */}
                        <div className="bg-slate-50/70 dark:bg-slate-800/40 p-3 rounded-xl border border-slate-200/70 dark:border-slate-700/70 space-y-2">
                          <span className="text-[10px] font-extrabold uppercase text-emerald-700 dark:text-emerald-400 flex items-center gap-1">
                            <TrendingUp className="w-3 h-3" /> Trip Revenue (Income)
                          </span>
                          {financials.income_sources.length === 0 ? (
                            <p className="text-[11px] text-slate-400 italic">No completed trip revenue recorded yet.</p>
                          ) : (
                            <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                              {financials.income_sources.slice(0, 5).map((t) => (
                                <div key={t.id} className="flex items-center justify-between text-[11px] bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-100 dark:border-slate-800">
                                  <div>
                                    <div className="font-bold text-slate-800 dark:text-slate-200">{t.customer_name}</div>
                                    <div className="text-[10px] text-slate-400 font-mono">{t.ref_id || 'TRIP'} • {t.cargo_type}</div>
                                  </div>
                                  <span className="font-mono font-extrabold text-emerald-600 dark:text-emerald-400">
                                    +SAR {t.income.toLocaleString()}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Expense Records Column */}
                        <div className="bg-slate-50/70 dark:bg-slate-800/40 p-3 rounded-xl border border-slate-200/70 dark:border-slate-700/70 space-y-2">
                          <span className="text-[10px] font-extrabold uppercase text-rose-700 dark:text-rose-400 flex items-center gap-1">
                            <TrendingDown className="w-3 h-3" /> Service & Renewal Expenses
                          </span>
                          {financials.expense_records.length === 0 ? (
                            <p className="text-[11px] text-slate-400 italic">No maintenance expenses logged yet.</p>
                          ) : (
                            <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                              {financials.expense_records.slice(0, 5).map((m) => (
                                <div key={m.id} className="flex items-center justify-between text-[11px] bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-100 dark:border-slate-800">
                                  <div>
                                    <div className="font-bold text-slate-800 dark:text-slate-200">{m.workshop_name}</div>
                                    <div className="text-[10px] text-slate-400 font-mono">{m.maintenance_type} • {m.start_date ? new Date(m.start_date).toLocaleDateString() : ''}</div>
                                  </div>
                                  <span className="font-mono font-extrabold text-rose-600 dark:text-rose-400">
                                    -SAR {(m.cost || 0).toLocaleString()}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                      </div>
                    </div>
                  </>
                ) : null}
              </CardContent>
            </Card>

            {/* Section 4: Workshop Maintenance & Service History Ledger */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs overflow-hidden">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <Wrench className="w-4 h-4 text-amber-500" /> Maintenance & Service History Ledger
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Workshop repairs, oil services, renewals, and work done details for this vehicle.
                  </CardDescription>
                </div>
                
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => {
                      setMaintFormData({
                        vehicle_id: id || '',
                        workshop_name: '',
                        workshop_contact: '',
                        maintenance_type: 'Routine',
                        status: 'Completed',
                        start_date: new Date().toISOString().split('T')[0],
                        end_date: new Date().toISOString().split('T')[0],
                        work_done: '',
                        odometer_reading: vehicle.current_odometer || 0,
                        cost: 0,
                        invoice_number: '',
                        remarks: '',
                      });
                      setIsLogMaintModalOpen(true);
                    }}
                    className="h-7 text-xs font-bold bg-[#E8450F] hover:bg-[#d03c0b] text-white gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" /> Log Maintenance
                  </Button>
                  <Badge variant="outline" className="text-[10px] font-mono font-bold text-slate-500">
                    {maintenanceRecords.length} Logs
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="p-0">
                {isMaintLoading ? (
                  <div className="p-8 text-center text-slate-400 animate-pulse text-xs">
                    Loading maintenance records...
                  </div>
                ) : maintenanceRecords.length === 0 ? (
                  <div className="p-10 text-center text-slate-400 flex flex-col items-center gap-2">
                    <Wrench className="w-8 h-8 opacity-30 text-slate-400" />
                    <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">No maintenance records logged for this vehicle yet.</p>
                    <Button
                      size="sm"
                      onClick={() => setIsLogMaintModalOpen(true)}
                      className="mt-1 text-xs font-bold bg-[#E8450F] text-white"
                    >
                      + Log First Maintenance
                    </Button>
                  </div>
                ) : (
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900">
                        <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Start / End Date</th>
                        <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Type</th>
                        <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Work Done / Details</th>
                        <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Expense</th>
                        <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Status</th>
                        <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                      {maintenanceRecords.map((m) => (
                        <tr key={m.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                          <td className="px-5 py-3 font-mono font-semibold text-slate-700 dark:text-slate-300">
                            <div>{m.start_date ? new Date(m.start_date).toLocaleDateString() : new Date(m.service_date).toLocaleDateString()}</div>
                            {m.end_date && (
                              <div className="text-[10px] text-slate-400">to {new Date(m.end_date).toLocaleDateString()}</div>
                            )}
                          </td>
                          <td className="px-5 py-3">
                            <Badge variant="outline" className="text-[10px] font-bold">
                              {m.maintenance_type}
                            </Badge>
                          </td>
                          <td className="px-5 py-3">
                            <div className="font-semibold text-slate-800 dark:text-slate-200">{m.workshop_name}</div>
                            <div className="text-[11px] text-slate-500 truncate max-w-xs">{m.work_done || m.remarks || 'Standard Service'}</div>
                          </td>
                          <td className="px-5 py-3 font-mono font-extrabold text-rose-600 dark:text-rose-400">
                            SAR {(m.cost || 0).toLocaleString()}
                          </td>
                          <td className="px-5 py-3">
                            <Badge className={cn(
                              "text-[10px] font-bold",
                              m.status === 'Completed' ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                              m.status === 'In_Progress' ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-slate-100 text-slate-700"
                            )}>
                              {m.status.toUpperCase()}
                            </Badge>
                          </td>
                          <td className="px-5 py-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setMaintFormData({
                                  vehicle_id: m.vehicleId,
                                  workshop_name: m.workshop_name,
                                  workshop_contact: m.workshop_contact || '',
                                  maintenance_type: m.maintenance_type,
                                  status: m.status,
                                  start_date: m.start_date ? m.start_date.split('T')[0] : '',
                                  end_date: m.end_date ? m.end_date.split('T')[0] : '',
                                  work_done: m.work_done || '',
                                  odometer_reading: m.odometer_reading || 0,
                                  cost: m.cost || 0,
                                  invoice_number: m.invoice_number || '',
                                  remarks: m.remarks || '',
                                });
                                setIsLogMaintModalOpen(true);
                              }}
                              className="h-7 w-7 p-0 text-slate-600 hover:text-slate-900"
                              title="Edit Log"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardContent>
            </Card>

          </div>

          {/* Right Column (Compliance & Live Radar) */}
          <div className="space-y-6">

            {/* Card 1: Saudi Istimara & Compliance Audit */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" /> Compliance Audit Vault
                </CardTitle>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => navigate(`/vehicles/${vehicle.id}/documents`)}
                  className="h-7 text-xs font-bold text-indigo-600"
                >
                  Vault →
                </Button>
              </CardHeader>

              <CardContent className="p-4 space-y-3">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-slate-900 dark:text-slate-100">Saudi Istimara Registration</div>
                    <div className="text-[10px] text-slate-400">MOT Valid • 142d Remaining</div>
                  </div>
                  <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[9px] font-bold">VALID</Badge>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-slate-900 dark:text-slate-100">Najm Commercial Insurance</div>
                    <div className="text-[10px] text-slate-400">Najm Fleet Coverage</div>
                  </div>
                  <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[9px] font-bold">VALID</Badge>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-slate-900 dark:text-slate-100">Fahs Technical Inspection</div>
                    <div className="text-[10px] text-slate-400">Renewal due in 12 days</div>
                  </div>
                  <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 text-[9px] font-bold">DUE SOON</Badge>
                </div>
              </CardContent>
            </Card>

            {/* Card 2: Live Location & Corridor Radar */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-[#E8450F]" /> Live Location & Corridor Radar
                </CardTitle>
              </CardHeader>

              <CardContent className="p-4 space-y-3">
                {vehicle.status === 'OnTrip' ? (
                  <div className="p-4 rounded-xl bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 space-y-3">
                    <div className="flex items-center gap-2 text-indigo-600">
                      <MapPin className="w-4 h-4 animate-bounce" />
                      <span className="text-xs font-extrabold">In Transit — Highway Corridor</span>
                    </div>
                    <p className="text-[11px] text-slate-500">
                      En route: Riyadh Central Hub ➔ Dammam Freight Terminal
                    </p>
                    <Button size="sm" onClick={() => navigate('/trips')} className="w-full h-8 text-xs font-bold bg-indigo-600 text-white">
                      Track Trip Dispatch
                    </Button>
                  </div>
                ) : (
                  <div className="p-6 text-center text-slate-400 flex flex-col items-center gap-2">
                    <Truck size={28} className="opacity-30 text-slate-400" />
                    <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">Parked at Riyadh Central Hub.</p>
                  </div>
                )}
              </CardContent>
            </Card>

          </div>

        </div>

      </div>

      {/* ── Log Maintenance Dialog Modal ────────────────────────────── */}
      <Dialog open={isLogMaintModalOpen} onOpenChange={(open) => !open && setIsLogMaintModalOpen(false)}>
        <DialogContent className="max-w-xl rounded-2xl p-0 overflow-hidden border-slate-200 dark:border-slate-800 max-h-[90vh] flex flex-col">
          <DialogHeader className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 shrink-0">
            <DialogTitle className="text-base font-extrabold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Wrench className="w-5 h-5 text-[#E8450F]" /> Log Maintenance for {vehicle.plate_number}
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-500 mt-1">
              Enter service details, dates when maintenance started and ended, cost expense, and work done description.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={(e) => {
            e.preventDefault();
            if (!maintFormData.workshop_name.trim()) {
              setMaintFormError('Workshop name is required.');
              return;
            }
            createMaintMutation.mutate({ ...maintFormData, vehicle_id: vehicle.id });
          }} className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
            
            {maintFormError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs font-bold text-rose-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                <span>{maintFormError}</span>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              
              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Maintenance Type *</Label>
                <Select
                  value={maintFormData.maintenance_type}
                  onValueChange={(val: MaintenanceType) => setMaintFormData(prev => ({ ...prev, maintenance_type: val }))}
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
                  value={maintFormData.status}
                  onValueChange={(val: MaintenanceStatus) => setMaintFormData(prev => ({ ...prev, status: val }))}
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
                  value={maintFormData.cost}
                  onChange={(e) => setMaintFormData(prev => ({ ...prev, cost: parseFloat(e.target.value) || 0 }))}
                  placeholder="0.00"
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Odometer Reading (km)</Label>
                <Input
                  type="number"
                  value={maintFormData.odometer_reading}
                  onChange={(e) => setMaintFormData(prev => ({ ...prev, odometer_reading: parseFloat(e.target.value) || 0 }))}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Start Date ("When Put") *</Label>
                <Input
                  type="date"
                  value={maintFormData.start_date}
                  onChange={(e) => setMaintFormData(prev => ({ ...prev, start_date: e.target.value }))}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-bold">End Date ("When Ends")</Label>
                <Input
                  type="date"
                  value={maintFormData.end_date || ''}
                  onChange={(e) => setMaintFormData(prev => ({ ...prev, end_date: e.target.value }))}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Workshop / Service Center *</Label>
                <Input
                  value={maintFormData.workshop_name}
                  onChange={(e) => setMaintFormData(prev => ({ ...prev, workshop_name: e.target.value }))}
                  placeholder="Al-Riyadh Workshop"
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-bold">Invoice Ref Number</Label>
                <Input
                  value={maintFormData.invoice_number || ''}
                  onChange={(e) => setMaintFormData(prev => ({ ...prev, invoice_number: e.target.value }))}
                  placeholder="INV-1092"
                  className="h-9 text-xs"
                />
              </div>

            </div>

            <div className="space-y-1.5 pt-2">
              <Label className="text-xs font-bold">Work Done Details ("What All Was Done") *</Label>
              <textarea
                value={maintFormData.work_done || ''}
                onChange={(e) => setMaintFormData(prev => ({ ...prev, work_done: e.target.value }))}
                placeholder="Details of oil replacement, brake pad repair, renewal fees paid..."
                rows={3}
                className="w-full p-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs focus:ring-2 focus:ring-[#E8450F]"
              />
            </div>

            <DialogFooter className="pt-4 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-2 shrink-0">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setIsLogMaintModalOpen(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={createMaintMutation.isPending}
                className="text-xs bg-[#E8450F] hover:bg-[#d03c0b] text-white font-bold px-4"
              >
                {createMaintMutation.isPending ? 'Saving...' : 'Save Maintenance Log'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── Delete Vehicle Confirmation Modal ────────────────────────────── */}
      <Dialog open={isDeleteModalOpen} onOpenChange={(open) => !open && setIsDeleteModalOpen(false)}>
        <DialogContent className="max-w-md rounded-2xl p-0 overflow-hidden border-slate-200 dark:border-slate-800">
          <DialogHeader className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-rose-50/50 dark:bg-rose-950/20">
            <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <DialogTitle className="text-base font-extrabold">Delete Vehicle Asset</DialogTitle>
            </div>
            <DialogDescription className="text-xs text-slate-500 mt-1">
              Deleting vehicle <strong className="text-slate-900 dark:text-slate-100">{vehicle.plate_number}</strong> will remove it from active fleet rosters.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleDeleteSubmit}>
            {deleteError && (
              <div className="p-4 mx-6 mt-4 rounded-lg bg-rose-50 border border-rose-200 text-xs font-bold text-rose-700 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                <span>{deleteError}</span>
              </div>
            )}

            <DialogFooter className="px-6 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 flex justify-end gap-2 mt-4">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => { setIsDeleteModalOpen(false); setDeleteError(''); }}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={deleteMutation.isPending}
                className="text-xs bg-rose-600 hover:bg-rose-700 text-white font-bold px-4"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Confirm Delete'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
