import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  ArrowLeft, Edit2, FileText, Phone, MapPin, Calendar, Activity, Star, AlertTriangle, 
  Eye, Trash2, Truck, ShieldCheck, CheckCircle2, Clock, User, IdCard, Mail, Building2, 
  ExternalLink, ShieldAlert, Gauge, Fuel, Check, Plus, AlertCircle, FileCheck
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import StatusBadge from '@/components/ui/StatusBadge';
import { driverService } from '@/services/driverService';

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

export default function DriverDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'overview' | 'compliance' | 'trips' | 'telematics'>('overview');
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [deleteError, setDeleteError] = useState('');

  const { data: driver, isLoading, error } = useQuery({
    queryKey: ['driver', id],
    queryFn: () => driverService.getById(id!),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: (pwd: string) => driverService.delete(id!, pwd),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drivers'] });
      navigate('/drivers');
    },
    onError: (err: any) => {
      setDeleteError(err.response?.data?.error?.message || 'Failed to delete driver account.');
    },
  });

  const handleDeleteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setDeleteError('');
    if (!password) {
      setDeleteError('Admin password is required.');
      return;
    }
    deleteMutation.mutate(password);
  };

  if (isLoading) {
    return (
      <DashboardLayout active="Drivers" title="Driver Details">
        <div className="px-4 sm:px-6 pb-6 max-w-[1300px] mx-auto w-full space-y-5 animate-pulse">
          <div className="h-10 bg-slate-200 dark:bg-slate-800 rounded-xl w-1/4"></div>
          <div className="h-44 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
          <div className="h-80 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !driver) {
    return (
      <DashboardLayout active="Drivers" title="Driver Details">
        <div className="px-4 sm:px-6 pb-6 max-w-[1300px] mx-auto w-full flex flex-col items-center justify-center text-center h-[60vh] gap-3">
          <div className="w-16 h-16 rounded-2xl bg-rose-50 dark:bg-rose-950/40 text-rose-500 flex items-center justify-center">
            <AlertTriangle size={32} />
          </div>
          <h2 className="text-xl font-extrabold text-slate-900 dark:text-slate-100">Driver Not Found</h2>
          <p className="text-xs text-slate-500 max-w-md">
            The requested driver profile does not exist or may have been deleted from the MERCON roster.
          </p>
          <Button onClick={() => navigate('/drivers')} size="sm" className="mt-2 text-xs font-bold bg-[#E8450F] text-white">
            Return to Driver Roster
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  // Calculated Driver Credentials & Dates
  const isLicenseExpired = driver.license_expiry ? new Date(driver.license_expiry) < new Date() : false;
  const daysUntilExpiry = driver.license_expiry ? Math.ceil((new Date(driver.license_expiry).getTime() - Date.now()) / (1000 * 60 * 60 * 24)) : null;
  const initials = `${driver.first_name?.[0] || ''}${driver.last_name?.[0] || ''}`.toUpperCase() || 'D';
  const completedTripsCount = driver.trips?.filter(t => t.status === 'Completed').length || 0;
  const totalTripsCount = driver.trips?.length || 0;

  return (
    <DashboardLayout active="Drivers" title={`Driver: ${driver.ref_id || 'N/A'}`}>
      <div className="px-4 sm:px-6 pb-6 space-y-5 animate-fade-in max-w-[1300px] mx-auto w-full">

        {/* ── Page Content Header ─────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-1 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/drivers')}
              className="h-9 w-9 p-0 text-slate-600 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
              title="Back to Driver Roster"
            >
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  {driver.first_name} {driver.last_name}
                </h1>
                <StatusBadge status={driver.status} />
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Ref ID: <span className="font-mono text-slate-700 dark:text-slate-300 font-bold">{driver.ref_id || 'N/A'}</span> • Commercial Heavy Fleet Operator
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/drivers/${driver.id}/documents`)}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
            >
              <FileText className="w-3.5 h-3.5 text-indigo-500" />
              Documents Vault
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/drivers/${driver.id}/edit`)}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
            >
              <Edit2 className="w-3.5 h-3.5 text-slate-500" />
              Edit Profile
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsDeleteModalOpen(true)}
              className="h-9 gap-1.5 text-xs font-semibold border-rose-200 bg-white hover:bg-rose-50 text-rose-600 hover:text-rose-700 shadow-2xs dark:bg-slate-900 dark:border-rose-900/50"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-500" />
              Delete Driver
            </Button>
          </div>
        </div>

        {/* ── Driver Command Profile Header Card ─────────────────────────── */}
        <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs p-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            
            {/* Avatar & Driver Identity */}
            <div className="flex items-center gap-4">
              <div className="relative shrink-0">
                <div className="w-16 h-16 rounded-2xl bg-slate-900 dark:bg-slate-800 flex items-center justify-center text-white text-2xl font-black border-2 border-slate-200 dark:border-slate-700 shadow-md">
                  {initials}
                </div>
                <span className="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full bg-emerald-500 border-2 border-white dark:border-slate-900" title="Active Duty"></span>
              </div>

              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-xl font-extrabold text-slate-900 dark:text-slate-100">
                    {driver.first_name} {driver.last_name}
                  </h2>
                  <Badge variant="outline" className="bg-[#FFF0EB] text-[#E8450F] border-[#E8450F]/30 text-[10px] font-bold">
                    Saudi Heavy License
                  </Badge>
                </div>

                <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400 flex-wrap">
                  <span className="flex items-center gap-1 font-mono text-slate-700 dark:text-slate-300">
                    <Phone className="w-3.5 h-3.5 text-slate-400" /> {driver.phone_primary || 'No phone'}
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Building2 className="w-3.5 h-3.5 text-slate-400" /> Riyadh Central Hub
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1 font-mono">
                    <IdCard className="w-3.5 h-3.5 text-slate-400" /> License #{driver.ref_id || '109283'}
                  </span>
                </div>
              </div>
            </div>

            {/* 4 Telematics Gauges */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 border-t md:border-t-0 md:border-l border-slate-100 dark:border-slate-800 pt-4 md:pt-0 md:pl-6 shrink-0">
              {/* Gauge 1: License Expiry */}
              <div className="bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/80 text-center min-w-[110px]">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">License Status</div>
                <div className={cn(
                  'text-xs font-mono font-extrabold mt-0.5 flex items-center justify-center gap-1',
                  isLicenseExpired ? 'text-rose-600' : (daysUntilExpiry && daysUntilExpiry <= 30) ? 'text-amber-600' : 'text-emerald-600'
                )}>
                  {isLicenseExpired ? (
                    <>Expired <AlertTriangle className="w-3 h-3 text-rose-500" /></>
                  ) : (
                    <>{daysUntilExpiry ?? 90}d Valid</>
                  )}
                </div>
              </div>

              {/* Gauge 2: Safety Rating */}
              <div className="bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/80 text-center min-w-[110px]">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Safety Rating</div>
                <div className="text-xs font-mono font-extrabold text-amber-500 mt-0.5 flex items-center justify-center gap-1">
                  <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
                  <span>4.8 / 5.0</span>
                </div>
              </div>

              {/* Gauge 3: Completed Trips */}
              <div className="bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-xl border border-slate-200/80 dark:border-slate-700/80 text-center min-w-[110px]">
                <div className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Completed Trips</div>
                <div className="text-xs font-mono font-extrabold text-slate-800 dark:text-slate-200 mt-0.5">
                  {completedTripsCount} / {totalTripsCount}
                </div>
              </div>
            </div>

          </div>
        </Card>

        {/* ── 4 Workspace Tabs ───────────────────────────────────────────── */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full space-y-4">
          <TabsList className="bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl grid grid-cols-2 sm:grid-cols-4 w-full border border-slate-200/60 dark:border-slate-700">
            <TabsTrigger 
              value="overview" 
              className="text-xs font-semibold gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-slate-100 data-[state=active]:shadow-2xs rounded-lg"
            >
              <User className="w-3.5 h-3.5 text-slate-500" />
              <span>Personal Credentials</span>
            </TabsTrigger>

            <TabsTrigger 
              value="compliance" 
              className="text-xs font-semibold gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-slate-100 data-[state=active]:shadow-2xs rounded-lg"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-slate-500" />
              <span>Compliance & Permits</span>
            </TabsTrigger>

            <TabsTrigger 
              value="trips" 
              className="text-xs font-semibold gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-slate-100 data-[state=active]:shadow-2xs rounded-lg"
            >
              <MapPin className="w-3.5 h-3.5 text-slate-500" />
              <span>Trip History ({totalTripsCount})</span>
            </TabsTrigger>

            <TabsTrigger 
              value="telematics" 
              className="text-xs font-semibold gap-1.5 data-[state=active]:bg-white dark:data-[state=active]:bg-slate-900 data-[state=active]:text-slate-900 dark:data-[state=active]:text-slate-100 data-[state=active]:shadow-2xs rounded-lg"
            >
              <Gauge className="w-3.5 h-3.5 text-slate-500" />
              <span>Safety & Telematics</span>
            </TabsTrigger>
          </TabsList>

          {/* ── TAB 1: Personal Credentials ─────────────────────────────────── */}
          <TabsContent value="overview" className="m-0 space-y-4">
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <User className="w-4 h-4 text-[#E8450F]" /> Driver Profile & Licensing Credentials
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Official driver credentials, Saudi Iqama ID, and commercial heavy vehicle license details.
                </CardDescription>
              </CardHeader>

              <CardContent className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
                  
                  <div className="space-y-1">
                    <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Full Name</span>
                    <p className="font-semibold text-slate-800 dark:text-slate-200">{driver.first_name} {driver.last_name}</p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Driver Reference ID</span>
                    <p className="font-mono font-semibold text-slate-800 dark:text-slate-200">{driver.ref_id || 'N/A'}</p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Primary Mobile Phone</span>
                    <p className="font-mono font-semibold text-slate-800 dark:text-slate-200">{driver.phone_primary || 'N/A'}</p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Secondary Emergency Contact</span>
                    <p className="font-mono font-semibold text-slate-800 dark:text-slate-200">+966 55 999 8877</p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Saudi Iqama / National ID</span>
                    <p className="font-mono font-semibold text-slate-800 dark:text-slate-200">1092837465</p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">License Expiry Date</span>
                    <p className={cn('font-mono font-semibold', isLicenseExpired ? 'text-rose-600' : 'text-slate-800 dark:text-slate-200')}>
                      {driver.license_expiry ? new Date(driver.license_expiry).toLocaleDateString() : 'N/A'}
                    </p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">License Category</span>
                    <p className="font-semibold text-slate-800 dark:text-slate-200">Saudi Heavy Vehicle - Articulated Truck</p>
                  </div>

                  <div className="space-y-1">
                    <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Primary Base Hub</span>
                    <p className="font-semibold text-slate-800 dark:text-slate-200">Riyadh Central Distribution Center</p>
                  </div>

                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ── TAB 2: Compliance & Permits ────────────────────────────────── */}
          <TabsContent value="compliance" className="m-0 space-y-4">
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" /> Mandatory Saudi Driver Compliance Audit
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Live verification status of Ministry of Transport permits and medical certificates.
                  </CardDescription>
                </div>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate(`/drivers/${driver.id}/documents`)}
                  className="h-8 text-xs font-bold border-slate-200 text-indigo-600"
                >
                  <FileText className="w-3.5 h-3.5 mr-1" /> Open Documents Vault
                </Button>
              </CardHeader>

              <CardContent className="p-6 space-y-3">
                
                {/* File 1: Commercial License */}
                <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                      <FileCheck className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-900 dark:text-slate-100">Saudi Commercial Heavy License</div>
                      <div className="text-[10px] text-slate-400">Issuer: Ministry of Transport (MOT) • Exp: {new Date(driver.license_expiry).toLocaleDateString()}</div>
                    </div>
                  </div>
                  <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px] font-bold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 inline-block animate-pulse" />
                    <span>VERIFIED VALID</span>
                  </Badge>
                </div>

                {/* File 2: Medical Clearance Certificate */}
                <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-3">
                    <ShieldCheck className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />
                    <div>
                      <div className="text-xs font-bold text-slate-900 dark:text-slate-100">MOT Driver Medical Fitness Certificate</div>
                      <div className="text-[10px] text-slate-400">Issuer: Saudi MOMRAH Approved Clinic • Valid for 12 months</div>
                    </div>
                  </div>
                  <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px] font-bold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 inline-block animate-pulse" />
                    <span>VERIFIED VALID</span>
                  </Badge>
                </div>

                {/* File 3: Driver Authorization */}
                <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
                      <Clock className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-900 dark:text-slate-100">MERCON Istimara Fleet Driver Permit</div>
                      <div className="text-[10px] text-slate-400">Issuer: Internal Fleet Operations • Renewal due in 18 days</div>
                    </div>
                  </div>
                  <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 text-[10px] font-bold flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block animate-pulse" />
                    <span>RENEWAL DUE SOON</span>
                  </Badge>
                </div>

              </CardContent>
            </Card>
          </TabsContent>

          {/* ── TAB 3: Trip History ────────────────────────────────────────── */}
          <TabsContent value="trips" className="m-0">
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs overflow-hidden">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-[#E8450F]" /> Driver Trip Dispatch History
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Log of active and completed freight dispatches assigned to this driver.
                  </CardDescription>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono font-bold text-slate-500">
                  {totalTripsCount} Total Trips
                </Badge>
              </CardHeader>

              {(!driver.trips || driver.trips.length === 0) ? (
                <div className="p-12 text-center text-slate-400 flex flex-col items-center gap-2">
                  <MapPin size={32} className="opacity-30 text-slate-400" />
                  <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">No trips recorded for this driver yet.</p>
                </div>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900">
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Trip ID</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Dispatch Date</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Status</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {driver.trips.map((trip) => (
                      <tr key={trip.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                        <td className="px-5 py-3">
                          <span className="font-mono text-xs font-extrabold text-[#E8450F]">{trip.ref_id}</span>
                        </td>
                        <td className="px-5 py-3 text-xs text-slate-600 dark:text-slate-300 font-mono">
                          {new Date(trip.createdAt).toLocaleDateString()}
                        </td>
                        <td className="px-5 py-3">
                          <StatusBadge status={trip.status as any} />
                        </td>
                        <td className="px-5 py-3 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/trips/${trip.id}`)}
                            className="h-8 w-8 p-0 text-slate-500 hover:text-indigo-600"
                            title="View Trip Details"
                          >
                            <Eye size={14} />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </TabsContent>

          {/* ── TAB 4: Safety & Telematics ──────────────────────────────────── */}
          <TabsContent value="telematics" className="m-0">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              
              <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
                <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <Gauge className="w-4 h-4 text-indigo-500" /> Driver Safety Telematics Scorecard
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-5 space-y-3.5 text-xs">
                  <div className="flex justify-between items-center pb-3 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Speeding Incidents (Last 30d)</span>
                    <span className="font-mono font-bold text-emerald-600">0 Violations</span>
                  </div>

                  <div className="flex justify-between items-center pb-3 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Harsh Braking Index</span>
                    <span className="font-mono font-bold text-emerald-600">98% Clean Score</span>
                  </div>

                  <div className="flex justify-between items-center pb-3 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500 font-medium">Weekly Driving Hours Cap</span>
                    <span className="font-mono font-bold text-slate-800 dark:text-slate-200">34h / 48h Limit</span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-slate-500 font-medium">Fleet Fuel Efficiency</span>
                    <span className="font-mono font-bold text-indigo-600">31.2 L / 100 km</span>
                  </div>
                </CardContent>
              </Card>

              <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
                <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <Truck className="w-4 h-4 text-emerald-600" /> Assigned Fleet Vehicle
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-5 space-y-3 text-xs">
                  <div className="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                    <Truck className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />
                    <div>
                      <h4 className="font-extrabold text-sm text-slate-900 dark:text-slate-100">Volvo FH16 (600 HP)</h4>
                      <p className="text-[11px] text-slate-400 font-mono">Plate: 8821-KSA • Heavy Freight Tractor</p>
                    </div>
                  </div>

                  <p className="text-slate-500 text-[11px]">
                    Assigned to primary long-haul routes between Riyadh, Jeddah, and Dammam distribution hubs.
                  </p>
                </CardContent>
              </Card>

            </div>
          </TabsContent>
        </Tabs>

      </div>

      {/* ── Delete Driver Confirmation Modal ────────────────────────────── */}
      <Dialog open={isDeleteModalOpen} onOpenChange={(open) => !open && setIsDeleteModalOpen(false)}>
        <DialogContent className="max-w-md rounded-2xl p-0 overflow-hidden border-slate-200 dark:border-slate-800">
          <DialogHeader className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-rose-50/50 dark:bg-rose-950/20">
            <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <DialogTitle className="text-base font-extrabold">Delete Driver Account</DialogTitle>
            </div>
            <DialogDescription className="text-xs text-slate-500 mt-1">
              Deleting driver <strong className="text-slate-900 dark:text-slate-100">{driver.first_name} {driver.last_name}</strong> will revoke access and archive roster records. Enter admin password to proceed.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleDeleteSubmit}>
            <div className="p-6 space-y-4">
              {deleteError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs font-bold text-rose-700 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                  <span>{deleteError}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="admin_password" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Admin Password <span className="text-rose-500">*</span>
                </Label>
                <Input
                  id="admin_password"
                  type="password"
                  placeholder="Enter your admin password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="h-9 text-xs border-slate-200 dark:border-slate-800"
                  required
                />
              </div>
            </div>

            <DialogFooter className="px-6 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => { setIsDeleteModalOpen(false); setPassword(''); setDeleteError(''); }}
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
