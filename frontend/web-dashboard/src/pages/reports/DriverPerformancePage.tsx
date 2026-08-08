import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, Users, AlertTriangle, CheckCircle2, Route } from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ScatterChart, Scatter, ZAxis,
} from 'recharts';

import DashboardLayout from '@/components/layout/DashboardLayout';
import KpiCard from '@/components/ui/KpiCard';
import DataTable from '@/components/ui/DataTable';
import { DriverBadge, CheckBadge, RiskAlert, RouteLine } from '@/components/ui/kpi-icons';
import Btn from '@/components/ui/Btn';
import { reportsService, type DriverPerfRow } from '@/services/reportsService';

/** AI risk score → level. Lower is safer. */
function riskLevel(score: number | null): { label: string; cls: string } {
  if (score == null) return { label: 'N/A', cls: 'bg-[#F5F5F7] text-[#6E6E80]' };
  if (score < 4) return { label: 'Low', cls: 'bg-[#F0FDF4] text-[#16A34A]' };
  if (score < 7) return { label: 'Medium', cls: 'bg-[#FFFBEB] text-[#D97706]' };
  return { label: 'High', cls: 'bg-[#FEF2F2] text-[#DC2626]' };
}

import ReportsHeader from '@/components/reports/ReportsHeader';

export default function DriverPerformancePage() {
  const { data: response, isLoading, isError, refetch } = useQuery({
    queryKey: ['reports', 'drivers'],
    queryFn: () => reportsService.getDriverPerformance({ page: 1, per_page: 500 }),
  });

  const rows = response?.data || [];

  const handleExport = () => {
    if (!rows || rows.length === 0) return;

    const headers = ['S/L', 'Driver Name', 'Driver Ref ID', 'Status', 'AI Safety Risk Score', 'Risk Level', 'Total Trips', 'Completed Trips'];
    let sumTrips = 0;
    let sumCompleted = 0;

    const dataRows = rows.map((d, idx) => {
      sumTrips += d.total_trips || 0;
      sumCompleted += d.completed_trips || 0;
      const risk = riskLevel(d.ai_risk_score);

      return [
        idx + 1,
        `"${d.name || ''}"`,
        `"${d.ref_id || ''}"`,
        `"${d.status || ''}"`,
        d.ai_risk_score ?? 'N/A',
        `"${risk.label}"`,
        d.total_trips || 0,
        d.completed_trips || 0,
      ];
    });

    const summaryRow = ['TOTALS', '', '', '', '', '', sumTrips, sumCompleted];
    const csvContent = [headers.join(','), ...dataRows.map((r) => r.join(',')), summaryRow.join(',')].join('\n');
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `driver_safety_report_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };


  const kpis = useMemo(() => {
    const totalDrivers = rows.length;
    const available = rows.filter((d) => d.status === 'Available').length;
    const scored = rows.filter((d) => d.ai_risk_score != null);
    const avgRisk = scored.length ? (scored.reduce((s, d) => s + (d.ai_risk_score ?? 0), 0) / scored.length) : null;
    const totalTrips = rows.reduce((s, d) => s + d.total_trips, 0);
    return { totalDrivers, available, avgRisk, totalTrips };
  }, [rows]);

  const tripsByDriver = useMemo(
    () => [...rows]
      .sort((a, b) => b.completed_trips - a.completed_trips)
      .slice(0, 8)
      .map((d) => ({ name: d.name.split(' ')[0] || d.ref_id || '—', trips: d.completed_trips })),
    [rows],
  );

  const scatter = useMemo(
    () => rows
      .filter((d) => d.ai_risk_score != null)
      .map((d) => ({ x: d.total_trips, y: d.ai_risk_score as number, z: d.completed_trips, name: d.name })),
    [rows],
  );

  const topDrivers = useMemo(
    () => [...rows].sort((a, b) => b.completed_trips - a.completed_trips).slice(0, 5),
    [rows],
  );

  const completion = (d: DriverPerfRow) => (d.total_trips > 0 ? Math.round((d.completed_trips / d.total_trips) * 100) : 0);

  const chartState = isLoading ? 'loading' : isError ? 'error' : 'ready';
  const Fallback = ({ empty }: { empty: boolean }) => (
    <div className="h-full flex items-center justify-center text-xs text-[#9898A4]">
      {chartState === 'loading' ? 'Loading…' : chartState === 'error' ? 'Failed to load.' : empty ? 'No data yet.' : ''}
    </div>
  );

  return (
    <DashboardLayout active="Reports" title="Driver Safety">
      <div className="px-4 sm:px-6 pb-6 animate-fade-in max-w-[1400px] mx-auto">
        <ReportsHeader 
          activeTab="drivers" 
          onRefresh={() => refetch()}
          onExport={handleExport}
        />

        {/* KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <KpiCard
            title="Total Drivers"
            value={isLoading ? '—' : kpis.totalDrivers.toString()}
            icon={DriverBadge}
            variant="blue"
            trend="neutral"
            trendValue="Registered"
            description="Active & off-duty"
            chartData={[10, 14, 18, 16, 22, 25, 28]}
          />
          <KpiCard
            title="Available Now"
            value={isLoading ? '—' : kpis.available.toString()}
            icon={CheckBadge}
            variant="emerald"
            trend="up"
            trendValue="Ready"
            description="Available for dispatch"
            chartData={[8, 10, 12, 11, 15, 14, 16]}
          />
          <KpiCard
            title="Avg. Risk Score"
            value={isLoading ? '—' : (kpis.avgRisk == null ? 'N/A' : kpis.avgRisk.toFixed(1))}
            icon={RiskAlert}
            variant="rose"
            trend={kpis.avgRisk != null && kpis.avgRisk > 3 ? 'down' : 'neutral'}
            trendValue={kpis.avgRisk != null && kpis.avgRisk > 3 ? 'Elevated' : 'Safe'}
            description="AI safety score"
            chartData={[2.1, 1.8, 2.4, 2.0, 1.9, 1.7, kpis.avgRisk || 2.0]}
          />
          <KpiCard
            title="Total Trips"
            value={isLoading ? '—' : kpis.totalTrips.toLocaleString()}
            icon={RouteLine}
            variant="brand"
            trend="up"
            trendValue="+18%"
            description="Trips executed"
            chartData={[45, 60, 55, 75, 80, 95, 110]}
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">

          <div className="bg-white border border-black/[0.08] rounded-lg p-5 shadow-sm">
            <div className="mb-6">
              <h3 className="text-sm font-bold text-[#111]">Completed Trips per Driver</h3>
              <p className="text-xs text-[#6E6E80]">Busiest 8 drivers</p>
            </div>
            <div className="h-[280px]">
              {chartState === 'ready' && tripsByDriver.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={tripsByDriver} margin={{ top: 10, right: 0, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F0F0F2" />
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#9898A4' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#9898A4' }} axisLine={false} tickLine={false} allowDecimals={false} />
                    <Tooltip cursor={{ fill: '#F5F5F7' }} contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                    <Bar dataKey="trips" name="Completed Trips" fill="#2563EB" radius={[4, 4, 0, 0]} barSize={36} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <Fallback empty={tripsByDriver.length === 0} />}
            </div>
          </div>

          <div className="bg-white border border-black/[0.08] rounded-lg p-5 shadow-sm">
            <div className="mb-6">
              <h3 className="text-sm font-bold text-[#111]">Risk vs Trip Volume</h3>
              <p className="text-xs text-[#6E6E80]">Risk score (Y) relative to total trips (X)</p>
            </div>
            <div className="h-[280px]">
              {chartState === 'ready' && scatter.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 10, right: 20, bottom: 0, left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#F0F0F2" />
                    <XAxis type="number" dataKey="x" name="Trips" tick={{ fontSize: 11, fill: '#9898A4' }} axisLine={false} tickLine={false} />
                    <YAxis type="number" dataKey="y" name="Risk" domain={[0, 10]} tick={{ fontSize: 11, fill: '#9898A4' }} axisLine={false} tickLine={false} />
                    <ZAxis type="number" dataKey="z" range={[100, 400]} name="Completed" />
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                    <Scatter name="Drivers" data={scatter} fill="#E8450F" opacity={0.8} />
                  </ScatterChart>
                </ResponsiveContainer>
              ) : <Fallback empty={scatter.length === 0} />}
            </div>
          </div>

        </div>

        {/* Top Drivers Table */}
        <DataTable
          title="🏆 Top Drivers by Completed Trips"
          columns={[
            {
              header: 'Driver',
              accessor: (d: DriverPerfRow) => <span className="font-bold text-slate-900 dark:text-slate-100">{d.name}</span>
            },
            {
              header: 'Completed / Total',
              accessor: (d: DriverPerfRow) => <span className="text-slate-700 dark:text-slate-300 font-medium">{d.completed_trips} / {d.total_trips}</span>
            },
            {
              header: 'Completion %',
              accessor: (d: DriverPerfRow) => <span className="font-extrabold text-emerald-600 dark:text-emerald-400">{completion(d)}%</span>
            },
            {
              header: 'AI Risk Level',
              accessor: (d: DriverPerfRow) => {
                const risk = riskLevel(d.ai_risk_score);
                return <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${risk.cls}`}>{risk.label}</span>;
              }
            }
          ]}
          data={topDrivers}
          enableSelection={true}
          isLoading={isLoading}
        />

      </div>
    </DashboardLayout>
  );
}
