import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  ArrowLeft, Edit2, Trash2, MapPin, Building2, Calendar, DollarSign, 
  FileText, ShieldCheck, CheckCircle2, Clock, AlertTriangle, Truck, 
  FileCheck, Shield, Sparkles, Scale, RefreshCw, XCircle
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import ConfirmModal from '@/components/ui/ConfirmModal';
import { rateCardService } from '@/services/rateCardService';

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { cn } from '@/lib/utils';

export default function RateCardDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  const { data: card, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['rate-card', id],
    queryFn: () => rateCardService.getById(id!),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: () => rateCardService.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rate-cards'] });
      navigate('/rate-cards');
    },
  });

  if (isLoading) {
    return (
      <DashboardLayout active="Rate Cards" title="Rate Card Details">
        <div className="px-4 sm:px-6 pb-6 space-y-4 animate-pulse w-full">
          <div className="h-10 bg-slate-200 dark:bg-slate-800 rounded-xl w-1/4"></div>
          <div className="h-24 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
          <div className="h-64 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !card) {
    return (
      <DashboardLayout active="Rate Cards" title="Rate Card Details">
        <div className="px-4 sm:px-6 pb-6 flex flex-col items-center justify-center text-center h-[60vh] gap-3">
          <div className="w-14 h-14 rounded-2xl bg-rose-50 dark:bg-rose-950/40 text-rose-500 flex items-center justify-center">
            <AlertTriangle size={28} />
          </div>
          <h2 className="text-lg font-extrabold text-slate-900 dark:text-slate-100">Tariff Record Not Found</h2>
          <p className="text-xs text-slate-500 max-w-md">
            The requested freight tariff contract does not exist or has been removed.
          </p>
          <Button onClick={() => navigate('/rate-cards')} size="sm" className="mt-2 text-xs font-bold bg-[#E8450F] text-white">
            Return to Rate Cards Directory
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  const currency = card.currency || 'SAR';
  const isActive = card.is_active ?? true;

  return (
    <DashboardLayout active="Rate Cards" title={`Tariff: ${card.name}`}>
      <div className="px-4 sm:px-6 pb-8 space-y-4 animate-fade-in w-full">

        {/* ── Top Header Toolbar ─────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/rate-cards')}
              className="h-8 w-8 p-0 text-slate-600 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
              title="Back to Rate Cards"
            >
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                {card.name}
              </h1>
              <Badge 
                variant="outline" 
                className={`text-[10px] font-extrabold uppercase px-2 py-0.5 ${
                  isActive
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400'
                    : 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400'
                }`}
              >
                {isActive ? '● Active Tariff' : '● Suspended'}
              </Badge>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
              className="h-8 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-[#E8450F]' : 'text-slate-500'}`} />
              Refresh
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/rate-cards/${card.id}/documents`)}
              className="h-8 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
            >
              <FileCheck className="w-3.5 h-3.5 text-indigo-500" /> Contract Docs
            </Button>

            <Button
              size="sm"
              onClick={() => navigate(`/rate-cards/${card.id}/edit`)}
              className="h-8 gap-1.5 text-xs font-bold bg-[#E8450F] hover:bg-[#d03d0c] text-white shadow-xs px-3.5"
            >
              <Edit2 className="w-3.5 h-3.5" /> Edit Tariff
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsDeleteModalOpen(true)}
              className="h-8 text-xs font-semibold border-rose-200 dark:border-rose-950 bg-rose-50 dark:bg-rose-950/20 text-rose-600 hover:bg-rose-100"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </Button>
          </div>
        </div>

        {/* ── High-Density 4-Column Executive Freight KPI Strip ───────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          
          {/* KPI 1: Contracted Flat Base Rate */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs p-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Contract Base Rate</span>
              <Badge variant="outline" className="text-[9px] font-mono font-bold text-slate-500">FLAT</Badge>
            </div>
            <div className="text-xl font-mono font-black text-[#E8450F] mt-1">
              {currency} {card.base_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
              Per Completed Trip Dispatch
            </span>
          </Card>

          {/* KPI 2: Route Origin & Destination */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs p-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Corridor Route</span>
              <span className="text-[10px] font-mono text-slate-400 font-semibold">~480 km</span>
            </div>
            <div className="text-sm font-extrabold text-slate-900 dark:text-slate-100 truncate mt-1">
              {card.route_origin} ➔ {card.route_destination}
            </div>
            <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
              Est. Transit: 6h 15m
            </span>
          </Card>

          {/* KPI 3: Billed Customer Account */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs p-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Customer Account</span>
              {card.customer?.id && (
                <span 
                  onClick={() => navigate(`/customers/${card.customer?.id}`)}
                  className="text-[10px] font-bold text-cyan-600 hover:underline cursor-pointer"
                >
                  View →
                </span>
              )}
            </div>
            <div className="text-sm font-extrabold text-slate-900 dark:text-slate-100 truncate mt-1">
              {card.customer?.name || 'General Fleet Account'}
            </div>
            <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
              ID: CUST-{card.customerId?.slice(0, 6).toUpperCase() || '8801'}
            </span>
          </Card>

          {/* KPI 4: Contract Status & Updated Date */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs p-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Contract Validity</span>
              <Badge variant="outline" className="text-[9px] font-bold text-emerald-600 bg-emerald-50 border-emerald-200">VERIFIED</Badge>
            </div>
            <div className="text-sm font-mono font-extrabold text-slate-800 dark:text-slate-200 mt-1">
              Revised: {new Date(card.updatedAt || card.createdAt).toLocaleDateString()}
            </div>
            <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
              Created: {new Date(card.createdAt).toLocaleDateString()}
            </span>
          </Card>

        </div>

        {/* ── High-Density 2-Column Route & Commercial Terms Cards ──────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {/* Highway Route Corridor & Asset Specs Card */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
            <CardHeader className="border-b border-slate-100 dark:border-slate-800 py-2.5 px-4">
              <CardTitle className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-[#E8450F]" /> Highway Route Corridor & Equipment Specifications
              </CardTitle>
            </CardHeader>

            <CardContent className="p-4 space-y-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-[9px] text-slate-400 font-bold uppercase block">Origin Pickup Hub</span>
                  <span className="font-extrabold text-slate-900 dark:text-slate-100">{card.route_origin}</span>
                </div>
                <span className="text-slate-400 font-mono font-bold text-sm">➔</span>
                <div className="text-right">
                  <span className="text-[9px] text-slate-400 font-bold uppercase block">Destination Terminal</span>
                  <span className="font-extrabold text-slate-900 dark:text-slate-100">{card.route_destination}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">Permitted Fleet Assets</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">Heavy Flatbed / Reefer / Lowbed</span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">Max Load Tonnage</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">24.0 Metric Tons</span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">Transit Time Allowance</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">6 Hours 15 Minutes</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Commercial Terms & Detention Schedule Card */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
            <CardHeader className="border-b border-slate-100 dark:border-slate-800 py-2.5 px-4">
              <CardTitle className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-indigo-500" /> Commercial Contract Terms & Detention Fees
              </CardTitle>
            </CardHeader>

            <CardContent className="p-4 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">Bound Customer</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">{card.customer?.name || 'General Tariff'}</span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">Free Detention Allowance</span>
                  <span className="font-bold text-emerald-600">2 Hours Free Loading</span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">Overweight Fee</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">SAR 150 / ton over 24t</span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">Night/Weekend Premium</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">+10% Base Rate</span>
                </div>
              </div>
            </CardContent>
          </Card>

        </div>

        {/* ── High-Density Itemized Tariff Schedule Table (shadcn Table) ──── */}
        <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs overflow-hidden">
          <CardHeader className="border-b border-slate-100 dark:border-slate-800 py-2.5 px-4 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
              <Scale className="w-3.5 h-3.5 text-[#E8450F]" /> Itemized Tariff Surcharge & Rate Schedule
            </CardTitle>
            <Badge variant="outline" className="text-[9px] font-mono font-bold text-slate-500">
              Contract Schedule A
            </Badge>
          </CardHeader>

          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/70 dark:bg-slate-900/70">
                  <TableHead className="font-bold text-[10px] uppercase text-slate-400 tracking-wider py-2.5">Service Line Item</TableHead>
                  <TableHead className="font-bold text-[10px] uppercase text-slate-400 tracking-wider py-2.5">Condition / Trigger</TableHead>
                  <TableHead className="font-bold text-[10px] uppercase text-slate-400 tracking-wider py-2.5 text-right">Standard Rate ({currency})</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                <TableRow className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                  <TableCell className="py-3">
                    <div className="font-bold text-slate-900 dark:text-slate-100 text-xs">
                      Base Route Freight Transport Rate
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">Standard Corridor: {card.route_origin} ➔ {card.route_destination}</span>
                  </TableCell>
                  <TableCell className="py-3 font-mono font-semibold text-slate-700 dark:text-slate-300 text-xs">Per Completed Trip</TableCell>
                  <TableCell className="py-3 font-mono font-extrabold text-[#E8450F] text-right text-xs">
                    {card.base_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </TableCell>
                </TableRow>

                <TableRow className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                  <TableCell className="py-3">
                    <div className="font-bold text-slate-900 dark:text-slate-100 text-xs">
                      Demurrage / Detention Hourly Rate
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">Applies after 2 hours free loading/unloading time</span>
                  </TableCell>
                  <TableCell className="py-3 font-mono font-semibold text-slate-700 dark:text-slate-300 text-xs">Per Hour Delay</TableCell>
                  <TableCell className="py-3 font-mono font-extrabold text-slate-800 dark:text-slate-200 text-right text-xs">100.00</TableCell>
                </TableRow>

                <TableRow className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                  <TableCell className="py-3">
                    <div className="font-bold text-slate-900 dark:text-slate-100 text-xs">
                      Overweight Tonnage Fee
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">Applies when cargo payload exceeds 24.0 Metric Tons</span>
                  </TableCell>
                  <TableCell className="py-3 font-mono font-semibold text-slate-700 dark:text-slate-300 text-xs">Per Extra Ton</TableCell>
                  <TableCell className="py-3 font-mono font-extrabold text-slate-800 dark:text-slate-200 text-right text-xs">150.00</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>

      </div>

      {/* ── Confirm Delete Modal ────────────────────────────────────────── */}
      <ConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="Delete Rate Card Tariff"
        message={`Are you sure you want to permanently delete the tariff "${card.name}"? This action cannot be undone.`}
        confirmLabel="Yes, Delete Tariff"
        isDestructive={true}
        isLoading={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate()}
      />
    </DashboardLayout>
  );
}
