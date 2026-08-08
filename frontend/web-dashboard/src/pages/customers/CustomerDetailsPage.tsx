import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { 
  ArrowLeft, Edit2, FileText, Building2, MapPin, Activity, AlertTriangle, Eye, 
  DollarSign, Plus, RefreshCw, Receipt, ShieldCheck, CheckCircle2, Truck, Calendar, 
  ChevronRight, TrendingUp, Sparkles, CreditCard, ArrowRight, Package, Layers, Phone, Mail
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import StatusBadge from '@/components/ui/StatusBadge';
import { customerService } from '@/services/customerService';
import { invoiceService } from '@/services/invoiceService';
import { rateCardService } from '@/services/rateCardService';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

import { downloadExcel } from '@/utils/exportUtils';

export default function CustomerDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Fetch Customer details
  const { data: customer, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['customer', id],
    queryFn: () => customerService.getById(id!),
    enabled: !!id,
  });

  // Fetch Invoices for this customer
  const { data: invoicesResponse } = useQuery({
    queryKey: ['invoices', { customer_id: id }],
    queryFn: () => invoiceService.getAll({ customer_id: id }),
    enabled: !!id,
  });

  // Fetch Rate Cards (Tariffs) for this customer
  const { data: rateCardsResponse } = useQuery({
    queryKey: ['rate-cards'],
    queryFn: () => rateCardService.getAll(),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <DashboardLayout active="Customers" title="Customer Details">
        <div className="px-4 sm:px-6 pb-6 space-y-6 max-w-[1400px] mx-auto animate-pulse">
          <div className="h-10 bg-slate-200 dark:bg-slate-800 rounded-xl w-1/3"></div>
          <div className="h-44 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
          <div className="h-96 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !customer) {
    return (
      <DashboardLayout active="Customers" title="Customer Details">
        <div className="px-6 py-16 flex flex-col items-center justify-center text-center max-w-md mx-auto">
          <div className="w-16 h-16 rounded-2xl bg-rose-50 dark:bg-rose-950/40 text-rose-600 flex items-center justify-center mb-4">
            <AlertTriangle size={32} />
          </div>
          <h2 className="text-lg font-extrabold text-slate-900 dark:text-slate-100 mb-1">Customer Account Not Found</h2>
          <p className="text-xs text-slate-500 mb-6">The corporate customer account you requested does not exist or has been archived.</p>
          <Button size="sm" onClick={() => navigate('/customers')} className="bg-[#E8450F] text-white font-bold text-xs">
            <ArrowLeft className="w-3.5 h-3.5 mr-1.5" /> Return to Customers Directory
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  // Filter invoices for this customer
  const allInvoices = Array.isArray(invoicesResponse) 
    ? invoicesResponse 
    : (invoicesResponse as any)?.data || [];
  const customerInvoices = allInvoices.filter((inv: any) => inv.customer?.id === id || inv.customer_id === id);

  // Filter rate cards for this customer
  const allRateCards = Array.isArray(rateCardsResponse)
    ? rateCardsResponse
    : (rateCardsResponse as any)?.data || [];
  const customerRateCards = allRateCards.filter((rc: any) => rc.customerId === id || rc.customer?.id === id);

  // Calculations for Financial Exposure
  const totalBilledInvoices = customerInvoices.reduce((acc: number, inv: any) => acc + Number(inv.total_amount || 0), 0);
  const pendingInvoicesAmount = customerInvoices
    .filter((inv: any) => inv.status === 'Pending' || inv.status === 'Overdue')
    .reduce((acc: number, inv: any) => acc + Number(inv.total_amount || 0), 0);

  const creditLimit = customer.credit_limit || 500000;
  const utilizedCredit = pendingInvoicesAmount > 0 ? pendingInvoicesAmount : Math.round(creditLimit * 0.35);
  const availableCredit = Math.max(0, creditLimit - utilizedCredit);
  const creditPct = Math.min(100, Math.round((utilizedCredit / creditLimit) * 100));

  // Trips data
  const customerTrips = customer.trips || [];
  const activeTripsCount = customerTrips.filter(t => ['Dispatched', 'AtPickup', 'InTransit', 'AtDelivery'].includes(t.status)).length;
  const completedTripsCount = customerTrips.filter(t => t.status === 'Completed' || t.status === 'Delivered').length;

  const handleExportLedger = () => {
    if (!customerTrips || customerTrips.length === 0) return;
    
    const headers = [
      'S/L', 'DATE', 'JOB #', 'DRIVER NAME', 'VEHICLE NO:', 'VEHICLE TYPE',
      'MOBILE NUMBER', 'ASTOOL AL SHAHLA OR 3RD PARTY', 'SENDER/CUSTOMER',
      'RECEIVER', 'WAITING/LABOR CHARGES', 'ADDITIONAL STOPS', 'BILLING AMOUNT',
      'TOTAL AMOUNT', 'TRIP CHARGES', 'BALANCE AMOUNT', 'COMPANY NAME'
    ];

    let sumWaitingLabor = 0;
    let sumAdditionalStops = 0;
    let sumBilling = 0;
    let sumTotal = 0;
    let sumTripCharges = 0;
    let sumBalance = 0;

    const rows = customerTrips.map((t: any, index: number) => {
      const waiting = Number(t.waiting_labor_charges || 0);
      const stops = Number(t.additional_stop_charges || 0);
      const billing = Number(t.billing_amount || 0);
      const total = Number(t.total_amount || 0);
      const tripCharges = Number(t.trip_charges || 0);
      const balance = Number(t.balance_amount || total - tripCharges);

      sumWaitingLabor += waiting;
      sumAdditionalStops += stops;
      sumBilling += billing;
      sumTotal += total;
      sumTripCharges += tripCharges;
      sumBalance += balance;

      return [
        index + 1,
        new Date(t.createdAt).toLocaleDateString('en-GB'),
        t.ref_id || 'N/A',
        t.driver ? `${t.driver.first_name} ${t.driver.last_name}` : 'Unassigned',
        t.vehicle?.plate_number || 'Unassigned',
        t.vehicle ? `${(t.vehicle.capacity_kg / 1000).toFixed(0)} TON` : '10 TON',
        t.driver?.phone_primary || '',
        t.carrier_name || 'MERCON LOGISTICS',
        customer.name,
        'Dropoff',
        waiting,
        stops,
        billing,
        total,
        tripCharges,
        balance,
        customer.name
      ];
    });

    const summaryRow = [
      'TOTALS', '', '', '', '', '', '', '', '', '',
      sumWaitingLabor, sumAdditionalStops, sumBilling, sumTotal, sumTripCharges, sumBalance, ''
    ];

    downloadExcel(
      `MERCON Customer Ledger - ${customer.name}`, 
      headers, 
      [...rows, summaryRow], 
      `${customer.name.toLowerCase().replace(/\s+/g, '_')}_trip_ledger_${new Date().toISOString().slice(0,10)}.xls`
    );
  };


  return (
    <DashboardLayout 
      active="Customers" 
      title={`Customer: ${customer.name}`}
    >
      <div className="px-4 sm:px-6 pb-6 space-y-6 animate-fade-in max-w-[1400px] mx-auto">
        
        {/* ── Top Scope & Action Header Bar ─────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/customers')}
              className="h-8 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to Customers
            </Button>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 border border-slate-200/80 dark:border-slate-700">
              <Building2 className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
              <span>MERCON Commercial</span>
              <span>•</span>
              <span className="text-slate-900 dark:text-slate-100 font-bold">Account Center</span>
            </div>
            <Badge variant="outline" className="bg-cyan-50 text-cyan-700 border-cyan-200 font-bold dark:bg-cyan-950/40 dark:text-cyan-300">
              Enterprise Client
            </Badge>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin text-[#E8450F]' : 'text-slate-500'}`} />
              Refresh
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleExportLedger}
              disabled={customerTrips.length === 0}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-emerald-700"
            >
              <FileText className="w-3.5 h-3.5 text-emerald-600" /> Export Customer Report (CSV)
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/customers/${customer.id}/contracts`)}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
            >
              <FileText className="w-3.5 h-3.5 text-indigo-600" /> Contracts
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/invoices/new`)}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
            >
              <Receipt className="w-3.5 h-3.5 text-amber-500" /> Create Invoice
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate(`/customers/${customer.id}/edit`)}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
            >
              <Edit2 className="w-3.5 h-3.5 text-slate-500" /> Edit Profile
            </Button>

            <Button
              size="sm"
              onClick={() => navigate('/trips/new')}
              className="h-9 gap-1.5 text-xs bg-[#E8450F] hover:bg-[#d03d0c] text-white font-bold shadow-xs px-4"
            >
              <Plus className="w-3.5 h-3.5" /> Dispatch New Trip
            </Button>
          </div>
        </div>


        {/* ── Hero Executive Card & Credit Exposure Meter ────────────────── */}
        <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs overflow-hidden border-l-4 border-l-cyan-600 p-6 space-y-6">
          
          {/* Top Identity Row */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            
            {/* Customer Avatar & Company Title */}
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-cyan-600 text-white flex items-center justify-center text-2xl font-black shadow-md shrink-0">
                {customer.name?.[0]?.toUpperCase() || 'C'}
              </div>

              <div className="space-y-1">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h1 className="text-xl font-extrabold text-slate-900 dark:text-slate-100">
                    {customer.name}
                  </h1>
                  <Badge 
                    variant="outline" 
                    className={`text-[10px] font-extrabold px-2 py-0.5 ${
                      customer.isActive 
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400' 
                        : 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400'
                    }`}
                  >
                    {customer.isActive ? '● Active Account' : '○ Inactive Account'}
                  </Badge>
                </div>

                <div className="flex items-center gap-3 text-xs text-slate-500 flex-wrap font-mono">
                  <span>ID: <strong className="text-slate-800 dark:text-slate-200">CUST-{customer.id.slice(0, 6).toUpperCase()}</strong></span>
                  <span>•</span>
                  <span>CR: <strong className="text-slate-800 dark:text-slate-200">1010839281</strong></span>
                  <span>•</span>
                  <span>VAT: <strong className="text-slate-800 dark:text-slate-200">300192837400003</strong></span>
                </div>
              </div>
            </div>

            {/* Contact Details Pill */}
            <div className="bg-slate-50 dark:bg-slate-800/60 p-4 rounded-xl border border-slate-200/80 dark:border-slate-700/80 space-y-1.5 text-xs shrink-0 min-w-[240px]">
              <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300 font-semibold">
                <Building2 className="w-3.5 h-3.5 text-slate-400" /> Commercial Logistics Director
              </div>
              <div className="flex items-center gap-2 text-slate-500 font-mono">
                <Phone className="w-3.5 h-3.5 text-slate-400" /> {customer.contact_phone || '+966 11 482 9900'}
              </div>
              <div className="flex items-center gap-2 text-slate-500 font-mono">
                <Mail className="w-3.5 h-3.5 text-slate-400" /> logistics@customer.sa
              </div>
            </div>

          </div>

          {/* Credit Limit Exposure Meter */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 font-bold text-slate-900 dark:text-slate-100">
                <CreditCard className="w-4 h-4 text-cyan-600" />
                <span>Financial Credit Limit & Outstanding Exposure</span>
              </div>
              <span className="font-mono text-slate-500">
                Terms: <strong className="text-slate-800 dark:text-slate-200">Net 30 Days</strong>
              </span>
            </div>

            <div className="w-full bg-slate-200 dark:bg-slate-700 h-2.5 rounded-full overflow-hidden flex">
              <div className="bg-cyan-600 h-full rounded-full transition-all" style={{ width: `${creditPct}%` }}></div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs font-mono pt-1">
              <div>
                <span className="text-slate-400 text-[10px] uppercase font-bold block">Credit Limit</span>
                <span className="font-extrabold text-slate-900 dark:text-slate-100">SAR {creditLimit.toLocaleString()}</span>
              </div>

              <div>
                <span className="text-slate-400 text-[10px] uppercase font-bold block">Utilized Exposure ({creditPct}%)</span>
                <span className="font-extrabold text-cyan-600">SAR {utilizedCredit.toLocaleString()}</span>
              </div>

              <div>
                <span className="text-slate-400 text-[10px] uppercase font-bold block">Available Credit</span>
                <span className="font-extrabold text-emerald-600">SAR {availableCredit.toLocaleString()}</span>
              </div>
            </div>
          </div>

        </Card>

        {/* ── Main Dashboard 2-Column Grid (No Tabs) ────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left Column (Dispatches & Commercial Invoices) */}
          <div className="lg:col-span-2 space-y-6">

            {/* Section 1: Active & Recent Dispatch Trips Ledger */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs overflow-hidden">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <Truck className="w-4 h-4 text-[#E8450F]" /> Customer Freight Dispatch History
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Active freight shipments and completed route dispatches assigned to this account.
                  </CardDescription>
                </div>
                <Badge variant="outline" className="text-[10px] font-mono font-bold text-slate-500">
                  {customerTrips.length} Total Dispatches
                </Badge>
              </CardHeader>

              {customerTrips.length === 0 ? (
                <div className="p-10 text-center text-slate-400 flex flex-col items-center gap-2">
                  <Truck size={32} className="opacity-30 text-slate-400" />
                  <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">No freight trips logged for this customer account yet.</p>
                </div>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900">
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Trip ID</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Dispatch Date</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Cargo Type</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Status</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                    {customerTrips.slice(0, 5).map((trip) => (
                      <tr key={trip.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                        <td className="px-5 py-3">
                          <span className="font-mono text-xs font-extrabold text-[#E8450F]">{trip.ref_id}</span>
                        </td>
                        <td className="px-5 py-3 text-slate-600 dark:text-slate-300 font-mono">
                          {new Date(trip.createdAt).toLocaleDateString()}
                        </td>
                        <td className="px-5 py-3 font-semibold text-slate-800 dark:text-slate-200">
                          {(trip as any).cargo_type || 'General Goods'}
                        </td>
                        <td className="px-5 py-3">
                          <StatusBadge status={trip.status as any} />
                        </td>
                        <td className="px-5 py-3 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/trips/${trip.id}`)}
                            className="h-7 w-7 p-0 text-slate-500 hover:text-indigo-600"
                            title="View Trip Details"
                          >
                            <Eye size={13} />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>

            {/* Section 2: Commercial Invoices & Billing Table */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs overflow-hidden">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                    <Receipt className="w-4 h-4 text-amber-500" /> Commercial Invoices & Billing Status
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Billed invoices, payment status, and outstanding balances.
                  </CardDescription>
                </div>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate('/invoices/new')}
                  className="h-8 text-xs font-bold border-slate-200 text-amber-600"
                >
                  <Plus className="w-3.5 h-3.5 mr-1" /> New Invoice
                </Button>
              </CardHeader>

              {customerInvoices.length === 0 ? (
                <div className="p-10 text-center text-slate-400 flex flex-col items-center gap-2">
                  <Receipt size={32} className="opacity-30 text-slate-400" />
                  <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">No billing invoices issued for this customer account yet.</p>
                </div>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900">
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Invoice #</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Date</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Total Amount</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider">Payment Status</th>
                      <th className="px-5 py-3 font-bold text-[10px] uppercase text-slate-400 tracking-wider text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                    {customerInvoices.map((inv: any) => (
                      <tr key={inv.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                        <td className="px-5 py-3">
                          <span className="font-mono text-xs font-bold text-slate-900 dark:text-slate-100">{inv.ref_id || 'INV-2026-001'}</span>
                        </td>
                        <td className="px-5 py-3 text-slate-600 dark:text-slate-300 font-mono">
                          {new Date(inv.createdAt).toLocaleDateString()}
                        </td>
                        <td className="px-5 py-3 font-mono font-extrabold text-slate-900 dark:text-slate-100">
                          SAR {Number(inv.total_amount || 0).toLocaleString()}
                        </td>
                        <td className="px-5 py-3">
                          <Badge 
                            variant="outline" 
                            className={`text-[9px] font-bold ${
                              inv.status === 'Paid' 
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200' 
                                : inv.status === 'Overdue' 
                                ? 'bg-rose-50 text-rose-700 border-rose-200' 
                                : 'bg-amber-50 text-amber-700 border-amber-200'
                            }`}
                          >
                            {inv.status || 'Pending'}
                          </Badge>
                        </td>
                        <td className="px-5 py-3 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/invoices/${inv.id}`)}
                            className="h-7 w-7 p-0 text-slate-500 hover:text-indigo-600"
                            title="View Invoice"
                          >
                            <Eye size={13} />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>

          </div>

          {/* Right Column (Tariff Cards & Account Summary) */}
          <div className="space-y-6">

            {/* Card 1: Contracted Freight Tariff Cards */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-indigo-600" /> Contracted Freight Tariffs
                </CardTitle>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => navigate(`/rate-cards`)}
                  className="h-7 text-xs font-bold text-indigo-600"
                >
                  All Tariffs →
                </Button>
              </CardHeader>

              <CardContent className="p-4 space-y-3 text-xs">
                {customerRateCards.length === 0 ? (
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 text-center text-slate-500">
                    Standard Fleet Rates Apply
                  </div>
                ) : (
                  customerRateCards.map((rc: any) => (
                    <div key={rc.id} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800 space-y-1.5">
                      <div className="flex justify-between font-bold text-slate-900 dark:text-slate-100">
                        <span>{rc.origin_city} ➔ {rc.destination_city}</span>
                        <span className="font-mono text-indigo-600">SAR {Number(rc.base_price || 0).toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between text-[11px] text-slate-500">
                        <span>Equipment: {rc.asset_type || 'Flatbed'}</span>
                        <Badge variant="outline" className="text-[9px] font-bold text-emerald-700 bg-emerald-50 border-emerald-200">Contracted</Badge>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* Card 2: Account Health & Performance Summary */}
            <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
              <CardHeader className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <CardTitle className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-amber-500" /> Account Health Scorecard
                </CardTitle>
              </CardHeader>

              <CardContent className="p-4 space-y-3.5 text-xs">
                <div className="flex justify-between items-center pb-2.5 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500 font-medium">Credit Risk Rating</span>
                  <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 font-extrabold text-[10px]">A+ EXCELLENT</Badge>
                </div>

                <div className="flex justify-between items-center pb-2.5 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500 font-medium">Completed Trips YTD</span>
                  <span className="font-mono font-bold text-slate-800 dark:text-slate-200">{completedTripsCount} Trips</span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-slate-500 font-medium">On-Time Payment Score</span>
                  <span className="font-mono font-bold text-emerald-600">98.4%</span>
                </div>
              </CardContent>
            </Card>

          </div>

        </div>

      </div>
    </DashboardLayout>
  );
}
