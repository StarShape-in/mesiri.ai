import { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  Plus, DollarSign, Download, Trash2, CheckCircle, RotateCw, FileText, 
  Search, Filter, MoreVertical, ExternalLink, Receipt
} from 'lucide-react';
import { InvoiceDoc, ClockIcon, RiskAlert, CheckBadge, RevenueChart } from '@/components/ui/kpi-icons';

import { downloadCSV } from '@/utils/exportUtils';
import DashboardLayout from '@/components/layout/DashboardLayout';
import DataTable from '@/components/ui/DataTable';
import KpiCard from '@/components/ui/KpiCard';
import { InvoiceAgingKpi } from '@/components/ui/CustomKpiWidgets';
import { invoiceService, Invoice, InvoiceStatus } from '@/services/invoiceService';
import { useDebouncedValue } from '@/hooks/useDebouncedValue';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';

export default function InvoiceListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [selectedStatus, setSelectedStatus] = useState<InvoiceStatus | 'All'>('All');
  const [search, setSearch] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showRevenueModal, setShowRevenueModal] = useState(false);
  const debouncedSearch = useDebouncedValue(search, 300);

  // Fetch invoices using React Query
  const { data: invoicesRes, isLoading, isError, error } = useQuery({
    queryKey: ['invoices', selectedStatus, debouncedSearch, currentPage, pageSize],
    queryFn: () => invoiceService.getAll({
      status: selectedStatus === 'All' ? undefined : selectedStatus,
      search: debouncedSearch || undefined,
      page: currentPage,
      per_page: pageSize,
    }),
  });

  const invoices = invoicesRes?.data || [];
  const totalPages = invoicesRes?.meta?.total_pages || 1;
  const totalCount = invoicesRes?.meta?.total || invoices.length;

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['invoices'] });
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const handleExportCSV = () => {
    downloadCSV(invoices, `invoices_${new Date().toISOString().slice(0, 10)}.csv`);
  };

  const handleDeleteInvoice = async (id: string) => {
    if (!confirm('Are you sure you want to delete this invoice?')) return;
    try {
      await invoiceService.bulkDelete([id]);
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    } catch (e) {
      alert('Failed to delete invoice.');
    }
  };

  // KPIs
  const paidCount = invoices.filter(i => i.status === 'Paid').length;
  const pendingCount = invoices.filter(i => i.status === 'Pending').length;
  const overdueCount = invoices.filter(i => i.status === 'Overdue').length;

  const paidRatioPct = totalCount > 0 ? Math.round((paidCount / totalCount) * 100) : 0;
  const totalCollectedAmount = invoices.filter(i => i.status === 'Paid').reduce((acc, i) => acc + (Number(i.total_amount) || 0), 0);

  const getStatusBadge = (status: InvoiceStatus) => {
    switch (status) {
      case 'Paid': 
        return <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 font-bold uppercase text-[10px]">Paid</Badge>;
      case 'Pending': 
        return <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-300 font-bold uppercase text-[10px]">Pending</Badge>;
      case 'Overdue': 
        return <Badge variant="outline" className="bg-rose-50 text-rose-700 border-rose-200 font-bold uppercase text-[10px]">Overdue</Badge>;
      case 'Cancelled': 
        return <Badge variant="outline" className="bg-slate-100 text-slate-500 border-slate-200 font-bold uppercase text-[10px]">Cancelled</Badge>;
      default: 
        return <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 font-bold uppercase text-[10px]">Draft</Badge>;
    }
  };

  const columns = [
    {
      header: 'Invoice ID',
      accessor: (row: Invoice) => (
        <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
          {row.ref_id || row.id.split('-')[0].toUpperCase()}
        </span>
      ),
    },
    {
      header: 'Customer / Client',
      accessor: (row: Invoice) => (
        <div>
          <div className="font-bold text-slate-900 dark:text-slate-100 text-xs">
            {row.customer?.name || 'Standard Account'}
          </div>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">
            Trip: {row.trip?.ref_id || '—'}
          </div>
        </div>
      ),
    },
    {
      header: 'Total Amount',
      accessor: (row: Invoice) => (
        <span className="text-xs text-slate-950 dark:text-slate-55 font-extrabold font-mono tabular-nums">
          {row.currency || 'SAR'} {Number(row.total_amount).toLocaleString()}
        </span>
      ),
    },
    {
      header: 'Due Date',
      accessor: (row: Invoice) => {
        const isOverdue = new Date(row.due_date) < new Date() && row.status !== 'Paid';
        return (
          <div className="flex items-center gap-1.5">
            <span className={`text-xs font-mono font-bold ${isOverdue ? 'text-rose-600' : 'text-slate-500'}`}>
              {new Date(row.due_date).toLocaleDateString()}
            </span>
            {isOverdue && (
              <Badge variant="outline" className="bg-rose-50 text-rose-700 border-rose-200 text-[8px] font-extrabold px-1 py-0 h-4 w-fit shrink-0">
                OVERDUE
              </Badge>
            )}
          </div>
        );
      },
    },
    {
      header: 'Status',
      accessor: (row: Invoice) => getStatusBadge(row.status),
    },
    {
      header: 'Actions',
      accessor: (row: Invoice) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
            >
              <MoreVertical className="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 shadow-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-xl p-1.5">
            <DropdownMenuLabel className="text-[10px] font-bold tracking-wider uppercase text-slate-400 px-2 py-1">
              Invoice Options
            </DropdownMenuLabel>
            
            <DropdownMenuItem 
              onClick={() => window.open(`/invoices/${row.id}/print`, '_blank')}
              className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md"
            >
              <Download className="w-3.5 h-3.5 mr-2 text-indigo-600" /> Print / PDF Invoice
            </DropdownMenuItem>

            {row.status === 'Pending' && (
              <DropdownMenuItem 
                onClick={() => navigate(`/invoices/${row.id}/payment`)}
                className="cursor-pointer text-xs font-semibold py-1.5 px-2 rounded-md text-emerald-600"
              >
                <DollarSign className="w-3.5 h-3.5 mr-2 text-emerald-600" /> Record Settlement
              </DropdownMenuItem>
            )}

            <DropdownMenuSeparator className="my-1 bg-slate-100 dark:bg-slate-800" />

            <DropdownMenuItem 
              onClick={() => handleDeleteInvoice(row.id)}
              className="cursor-pointer text-xs font-semibold py-1.5 px-2 rounded-md text-rose-600 focus:bg-rose-50"
            >
              <Trash2 className="w-3.5 h-3.5 mr-2 text-rose-600" /> Delete Invoice
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  const bulkActions = [
    {
      label: 'Mark Paid',
      icon: <CheckCircle className="w-3.5 h-3.5" />,
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
        downloadCSV(selectedRows, 'invoices_export.csv');
      }
    },
    {
      label: 'Delete',
      icon: <Trash2 className="w-3.5 h-3.5" />,
      variant: 'danger' as const,
      onClick: async (selectedRows: Invoice[]) => {
        if (!confirm(`Are you sure you want to delete ${selectedRows.length} invoices?`)) return;
        try {
          await invoiceService.bulkDelete(selectedRows.map(r => r.id));
          queryClient.invalidateQueries({ queryKey: ['invoices'] });
        } catch (e) { alert('Failed to delete invoices'); }
      }
    }
  ];

  return (
    <DashboardLayout 
      active="Invoices" 
      title="Invoices" 
    >
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col animate-fade-in gap-5 max-w-[1400px] mx-auto w-full">
        
        {/* Page Content Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 pb-1">
          <div className="flex items-center gap-3">
            <FileText className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />

            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  Invoices
                </h1>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
              onClick={handleExportCSV}
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
              Create Invoice
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

        {/* 4-Card Instrument Panel KPI Section */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 shrink-0">
          
          {/* Card 1: Total Invoices — Billing Ratio Donut Gauge */}
          <KpiCard
            title="TOTAL INVOICES"
            value={totalCount}
            variant="blue"
            trend="neutral"
            trendValue={`${paidRatioPct}% Paid`}
            description="Total billing records"
            icon={InvoiceDoc}
            completionGauge={{
              percentage: paidRatioPct || 70,
              label: `${paidRatioPct}% Settled`,
              subtext: `${paidCount} Paid • ${pendingCount} Pending`
            }}
            onClick={() => { setSelectedStatus('All'); setCurrentPage(1); }}
          />

          {/* Card 2: Total Revenue Collected — Financial Area Sparkline */}
          <KpiCard
            title="COLLECTED REVENUE"
            value={`SAR ${totalCollectedAmount.toLocaleString()}`}
            variant="emerald"
            trend="up"
            trendValue="+14.8%"
            description="Revenue settlement summary"
            icon={RevenueChart}
            chartData={[15000, 22000, 19000, 28000, 31000, 42000]}
            onClick={() => setShowRevenueModal(true)}
          />

          {/* Card 3: Pending Receivables — Progress Segment Bar */}
          <KpiCard
            title="PENDING RECEIVABLES"
            value={pendingCount}
            variant="brand"
            trend="neutral"
            trendValue="In Progress"
            description="Pending invoices overview"
            icon={ClockIcon}
            onClick={() => { setSelectedStatus('Pending'); setCurrentPage(1); }}
          >
            <InvoiceAgingKpi pendingCount={pendingCount} overdueCount={overdueCount} paidCount={paidCount} />
          </KpiCard>

          {/* Card 4: Overdue & Risk — Urgency Bar */}
          <KpiCard
            title="OVERDUE & AT-RISK"
            value={overdueCount}
            variant="rose"
            trend={overdueCount > 0 ? 'down' : 'neutral'}
            trendValue={overdueCount > 0 ? 'Overdue Action' : 'All Clear'}
            description="Overdue invoice risk warning"
            icon={RiskAlert}
            progressSegments={[
              { label: `${overdueCount} Overdue`, value: overdueCount > 0 ? 80 : 0, color: 'bg-rose-600' },
              { label: 'Clear', value: overdueCount > 0 ? 20 : 100, color: 'bg-slate-300' },
            ]}
            onClick={() => { setSelectedStatus('Overdue'); setCurrentPage(1); }}
          />
        </div>

        {/* Toolbar Control Bar Section (Strictly Horizontal) */}
        <div className="bg-white dark:bg-slate-900 rounded-xl p-2.5 shadow-2xs border border-slate-200 dark:border-slate-800 shrink-0">
          <div className="flex items-center justify-between gap-3 overflow-x-auto">
            
            {/* Left: Search Bar + Status Filter Dropdown */}
            <div className="flex items-center gap-3 shrink-0">
              
              {/* Search Bar */}
              <div className="relative w-64">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                <Input
                  placeholder="Search invoice ID, customer..."
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setCurrentPage(1); }}
                  className="h-9 text-xs pl-8 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F] rounded-lg font-medium"
                />
              </div>

              {/* Status Filter Dropdown */}
              <Select 
                value={selectedStatus} 
                onValueChange={(val: any) => { setSelectedStatus(val); setCurrentPage(1); }}
              >
                <SelectTrigger className="h-9 px-3 w-44 shrink-0 border-slate-200 bg-white rounded-lg text-xs font-semibold text-slate-800 shadow-2xs focus-visible:ring-[#E8450F]/20">
                  <div className="flex items-center gap-2">
                    <Filter className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
                    <SelectValue placeholder="Invoice Status" />
                  </div>
                </SelectTrigger>
                <SelectContent align="start" className="w-48 p-1.5 shadow-lg border border-slate-200 bg-white rounded-xl">
                  <SelectGroup>
                    <SelectLabel className="text-[10px] font-bold tracking-wider uppercase text-slate-400 px-2 py-1">
                      Status Filter
                    </SelectLabel>
                    <SelectItem value="All" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">All Statuses</SelectItem>
                    <SelectItem value="Paid" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-emerald-700">Paid Only</SelectItem>
                    <SelectItem value="Pending" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-amber-700">Pending Only</SelectItem>
                    <SelectItem value="Overdue" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-rose-700">Overdue Only</SelectItem>
                    <SelectItem value="Draft" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-blue-700">Draft Only</SelectItem>
                    <SelectItem value="Cancelled" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-slate-500">Cancelled</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>

            </div>

            {/* Right: Record Ledger Counter */}
            <div className="flex items-center gap-3 shrink-0 ml-auto">
              <div className="text-xs font-semibold text-slate-500">
                Showing <span className="font-extrabold text-slate-900 dark:text-slate-100">{invoices.length}</span> of <span className="font-extrabold text-slate-900 dark:text-slate-100">{totalCount}</span> invoices
              </div>
            </div>

          </div>
        </div>

        {/* Content Workspace: Ledger Data Table */}
        <div className="flex-1 min-h-0 flex flex-col">
          <DataTable
            title={
              <span className="flex items-center gap-2">
                <Receipt className="w-4 h-4 text-amber-500" />
                <span>Invoices Ledger</span>
              </span>
            }
            columns={columns}
            data={invoices}
            bulkActions={bulkActions}
            enableSelection={true}
            isLoading={isLoading}
            isError={isError}
            errorMessage={(error as Error)?.message || 'Failed to load invoices.'}
            searchPlaceholder="Search invoices..."
            searchValue={search}
            onSearchChange={setSearch}
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setCurrentPage(1);
            }}
            totalRecords={totalCount}
            onPageChange={(page) => setCurrentPage(page)}
            onRowClick={(row) => navigate(`/invoices/${row.id}`)}
          />
        </div>

        {/* Revenue Settlement Summary Modal */}
        <Dialog open={showRevenueModal} onOpenChange={setShowRevenueModal}>
          <DialogContent className="max-w-md rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6">
            <DialogHeader>
              <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 flex items-center justify-center mb-2">
                <RevenueChart className="w-5 h-5 text-emerald-600" />
              </div>
              <DialogTitle className="text-lg font-extrabold text-slate-900 dark:text-slate-100">
                Gross Revenue & Settlement Summary
              </DialogTitle>
              <DialogDescription className="text-xs text-slate-500">
                Real-time collection breakdown across paid, pending, and overdue tax invoices.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 my-4 text-xs">
              <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-200/60">
                <div>
                  <div className="font-bold text-emerald-900 dark:text-emerald-300">Total Settled Revenue</div>
                  <div className="text-[10px] text-emerald-700 dark:text-emerald-400">Paid customer invoices ({paidCount})</div>
                </div>
                <span className="font-mono font-extrabold text-emerald-700 dark:text-emerald-300 text-sm">SAR {totalCollectedAmount.toLocaleString()}</span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200/60">
                <div>
                  <div className="font-bold text-amber-900 dark:text-amber-300">Pending Receivables</div>
                  <div className="text-[10px] text-amber-700 dark:text-amber-400">Awaiting customer payment ({pendingCount})</div>
                </div>
                <span className="font-mono font-extrabold text-amber-700 dark:text-amber-300 text-sm">{pendingCount} Invoices</span>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                size="sm"
                className="w-full text-xs font-bold border-slate-200"
                onClick={() => setShowRevenueModal(false)}
              >
                Close Revenue Summary
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

      </div>
    </DashboardLayout>
  );
}
