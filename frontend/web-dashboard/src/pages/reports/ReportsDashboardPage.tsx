import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, 
  ResponsiveContainer, Cell, PieChart, Pie, Legend 
} from 'recharts';
import { 
  TrendingUp, Truck, Users, FileText, AlertTriangle, Download, 
  RotateCw, BarChart3, Calendar as CalendarIcon, Filter, Layers, SlidersHorizontal 
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import DashboardLayout from '@/components/layout/DashboardLayout';
import KpiCard from '@/components/ui/KpiCard';
import { RevenueChart, TruckMotion, FleetTruck, DriverBadge, CalendarAlert } from '@/components/ui/kpi-icons';
import Btn from '@/components/ui/Btn';
import { reportsService } from '@/services/reportsService';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import ReportsHeader from '@/components/reports/ReportsHeader';

const CHART_COLORS = ['#E8450F', '#111111', '#16A34A', '#2563EB', '#CA8A04', '#9898A4'];

export default function ReportsDashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [dateHorizon, setDateHorizon] = useState('6months');
  const [moduleFilter, setModuleFilter] = useState('All');

  const { data: summary, isLoading, error } = useQuery({
    queryKey: ['reports-summary', dateHorizon, moduleFilter],
    queryFn: reportsService.getSummary,
  });

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['reports-summary'] });
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const handleExport = () => {
    if (!summary) return;

    const rows = [
      ['SECTION', 'METRIC / CATEGORY', 'VALUE'],
      ['KPI Summary', 'Total Freight Trips', summary.kpis?.total_trips?.value || 0],
      ['KPI Summary', 'Active Drivers', summary.kpis?.active_drivers?.value || 0],
      ['KPI Summary', 'Fleet Available (Standby)', summary.kpis?.fleet_available?.value || 0],
      ['KPI Summary', 'Fleet On Road', summary.kpis?.fleet_on_trip?.value || 0],
      ['KPI Summary', 'Revenue This Month (SAR)', summary.kpis?.revenue_this_month?.value || 0],
      ['KPI Summary', 'Documents Expiring Soon (30d)', summary.kpis?.docs_expiring_soon?.value || 0],
      ['', '', ''],
      ['Trip Status Distribution', 'Status', 'Count'],
      ...Object.entries(summary.trip_status_distribution || {}).map(([status, count]) => ['Trip Status Distribution', status, count]),
      ['', '', ''],
      ['Monthly Revenue', 'Month', 'Revenue (SAR)'],
      ...(summary.monthly_revenue_chart || []).map((m: any) => ['Monthly Revenue', m.month, m.revenue]),
    ];

    const csvContent = rows.map((r) => r.join(',')).join('\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `executive_reports_summary_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };


  if (isLoading) {
    return (
      <DashboardLayout active="Reports" title="Reports & Analytics">
        <div className="px-4 sm:px-6 pb-6">
          <ReportsHeader activeTab="overview" />
          <div className="animate-pulse grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {[1, 2, 3, 4].map(i => <div key={i} className="h-28 bg-slate-100 dark:bg-slate-800 rounded-xl"></div>)}
          </div>
          <div className="animate-pulse h-96 bg-slate-100 dark:bg-slate-800 rounded-xl"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !summary) {
    return (
      <DashboardLayout active="Reports" title="Reports & Analytics">
        <div className="px-4 sm:px-6 pb-6">
          <ReportsHeader activeTab="overview" />
          <div className="p-6 text-center text-slate-500 mt-12">
            <AlertTriangle size={48} className="mx-auto mb-4 text-rose-500 opacity-50" />
            Failed to load reports. Make sure the analytics engine is online.
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const { kpis, trip_status_distribution, monthly_revenue_chart } = summary;

  const totalTripsVal = kpis?.total_trips?.value || 0;
  const fleetAvailVal = kpis?.fleet_available?.value || 0;
  const fleetOnTripVal = kpis?.fleet_on_trip?.value || 0;
  const totalFleetVal = fleetAvailVal + fleetOnTripVal || 1;
  const fleetUtilizationPct = Math.round((fleetOnTripVal / totalFleetVal) * 100);

  const docsExpiringVal = kpis?.docs_expiring_soon?.value || 0;
  const criticalDocs = Math.min(docsExpiringVal, Math.ceil(docsExpiringVal * 0.4));
  const warningDocs = Math.max(0, docsExpiringVal - criticalDocs);
  const safeDocs = Math.max(5, 20 - docsExpiringVal);

  const donutData = Object.entries(trip_status_distribution || {}).map(([name, value]) => ({
    name,
    value,
  })).filter(d => d.value > 0);

  return (
    <DashboardLayout active="Reports" title="Reports & Analytics">
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col animate-fade-in gap-5 max-w-[1400px] mx-auto">
        <ReportsHeader 
          activeTab="overview" 
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
          onExport={handleExport}
        />

        {/* 4-Card Instrument Panel KPI Section */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 shrink-0">
          {/* Card 1: Monthly Revenue Trend — Financial Sparkline */}
          <KpiCard
            title="TOTAL REVENUE (MONTH)"
            value={`SAR ${(kpis?.revenue_this_month?.value || 0).toLocaleString()}`}
            variant="emerald"
            trend="up"
            trendValue={kpis?.revenue_this_month?.delta ? `${kpis.revenue_this_month.delta}%` : '+8.5%'}
            description="vs previous month"
            icon={RevenueChart}
            chartData={monthly_revenue_chart?.map((d: any) => d.revenue || 5000)}
          />

          {/* Card 2: Trip Volume Fulfillment — Status Segment Bar */}
          <KpiCard
            title="TRIP FULFILLMENT"
            value={totalTripsVal}
            variant="brand"
            trend="up"
            trendValue={kpis?.total_trips?.delta ? `${kpis.total_trips.delta}%` : '+12%'}
            description="Active trip volume"
            icon={TruckMotion}
            progressSegments={[
              { label: 'Completed', value: 70, color: 'bg-emerald-500' },
              { label: 'In Transit', value: 20, color: 'bg-blue-500' },
              { label: 'Draft', value: 10, color: 'bg-amber-500' },
            ]}
          />

          {/* Card 3: Fleet Utilization Capacity — Donut Ratio Gauge */}
          <KpiCard
            title="FLEET CAPACITY"
            value={`${fleetAvailVal} Free`}
            variant="blue"
            trend="neutral"
            trendValue={`${fleetUtilizationPct}% Active`}
            description={`${fleetOnTripVal} currently on route`}
            icon={FleetTruck}
            completionGauge={{
              percentage: fleetUtilizationPct || 80,
              label: `${fleetUtilizationPct}% Fleet Utilized`,
              subtext: `${fleetAvailVal} Available • ${fleetOnTripVal} On Trip`
            }}
          />

          {/* Card 4: Compliance & Risk Horizon — Urgency Bar */}
          <KpiCard
            title="COMPLIANCE RISK"
            value={docsExpiringVal}
            variant="amber"
            trend={docsExpiringVal > 0 ? 'down' : 'neutral'}
            trendValue={docsExpiringVal > 0 ? 'Action Needed' : 'All Clear'}
            description="Documents expiring soon"
            icon={CalendarAlert}
            progressSegments={[
              { label: `${criticalDocs} Critical (<7d)`, value: docsExpiringVal > 0 ? 35 : 0, color: 'bg-rose-500' },
              { label: `${warningDocs} Warning (30d)`, value: docsExpiringVal > 0 ? 45 : 0, color: 'bg-amber-500' },
              { label: `${safeDocs} Clear`, value: docsExpiringVal > 0 ? 20 : 100, color: 'bg-slate-300' },
            ]}
          />
        </div>

        {/* Filter & Control Bar */}
        <div className="bg-white rounded-xl border border-black/[0.08] p-2.5 shadow-2xs shrink-0">
          <div className="flex items-center justify-between gap-3 overflow-x-auto">
            
            {/* Inline Dropdown Controls (Strictly Horizontal) */}
            <div className="flex items-center gap-3 shrink-0">
              
              {/* Date Horizon Dropdown */}
              <Select value={dateHorizon} onValueChange={(val) => { if (val) setDateHorizon(val); }}>
                <SelectTrigger className="h-9 px-3 w-48 shrink-0 border-slate-200 bg-white rounded-lg text-xs font-semibold text-slate-800 hover:bg-slate-50 transition-colors shadow-2xs focus-visible:ring-[#E8450F]/20">
                  <div className="flex items-center gap-2">
                    <CalendarIcon className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
                    <SelectValue placeholder="Date Horizon" />
                  </div>
                </SelectTrigger>
                <SelectContent align="start" className="w-52 p-1.5 shadow-lg border border-slate-200 bg-white rounded-xl">
                  <SelectGroup>
                    <SelectLabel className="text-[10px] font-bold tracking-wider uppercase text-slate-400 px-2 py-1">
                      Time Horizon
                    </SelectLabel>
                    <SelectItem value="thisMonth" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">This Month</SelectItem>
                    <SelectItem value="6months" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">Last 6 Months</SelectItem>
                    <SelectItem value="ytd" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">Year to Date (YTD)</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>

              {/* Module Filter Dropdown */}
              <Select value={moduleFilter} onValueChange={(val) => { if (val) setModuleFilter(val); }}>
                <SelectTrigger className="h-9 px-3 w-48 shrink-0 border-slate-200 bg-white rounded-lg text-xs font-semibold text-slate-800 hover:bg-slate-50 transition-colors shadow-2xs focus-visible:ring-[#E8450F]/20">
                  <div className="flex items-center gap-2">
                    <Layers className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
                    <SelectValue placeholder="Analytics Module" />
                  </div>
                </SelectTrigger>
                <SelectContent align="start" className="w-56 p-1.5 shadow-lg border border-slate-200 bg-white rounded-xl">
                  <SelectGroup>
                    <SelectLabel className="text-[10px] font-bold tracking-wider uppercase text-slate-400 px-2 py-1">
                      Module Category
                    </SelectLabel>
                    <SelectItem value="All" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">All Analytics Modules</SelectItem>
                    <SelectItem value="Revenue" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-emerald-700">Financial & Revenue</SelectItem>
                    <SelectItem value="Fleet" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-blue-700">Fleet Operations</SelectItem>
                    <SelectItem value="Safety" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-amber-700">Safety & Compliance</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>

            </div>

            {/* Sub-page Navigation Tabs */}
            <div className="flex items-center p-0.5 bg-slate-100 dark:bg-slate-800 rounded-lg border border-slate-200/60 dark:border-slate-700/60 shrink-0 ml-auto gap-1">
              <button
                onClick={() => navigate('/reports/revenue')}
                className="px-2.5 py-1 rounded-md text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-white transition-all"
              >
                Revenue Report
              </button>
              <button
                onClick={() => navigate('/reports/fleet')}
                className="px-2.5 py-1 rounded-md text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-white transition-all"
              >
                Fleet Performance
              </button>
              <button
                onClick={() => navigate('/reports/drivers')}
                className="px-2.5 py-1 rounded-md text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-white transition-all"
              >
                Driver Safety
              </button>
              <button
                onClick={() => navigate('/reports/delays')}
                className="px-2.5 py-1 rounded-md text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-white transition-all"
              >
                Delay Report
              </button>
            </div>

          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 shrink-0">
          {/* Revenue Bar Chart */}
          <div className="lg:col-span-2 bg-white border border-black/[0.08] rounded-xl p-5 shadow-2xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Monthly Revenue Trend</h3>
                <p className="text-xs text-slate-500">Gross completed payments breakdown (SAR)</p>
              </div>
            </div>
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={monthly_revenue_chart || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#00000010" />
                  <XAxis 
                    dataKey="month" 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{ fill: '#6E6E80', fontSize: 11, fontWeight: 600 }}
                    dy={10}
                  />
                  <YAxis 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{ fill: '#6E6E80', fontSize: 11, fontWeight: 600 }}
                    tickFormatter={(val) => `SAR ${val / 1000}k`}
                    dx={-10}
                  />
                  <RechartsTooltip 
                    cursor={{ fill: '#00000005' }}
                    contentStyle={{ borderRadius: '12px', border: '1px solid #00000015', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                    formatter={(value: any) => [`SAR ${Number(value).toLocaleString()}`, 'Revenue']}
                  />
                  <Bar dataKey="revenue" radius={[6, 6, 0, 0]} maxBarSize={48}>
                    {(monthly_revenue_chart || []).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={index === (monthly_revenue_chart?.length || 1) - 1 ? '#E8450F' : '#E8450F40'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Trip Status Donut Chart */}
          <div className="bg-white border border-black/[0.08] rounded-xl p-5 shadow-2xs flex flex-col justify-between">
            <h3 className="text-sm font-bold text-slate-900 mb-2">Trip Status Distribution</h3>
            <div className="flex-1 flex flex-col justify-center relative min-h-[200px]">
              {donutData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={75}
                      paddingAngle={4}
                      dataKey="value"
                      stroke="none"
                    >
                      {donutData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <RechartsTooltip 
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                      itemStyle={{ fontWeight: 600, fontSize: '12px' }}
                    />
                    <Legend 
                      verticalAlign="bottom" 
                      height={36} 
                      iconType="circle"
                      formatter={(value) => <span className="text-xs font-semibold text-slate-800">{value}</span>}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-center text-slate-400 text-xs font-medium">No trip data available</div>
              )}
            </div>
          </div>
        </div>

        {/* Compliance Warning Row */}
        <div className="bg-white border border-black/[0.08] rounded-xl p-4 shadow-2xs flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200/80 text-rose-600 flex items-center justify-center shrink-0">
              <FileText className="w-5 h-5 text-rose-600" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-slate-900">Compliance & Expiry Radar Alert</h3>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                <span className="text-rose-600 font-extrabold">{docsExpiringVal}</span> compliance document(s) require renewal within 30 days.
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" className="h-8 text-xs font-semibold" onClick={() => navigate('/documents/expiring')}>
            View Compliance Center
          </Button>
        </div>

      </div>
    </DashboardLayout>
  );
}
