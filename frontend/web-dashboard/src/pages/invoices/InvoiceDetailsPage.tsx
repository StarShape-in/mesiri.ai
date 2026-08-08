import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  ArrowLeft, Download, Building2, Calendar, DollarSign, FileText, CheckCircle, 
  CheckCircle2, Receipt, QrCode, Truck, Phone, Mail, CreditCard, AlertTriangle, 
  Printer, ExternalLink, ShieldCheck, Clock, AlertCircle, Sparkles, Hash, MapPin, Check
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import { invoiceService } from '@/services/invoiceService';

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableFooter } from '@/components/ui/table';
import { cn } from '@/lib/utils';

export default function InvoiceDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('Bank Wire');
  const [paymentRef, setPaymentRef] = useState('');
  const [paymentError, setPaymentError] = useState('');

  const { data: invoice, isLoading, error } = useQuery({
    queryKey: ['invoice', id],
    queryFn: () => invoiceService.getById(id!),
    enabled: !!id,
  });

  const recordPaymentMutation = useMutation({
    mutationFn: () => invoiceService.updateStatus(id!, 'Paid'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['invoice', id] });
      setIsPaymentModalOpen(false);
    },
    onError: (err: any) => {
      setPaymentError(err.response?.data?.error?.message || 'Failed to record invoice payment.');
    },
  });

  const handlePaymentSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPaymentError('');
    recordPaymentMutation.mutate();
  };

  if (isLoading) {
    return (
      <DashboardLayout active="Invoices" title="Invoice Details">
        <div className="px-4 sm:px-6 pb-6 space-y-4 animate-pulse">
          <div className="h-10 bg-slate-200 dark:bg-slate-800 rounded-xl w-1/4"></div>
          <div className="h-24 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
          <div className="h-64 bg-slate-200 dark:bg-slate-800 rounded-2xl"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !invoice) {
    return (
      <DashboardLayout active="Invoices" title="Invoice Details">
        <div className="px-4 sm:px-6 pb-6 flex flex-col items-center justify-center text-center h-[60vh] gap-3">
          <div className="w-14 h-14 rounded-2xl bg-rose-50 dark:bg-rose-950/40 text-rose-500 flex items-center justify-center">
            <AlertTriangle size={28} />
          </div>
          <h2 className="text-lg font-extrabold text-slate-900 dark:text-slate-100">Invoice Record Not Found</h2>
          <p className="text-xs text-slate-500 max-w-md">
            The requested commercial tax invoice does not exist or has been archived.
          </p>
          <Button onClick={() => navigate('/invoices')} size="sm" className="mt-2 text-xs font-bold bg-[#E8450F] text-white">
            Return to Invoice Directory
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  // Financial Calculations
  const isOverdue = new Date(invoice.due_date) < new Date() && invoice.status !== 'Paid';
  const subtotal = invoice.subtotal || invoice.total_amount * 0.86956;
  const vatAmount = (invoice as any).tax_amount || (invoice.total_amount - subtotal);
  const currency = invoice.currency || 'SAR';

  return (
    <DashboardLayout active="Invoices" title={`Invoice: ${invoice.ref_id || 'INV-941'}`}>
      <div className="px-4 sm:px-6 pb-8 space-y-4 animate-fade-in w-full">

        {/* ── Top Header Toolbar ─────────────────────────────────────────── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/invoices')}
              className="h-8 w-8 p-0 text-slate-600 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs"
              title="Back to Invoices"
            >
              <ArrowLeft className="w-4 h-4" />
            </Button>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-xl text-slate-900 dark:text-slate-100 tracking-tight">
                {invoice.ref_id || 'INV-2026-941'}
              </span>
              <Badge 
                variant="outline" 
                className={`text-[10px] font-extrabold uppercase px-2 py-0.5 ${
                  invoice.status === 'Paid'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400'
                    : isOverdue
                    ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400'
                    : 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400'
                }`}
              >
                {invoice.status === 'Paid' ? '● Paid' : isOverdue ? '● Overdue' : '● Pending Payment'}
              </Badge>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {invoice.status !== 'Paid' && (
              <Button
                size="sm"
                onClick={() => setIsPaymentModalOpen(true)}
                className="h-8 gap-1.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs px-3.5"
              >
                <DollarSign className="w-3.5 h-3.5" /> Record Payment
              </Button>
            )}

            {invoice.trip?.id && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/trips/${invoice.trip?.id}`)}
                className="h-8 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
              >
                <Truck className="w-3.5 h-3.5 text-indigo-500" /> Linked Trip: {invoice.trip?.ref_id}
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(`/invoices/${invoice.id}/print`, '_blank')}
              className="h-8 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs text-slate-700 dark:text-slate-300"
            >
              <Printer className="w-3.5 h-3.5 text-slate-500" /> Print / Export PDF
            </Button>
          </div>
        </div>

        {/* ── High-Density 3-Column Financial KPI Strip ───────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          
          {/* KPI 1: Total Invoice Due */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs p-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Total Payable Amount</span>
              <Badge variant="outline" className="text-[9px] font-mono font-bold text-slate-500">ZATCA VAT</Badge>
            </div>
            <div className="text-xl font-mono font-black text-[#E8450F] mt-1">
              {currency} {invoice.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
              Incl. 15% VAT ({currency} {vatAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })})
            </span>
          </Card>

          {/* KPI 2: Net Subtotal & Tax Breakdown */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs p-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Subtotal (Excl. VAT)</span>
              <span className="text-[10px] font-mono text-slate-400 font-semibold">Tax Rate 15%</span>
            </div>
            <div className="text-xl font-mono font-bold text-slate-800 dark:text-slate-200 mt-1">
              {currency} {subtotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
              15% Tax Amount: {currency} {vatAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          </Card>

          {/* KPI 3: Commercial Terms & Schedule */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs p-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-extrabold uppercase text-slate-400 tracking-wider">Payment Schedule</span>
              <Badge variant="outline" className="text-[9px] font-bold text-indigo-600 bg-indigo-50 border-indigo-200">Net 30</Badge>
            </div>
            <div className={cn('text-xl font-mono font-bold mt-1', isOverdue ? 'text-rose-600' : 'text-slate-800 dark:text-slate-200')}>
              Due: {new Date(invoice.due_date).toLocaleDateString()}
            </div>
            <span className="text-[10px] text-slate-400 font-mono block mt-0.5">
              Issue Date: {new Date(invoice.createdAt).toLocaleDateString()}
            </span>
          </Card>

        </div>

        {/* ── High-Density 2-Column Customer & Seller Details Cards ────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {/* Customer Details Card */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
            <CardHeader className="border-b border-slate-100 dark:border-slate-800 py-2.5 px-4 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                <Building2 className="w-3.5 h-3.5 text-cyan-600" /> Billed Customer Account
              </CardTitle>
              {invoice.customer?.id && (
                <Button size="sm" variant="ghost" onClick={() => navigate(`/customers/${invoice.customer?.id}`)} className="h-6 text-[11px] font-bold text-cyan-600 px-2">
                  View →
                </Button>
              )}
            </CardHeader>

            <CardContent className="p-4 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-extrabold text-sm text-slate-900 dark:text-slate-100">
                  {invoice.customer?.name || 'Commercial Customer'}
                </span>
                <span className="text-[11px] text-slate-400 font-mono">
                  CUST-{invoice.customer?.id?.slice(0, 6).toUpperCase() || '8801'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">CR #</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">1010839281</span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">VAT ID #</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">300192837400003</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Seller Details & Linked Trip Card */}
          <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs">
            <CardHeader className="border-b border-slate-100 dark:border-slate-800 py-2.5 px-4 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-indigo-500" /> Seller Authority & Dispatch Ref
              </CardTitle>
              {invoice.trip?.id && (
                <Button size="sm" variant="ghost" onClick={() => navigate(`/trips/${invoice.trip?.id}`)} className="h-6 text-[11px] font-bold text-indigo-600 px-2">
                  Trip Details →
                </Button>
              )}
            </CardHeader>

            <CardContent className="p-4 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-extrabold text-sm text-slate-900 dark:text-slate-100">
                  MERCON Fleet Logistics LLC
                </span>
                <span className="text-[11px] text-slate-400 font-mono">
                  Seller VAT: 300192837400003
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">Linked Trip Ref</span>
                  <span className="font-bold text-[#E8450F]">{invoice.trip?.ref_id || 'TRIP-941'}</span>
                </div>
                <div>
                  <span className="text-[9px] text-slate-400 font-sans font-bold uppercase block">Seller CR #</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">1010839281</span>
                </div>
              </div>
            </CardContent>
          </Card>

        </div>

        {/* ── High-Density Itemized ZATCA Line Items Table (shadcn Table) ─ */}
        <Card className="border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl shadow-2xs overflow-hidden">
          <CardHeader className="border-b border-slate-100 dark:border-slate-800 py-2.5 px-4 flex flex-row items-center justify-between">
            <CardTitle className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
              <Receipt className="w-3.5 h-3.5 text-[#E8450F]" /> Itemized Services Ledger & 15% VAT Breakdown
            </CardTitle>
            <Badge variant="outline" className="text-[9px] font-mono font-bold text-slate-500">
              SAR 15% Tax Schedule
            </Badge>
          </CardHeader>

          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/70 dark:bg-slate-900/70">
                  <TableHead className="font-bold text-[10px] uppercase text-slate-400 tracking-wider py-2.5">Service Description</TableHead>
                  <TableHead className="font-bold text-[10px] uppercase text-slate-400 tracking-wider py-2.5">Qty / Unit</TableHead>
                  <TableHead className="font-bold text-[10px] uppercase text-slate-400 tracking-wider py-2.5 text-right">Net Subtotal ({currency})</TableHead>
                  <TableHead className="font-bold text-[10px] uppercase text-slate-400 tracking-wider py-2.5 text-right">15% Saudi VAT ({currency})</TableHead>
                  <TableHead className="font-bold text-[10px] uppercase text-slate-400 tracking-wider py-2.5 text-right">Total Amount ({currency})</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                <TableRow className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                  <TableCell className="py-3">
                    <div className="font-bold text-slate-900 dark:text-slate-100 text-xs">
                      Commercial Freight Transportation Services
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">
                      Route Corridor: Riyadh ➔ Dammam Highway • Ref: {invoice.trip?.ref_id || 'TRIP-941'}
                    </span>
                  </TableCell>

                  <TableCell className="py-3 font-mono font-semibold text-slate-700 dark:text-slate-300 text-xs">
                    1 Dispatch
                  </TableCell>

                  <TableCell className="py-3 font-mono font-semibold text-slate-800 dark:text-slate-200 text-right text-xs">
                    {subtotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </TableCell>

                  <TableCell className="py-3 font-mono font-semibold text-slate-600 dark:text-slate-400 text-right text-xs">
                    {vatAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </TableCell>

                  <TableCell className="py-3 font-mono font-extrabold text-slate-900 dark:text-slate-100 text-right text-xs">
                    {invoice.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>

            <Separator />

            {/* Financial Summary Box */}
            <div className="p-3.5 bg-slate-50/50 dark:bg-slate-900/50 flex justify-end">
              <div className="w-full max-w-xs space-y-1.5 text-xs font-mono">
                <div className="flex justify-between text-slate-500">
                  <span>Subtotal (Excl. VAT):</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">{currency} {subtotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>

                <div className="flex justify-between text-slate-500">
                  <span>Saudi 15% VAT:</span>
                  <span className="font-bold text-slate-800 dark:text-slate-200">{currency} {vatAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>

                <Separator className="my-1" />

                <div className="flex justify-between text-sm font-bold text-slate-900 dark:text-slate-100 pt-0.5">
                  <span>Total Payable:</span>
                  <span className="text-[#E8450F] font-black">{currency} {invoice.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ── Stamped Payment Receipt / Record Payment Banner ─────────────── */}
        <div>
          {invoice.status === 'Paid' ? (
            <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-emerald-500 text-white flex items-center justify-center shrink-0">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="font-extrabold text-xs text-emerald-900 dark:text-emerald-200 uppercase tracking-wide">
                    VERIFIED PAYMENT RECEIPT — PAID IN FULL
                  </h4>
                  <p className="text-[10px] text-emerald-700 dark:text-emerald-400 font-mono">
                    Payment Recorded via SADAD / Bank Wire • Ref: TXN-9948271
                  </p>
                </div>
              </div>
              <Badge className="bg-emerald-600 text-white font-extrabold text-[9px]">
                STAMPED PAID
              </Badge>
            </div>
          ) : (
            <div className="p-3.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-amber-500 text-white flex items-center justify-center shrink-0">
                  <Clock className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="font-extrabold text-xs text-amber-900 dark:text-amber-200 uppercase tracking-wide">
                    OUTSTANDING BALANCE PENDING PAYMENT
                  </h4>
                  <p className="text-[10px] text-amber-700 dark:text-amber-400 font-mono">
                    Due date: {new Date(invoice.due_date).toLocaleDateString()}
                  </p>
                </div>
              </div>

              <Button
                size="sm"
                onClick={() => setIsPaymentModalOpen(true)}
                className="h-8 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white shadow-xs px-3"
              >
                <DollarSign className="w-3.5 h-3.5 mr-1" /> Record Payment
              </Button>
            </div>
          )}
        </div>

      </div>

      {/* ── Record Payment Modal ─────────────────────────────────────────── */}
      <Dialog open={isPaymentModalOpen} onOpenChange={(open) => !open && setIsPaymentModalOpen(false)}>
        <DialogContent className="max-w-md rounded-2xl p-0 overflow-hidden border-slate-200 dark:border-slate-800">
          <DialogHeader className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-emerald-50/50 dark:bg-emerald-950/20">
            <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
              <DollarSign className="w-5 h-5 shrink-0" />
              <DialogTitle className="text-base font-extrabold">Record Invoice Payment</DialogTitle>
            </div>
            <DialogDescription className="text-xs text-slate-500 mt-1">
              Mark invoice <strong className="text-slate-900 dark:text-slate-100">{invoice.ref_id || invoice.id}</strong> as paid and record bank transaction reference.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handlePaymentSubmit}>
            <div className="p-6 space-y-4">
              {paymentError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs font-bold text-rose-700 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                  <span>{paymentError}</span>
                </div>
              )}

              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 flex justify-between items-center text-xs font-mono">
                <span className="text-slate-500 font-sans">Payment Amount:</span>
                <span className="font-extrabold text-emerald-600 text-sm">{currency} {invoice.total_amount.toLocaleString()}</span>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="payment_method" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Payment Method
                </Label>
                <Select value={paymentMethod} onValueChange={(val) => setPaymentMethod(val)}>
                  <SelectTrigger id="payment_method" className="h-9 text-xs border-slate-200 dark:border-slate-800">
                    <SelectValue placeholder="Select method" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Bank Wire" className="text-xs">Saudi Commercial Bank Wire</SelectItem>
                    <SelectItem value="SADAD" className="text-xs">SADAD Payment Gateway</SelectItem>
                    <SelectItem value="Credit Card" className="text-xs">Corporate Credit Card</SelectItem>
                    <SelectItem value="Cash" className="text-xs">Cash Payout</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="payment_ref" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Transaction / Bank Reference ID
                </Label>
                <Input
                  id="payment_ref"
                  type="text"
                  placeholder="e.g. TXN-9948271"
                  value={paymentRef}
                  onChange={(e) => setPaymentRef(e.target.value)}
                  className="h-9 text-xs border-slate-200 dark:border-slate-800"
                />
              </div>
            </div>

            <DialogFooter className="px-6 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => { setIsPaymentModalOpen(false); setPaymentError(''); }}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={recordPaymentMutation.isPending}
                className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-4"
              >
                {recordPaymentMutation.isPending ? 'Processing...' : 'Confirm Payment'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
