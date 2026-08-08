import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, Filter, TrendingUp, DollarSign, Activity, FileText } from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, AreaChart, Area
} from 'recharts';

import DashboardLayout from '@/components/layout/DashboardLayout';
import KpiCard from '@/components/ui/KpiCard';
import { MoneyBills, InvoiceDoc, ActivityPulse, RevenueChart } from '@/components/ui/kpi-icons';
import Btn from '@/components/ui/Btn';
import { reportsService } from '@/services/reportsService';

/** Compact SAR formatter: 333000 -> "SAR 333K", 2450 -> "SAR 2,450" */
function sar(value: number): string {
  if (Math.abs(value) >= 1000) {
    return `SAR ${(value / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 })}K`;
  }
  return `SAR ${value.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
}

import ReportsHeader from '@/components/reports/ReportsHeader';

export default function RevenueReportsPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['reports', 'revenue'],
    queryFn: () => reportsService.getRevenueReport(6),
  });

  const handleExport = () => {
    if (!data) return;

    const rows = [
      ['SECTION', 'METRIC / CATEGORY', 'VALUE (SAR)'],
      ['Revenue Overview', 'All-Time Gross Paid Revenue', data.total_all_time || 0],
      ['Revenue Overview', 'Outstanding Unpaid Invoices', data.outstanding_total || 0],
      ['Revenue Overview', 'Paid Invoices Count', data.paid_invoice_count || 0],
      ['Revenue Overview', 'Average Revenue Per Invoice', Math.round(data.avg_per_invoice || 0)],
      ['', '', ''],
      ['Monthly Revenue Breakdown', 'Month', 'Gross Paid Revenue (SAR)'],
      ...(data.monthly_breakdown || []).map((r) => ['Monthly Revenue Breakdown', r.month, r.revenue]),
      ['', '', ''],
      ['Top Customers by Revenue', 'Customer Name', 'Paid Revenue (SAR)'],
      ...(data.top_customers || []).map((c) => ['Top Customers by Revenue', `"${c.name}"`, c.value]),
    ];

    const csvContent = rows.map((r) => r.join(',')).join('\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `revenue_analytics_report_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };


  const revenueData = useMemo(
    () => (data?.monthly_breakdown ?? []).map((r) => ({
      month: r.month,
      revenue: Number(r.revenue),
    })),
    [data],
  );
  const customerData = useMemo(
    () => (data?.top_customers ?? []).map((c) => ({ name: c.name, value: Number(c.value) })),
    [data],
  );

  return (
    <DashboardLayout active="Reports" title="Revenue Analytics">
      <div className="px-4 sm:px-6 pb-6 animate-fade-in max-w-[1400px] mx-auto">
        <ReportsHeader 
          activeTab="revenue" 
          onRefresh={() => refetch()}
          onExport={handleExport}
        />

        {/* KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <KpiCard
            title="Gross Revenue (Paid)"
            value={isLoading ? '—' : sar(data?.total_all_time ?? 0)}
            icon={MoneyBills}
            variant="emerald"
            trend="up"
            trendValue="+12.8%"
            description="All-time paid total"
            chartData={revenueData.map((d: any) => d.total || 10000)}
          />
          <KpiCard
            title="Outstanding (Unpaid)"
            value={isLoading ? '—' : sar(data?.outstanding_total ?? 0)}
            icon={InvoiceDoc}
            variant="rose"
            trend="down"
            trendValue="Pending"
            description="Uncollected balances"
            chartData={[5000, 7200, 6100, 8900, 7400, 9200, data?.outstanding_total || 6000]}
          />
          <KpiCard
            title="Avg Revenue / Invoice"
            value={isLoading ? '—' : sar(data?.avg_per_invoice ?? 0)}
            icon={ActivityPulse}
            variant="amber"
            trend="up"
            trendValue="Avg Ticket"
            description="Per invoice average"
            chartData={[1200, 1400, 1350, 1600, 1550, 1750, data?.avg_per_invoice || 1500]}
          />
          <KpiCard
            title="Paid Invoices"
            value={isLoading ? '—' : (data?.paid_invoice_count ?? 0).toLocaleString('en-US')}
            icon={RevenueChart}
            variant="blue"
            trend="neutral"
            trendValue="Settled"
            description="Completed invoices"
            chartData={revenueData.map((d: any) => d.count || 5)}
          />
        </div>

        {/* Charts Row 1 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

          {/* Monthly Revenue Area Chart */}
          <div className="lg:col-span-2 bg-white border border-black/[0.08] rounded-lg p-5 shadow-sm">
            <div className="mb-6">
              <h3 className="text-sm font-bold text-[#111]">Monthly Revenue</h3>
              <p className="text-xs text-[#6E6E80]">Gross revenue from paid invoices — last 6 months</p>
            </div>

            <div className="h-[280px]">
              {isLoading ? (
                <div className="h-full flex items-center justify-center text-xs text-[#9898A4]">Loading…</div>
              ) : isError ? (
                <div className="h-full flex items-center justify-center text-xs text-[#DC2626]">Failed to load revenue data.</div>
              ) : revenueData.length === 0 ? (
                <div className="h-full flex items-center justify-center text-xs text-[#9898A4]">No paid invoices yet.</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={revenueData} margin={{ top: 10, right: 0, left: -10, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#16A34A" stopOpacity={0.15}/>
                        <stop offset="95%" stopColor="#16A34A" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F0F0F2" />
                    <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#9898A4' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#9898A4' }} axisLine={false} tickLine={false} tickFormatter={(val) => `${val/1000}k`} />
                    <Tooltip formatter={(val) => sar(Number(val))} contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                    <Area type="monotone" dataKey="revenue" name="Gross Revenue" stroke="#16A34A" strokeWidth={2} fillOpacity={1} fill="url(#colorRev)" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Top Customers Bar Chart */}
          <div className="bg-white border border-black/[0.08] rounded-lg p-5 shadow-sm">
            <div className="mb-6">
              <h3 className="text-sm font-bold text-[#111]">Revenue by Customer</h3>
              <p className="text-xs text-[#6E6E80]">Top clients by paid revenue</p>
            </div>

            <div className="h-[280px]">
              {isLoading ? (
                <div className="h-full flex items-center justify-center text-xs text-[#9898A4]">Loading…</div>
              ) : customerData.length === 0 ? (
                <div className="h-full flex items-center justify-center text-xs text-[#9898A4]">No paid invoices yet.</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart layout="vertical" data={customerData} margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#F0F0F2" />
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" tick={{ fontSize: 11, fill: '#444', fontWeight: 600 }} axisLine={false} tickLine={false} width={80} />
                    <Tooltip cursor={{ fill: 'transparent' }} formatter={(val) => sar(Number(val))} contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                    <Bar dataKey="value" name="Revenue (SAR)" fill="#E8450F" radius={[0, 4, 4, 0]} barSize={24} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

        </div>

      </div>
    </DashboardLayout>
  );
}
