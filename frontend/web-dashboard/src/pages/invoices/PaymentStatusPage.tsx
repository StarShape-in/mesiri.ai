import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, FileText, CheckCircle2, Clock, AlertTriangle, Search, RotateCw, DollarSign, Plus, CreditCard } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { downloadCSV } from '@/utils/exportUtils';
import DashboardLayout from '@/components/layout/DashboardLayout';
import KpiCard from '@/components/ui/KpiCard';
import { ClockIcon, RiskAlert, CheckBadge, InvoiceDoc } from '@/components/ui/kpi-icons';
import Btn from '@/components/ui/Btn';
import DataTable from '@/components/ui/DataTable';
import { invoiceService, type Invoice, type InvoiceStatus } from '@/services/invoiceService';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const TABS: Array<'All' | InvoiceStatus> = ['All', 'Draft', 'Pending', 'Paid', 'Overdue', 'Cancelled'];

function sar(value: number): string {
  if (Math.abs(value) >= 1000) {
    return `SAR ${(value / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 })}K`;
  }
  return `SAR ${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toISOString().slice(0, 10);
}

const STATUS_STYLES: Record<InvoiceStatus, string> = {
  Draft:     'bg-[#F5F5F7] text-[#6E6E80]',
  Pending:   'bg-[#EFF6FF] text-[#2563EB]',
  Paid:      'bg-[#F0FDF4] text-[#16A34A]',
  Overdue:   'bg-[#FEF2F2] text-[#DC2626]',
  Cancelled: 'bg-[#F5F5F7] text-[#9898A4]',
};

export default function PaymentStatusPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState<'All' | InvoiceStatus>('All');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['invoices', 'payment-status'],
    queryFn: async () => (await invoiceService.getAll({ per_page: 100 })).data,
  });

  const invoices = useMemo(() => data ?? [], [data]);

  const kpis = useMemo(() => {
    const now = new Date();
    const sum = (list: Invoice[]) => list.reduce((s, i) => s + (i.total_amount ?? 0), 0);
    const outstanding = sum(invoices.filter((i) => i.status === 'Pending' || i.status === 'Overdue'));
    const overdue = sum(invoices.filter((i) => i.status === 'Overdue'));
    const paidThisMonth = sum(
      invoices.filter((i) => {
        if (i.status !== 'Paid') return false;
        const d = new Date(i.createdAt);
        return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
      }),
    );
    const draftCount = invoices.filter((i) => i.status === 'Draft').length;
    return { outstanding, overdue, paidThisMonth, draftCount };
  }, [invoices]);

  const filteredInvoices = useMemo(() => {
    const q = search.toLowerCase();
    return invoices.filter((i) => {
      const client = i.customer?.name ?? '';
      const ref = i.ref_id ?? i.id;
      const matchesSearch = client.toLowerCase().includes(q) || ref.toLowerCase().includes(q);
      const matchesTab = activeTab === 'All' || i.status === activeTab;
      return matchesSearch && matchesTab;
    });
  }, [invoices, search, activeTab]);

  const columns = [
    {
      header: 'Invoice ID',
      accessor: (row: Invoice) => (
        <span
          className="font-mono text-xs font-bold text-[#E8450F] cursor-pointer hover:underline"
          onClick={() => navigate(`/invoices/${row.id}`)}
        >
          {row.ref_id ?? row.id.slice(0, 8)}
        </span>
      ),
    },
    {
      header: 'Client',
      accessor: (row: Invoice) => (
        <span className="font-bold text-[#111]">{row.customer?.name ?? '—'}</span>
      ),
    },
    {
      header: 'Amount',
      accessor: (row: Invoice) => (
        <span className="font-bold text-[#444]">SAR {(row.total_amount ?? 0).toLocaleString()}</span>
      ),
    },
    {
      header: 'Issue Date',
      accessor: (row: Invoice) => (
        <span className="text-xs text-[#6E6E80] font-medium">{fmtDate(row.createdAt)}</span>
      ),
    },
    {
      header: 'Due Date',
      accessor: (row: Invoice) => (
        <span className="text-xs text-[#6E6E80] font-medium">{fmtDate(row.due_date)}</span>
      ),
    },
    {
      header: 'Status',
      accessor: (row: Invoice) => (
        <span className={`${STATUS_STYLES[row.status]} px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider`}>
          {row.status}
        </span>
      ),
    },
  ];

  return (
    <DashboardLayout
      active="Invoices"
      title="Payment Status"
    >
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col animate-fade-in gap-5">
        
        {/* Page Content Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 pb-1">
          <div className="flex items-center gap-3">
            <DollarSign className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />

            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  Payment Status
                </h1>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
              onClick={() => downloadCSV(data || [], 'payment_status_export.csv')}
            >
              <Download className="h-3.5 w-3.5 text-slate-600" />
              Export CSV
            </Button>

            <Button
              size="sm"
              className="h-9 gap-1.5 text-xs font-bold bg-[#E8450F] hover:bg-[#d03d0c] text-white shadow-xs rounded-md px-4"
              onClick={() => navigate('/invoices/new')}
            >
              <Plus className="h-4 w-4" />
              New Invoice
            </Button>

            <Button
              variant="outline"
              size="sm"
              className="h-9 w-9 p-0 text-slate-600 border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
              onClick={async () => {
                setIsRefreshing(true);
                await queryClient.invalidateQueries({ queryKey: ['invoices'] });
                setTimeout(() => setIsRefreshing(false), 500);
              }}
              title="Refresh Data"
            >
              <RotateCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <KpiCard
            title="Total Outstanding"
            value={isLoading ? '—' : sar(kpis.outstanding)}
            icon={ClockIcon}
            variant="blue"
            trend="neutral"
            trendValue="Pending"
            description="Pending & Overdue"
            chartData={[120, 150, 140, 180, 210, 190, 240]}
          />
          <KpiCard
            title="Total Overdue"
            value={isLoading ? '—' : sar(kpis.overdue)}
            icon={RiskAlert}
            variant="rose"
            trend="down"
            trendValue="Action Needed"
            description="Past due date"
            chartData={[30, 45, 40, 60, 55, 70, 65]}
          />
          <KpiCard
            title="Paid This Month"
            value={isLoading ? '—' : sar(kpis.paidThisMonth)}
            icon={CheckBadge}
            variant="emerald"
            trend="up"
            trendValue="+14.2%"
            description="Collected payments"
            chartData={[200, 310, 280, 420, 510, 630, 750]}
          />
          <KpiCard
            title="Draft Invoices"
            value={isLoading ? '—' : kpis.draftCount.toString()}
            icon={InvoiceDoc}
            variant="amber"
            trend="neutral"
            trendValue="Drafts"
            description="Awaiting submission"
            chartData={[5, 8, 6, 9, 7, 10, 8]}
          />
        </div>

        {/* Data Table Area */}
        {isError ? (
          <div className="p-12 text-center text-rose-600 text-sm font-semibold bg-white rounded-xl border border-slate-200">Failed to load invoices.</div>
        ) : (
          <DataTable
            title={
              <span className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-green-500" />
                <span>Payment Transactions Ledger</span>
              </span>
            }
            columns={columns}
            data={filteredInvoices}
            bulkActions={[
              {
                label: 'Mark Paid',
                icon: <CheckCircle2 className="w-3.5 h-3.5" />,
                onClick: async (selectedRows: Invoice[]) => {
                  if (!confirm(`Mark ${selectedRows.length} invoices as Paid?`)) return;
                  try {
                    await invoiceService.bulkUpdateStatus(selectedRows.map(r => r.id), 'Paid');
                    queryClient.invalidateQueries({ queryKey: ['invoices'] });
                  } catch (e) { alert('Failed to update status'); }
                }
              },
              {
                label: 'Export CSV',
                icon: <Download className="w-3.5 h-3.5" />,
                variant: 'secondary' as const,
                onClick: (selectedRows: Invoice[]) => {
                  downloadCSV(selectedRows, 'payments_export.csv');
                }
              }
            ]}
            enableSelection={true}
            isLoading={isLoading}
            searchPlaceholder="Search invoice or client..."
            searchValue={search}
            onSearchChange={setSearch}
            filterElement={
              <div className="flex items-center gap-1 p-1 bg-slate-100 dark:bg-slate-800 rounded-lg overflow-x-auto">
                {TABS.map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-3 py-1 text-xs font-bold rounded-md transition-all whitespace-nowrap ${
                      activeTab === tab
                        ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xs'
                        : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            }
          />
        )}

      </div>
    </DashboardLayout>
  );
}
