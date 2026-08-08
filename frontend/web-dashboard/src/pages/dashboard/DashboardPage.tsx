import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { 
  Truck, Car, DollarSign, AlertTriangle, 
  ArrowRight, ArrowUpRight, Loader2, RefreshCw, Clock, CheckCircle2, LayoutDashboard
} from 'lucide-react';
import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, 
  CartesianGrid, Tooltip, PieChart, Pie, Cell 
} from 'recharts';

import DashboardLayout from '@/components/layout/DashboardLayout';
import KpiCard from '@/components/ui/KpiCard';
import { TruckMotion, FleetTruck, MoneyBills, CalendarAlert } from '@/components/ui/kpi-icons';
import { HeroStatBanner, TelemetryDarkCard, GlassmeterCard, CompactCapsulePill } from '@/components/ui/NewKpiCardStyles';
import { DispatchTelemetryRadarKpi, SpeedometerGaugeKpi } from '@/components/ui/CustomKpiWidgets';
import StatusBadge from '@/components/ui/StatusBadge';
import Btn from '@/components/ui/Btn';
import TripCardSwiper from '@/components/trips/TripCardSwiper';
import PostTripSettlementModal from '@/components/trips/PostTripSettlementModal';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { reportsService } from '@/services/reportsService';
import { tripService, Trip } from '@/services/tripService';
import { authStore } from '@/store/authStore';

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = authStore.getUser();
  const operatorName = user?.name ? user.name.split(' ')[0] : 'Mohammed';
  const [selectedSettlementTrip, setSelectedSettlementTrip] = useState<Trip | null>(null);

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  // Fetch Reports Summary
  const { 
    data: summary, 
    isLoading: summaryLoading, 
    error: summaryError,
    refetch: refetchSummary 
  } = useQuery({
    queryKey: ['reports-summary'],
    queryFn: reportsService.getSummary,
  });

  // Fetch Unsettled Completed Trips (Waiting/Labor Check)
  const { 
    data: unsettledTrips = [], 
    refetch: refetchUnsettled 
  } = useQuery({
    queryKey: ['unsettled-trips'],
    queryFn: tripService.getUnsettled,
  });

  // Fetch Recent Trips
  const { 
    data: recentTripsRes, 
    isLoading: tripsLoading,
  } = useQuery({
    queryKey: ['recent-trips'],
    queryFn: () => tripService.getAll({ per_page: 5 }),
  });

  const recentTrips = recentTripsRes?.data || [];

  // Default values and trend/status mapping
  const kpis = summary?.kpis || {
    total_trips: { value: 0, delta: null },
    active_drivers: { value: 0, delta: null },
    fleet_available: { value: 0, delta: null },
    fleet_on_trip: { value: 0, delta: null },
    revenue_this_month: { value: 0, delta: null },
    docs_expiring_soon: { value: 0, delta: null },
  };

  const trendData = summary?.monthly_revenue_chart || [];

  const pieDataRaw = summary?.trip_status_distribution || {};
  const pieData = Object.keys(pieDataRaw).map((key) => {
    let color = '#9898A4';
    if (key === 'Completed') color = '#16A34A';
    if (key === 'InTransit') color = '#D97706';
    if (key === 'Draft') color = '#2563EB';
    if (key === 'Cancelled') color = '#DC2626';

    return {
      name: key,
      value: pieDataRaw[key],
      color,
    };
  });

  return (
    <DashboardLayout 
      active="Dashboard" 
      title="Dashboard" 
    >
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col gap-5 animate-fade-in">
        {/* Page Content Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 pb-1">
          <div className="flex items-center gap-3">
            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  {getGreeting()}, {operatorName}
                </h1>
              </div>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                Here's what's happening today across your operations.
              </p>
            </div>
          </div>

          {/* Page-Level Action Buttons */}
          <div className="flex items-center gap-2.5">
            <Btn 
              label="Refresh Data" 
              variant="secondary" 
              size="sm" 
              icon={<RefreshCw size={13} />} 
              onClick={() => { refetchSummary(); refetchUnsettled(); }} 
              shortcut={{ key: 'r', alt: true }}
            />
          </div>
        </div>

        {summaryError && (
          <div className="bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3 rounded-xl shadow-xs flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0" />
            <div className="text-sm font-semibold">
              Failed to load real-time dashboard KPIs. Showing cached or default values.
              <span className="block text-xs font-normal opacity-80">{(summaryError as Error)?.message || 'Server connection error.'}</span>
            </div>
          </div>
        )}

        {/* Pending Post-Trip Financial Settlement Notification Banner */}
        {unsettledTrips.length > 0 && (
          <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200/80 rounded-2xl p-4 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center shrink-0">
                <Clock size={20} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-amber-800 uppercase tracking-wider">Action Required</span>
                  <span className="bg-amber-200/60 text-amber-900 text-[10px] font-extrabold px-2 py-0.5 rounded-full">
                    {unsettledTrips.length} Pending
                  </span>
                </div>
                <h4 className="text-sm font-bold text-gray-900 mt-0.5">
                  Post-Trip Waiting / Labor Charges Check Pending
                </h4>
                <p className="text-xs text-gray-600">
                  Trips have been completed. Please review if waiting time or labor charges need to be entered before final invoice settlement.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto pb-1 md:pb-0 shrink-0">
              {unsettledTrips.slice(0, 3).map((t) => (
                <button
                  key={t.id}
                  onClick={() => setSelectedSettlementTrip(t)}
                  className="px-3 py-2 bg-white hover:bg-amber-100/50 border border-amber-200 rounded-xl text-xs font-bold text-amber-900 shadow-2xs flex items-center gap-1.5 transition-all"
                >
                  <DollarSign size={13} className="text-[#E8450F]" />
                  <span>#{t.ref_id || t.id.substring(0, 6)}</span>
                  <span className="text-[10px] font-normal text-amber-700">Review</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Instrument Panel KPI Section */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 shrink-0">
          
          {/* Card 1: Monthly Revenue — Donut Gauge (Strongest Emphasis / Brand Variant) */}
          <KpiCard
            title="MONTHLY REVENUE"
            value={`SAR ${((kpis.revenue_this_month.value || 0) / 1000).toFixed(1)}K`}
            variant="brand"
            trend={kpis.revenue_this_month.delta !== null ? (kpis.revenue_this_month.delta >= 0 ? 'up' : 'down') : 'up'}
            trendValue={kpis.revenue_this_month.delta !== null ? `${Math.abs(kpis.revenue_this_month.delta)}%` : '+14.8%'}
            description="Gross settled payments"
            icon={MoneyBills}
            completionGauge={{
              percentage: 84,
              label: '84% Monthly Target Reached',
              subtext: 'SAR 420K Monthly Target'
            }}
            onClick={() => navigate('/invoices')}
          />
          
          {/* Card 2: Total Freight Trips with Telemetry Radar Widget */}
          <KpiCard
            title="TOTAL FREIGHT TRIPS"
            value={kpis.total_trips.value}
            variant="purple"
            trend={kpis.total_trips.delta !== null ? (kpis.total_trips.delta >= 0 ? 'up' : 'down') : 'up'}
            trendValue={kpis.total_trips.delta !== null ? `${Math.abs(kpis.total_trips.delta)}%` : '+12.4%'}
            description="Active & completed manifests"
            icon={TruckMotion}
            onClick={() => navigate('/trips')}
          >
            <DispatchTelemetryRadarKpi 
              activeCount={kpis.fleet_on_trip.value || 0} 
              totalCount={kpis.total_trips.value || 1} 
              label="Live Dispatch Telemetry" 
            />
          </KpiCard>

          {/* Card 3: Active Fleet with Speedometer Dial Widget */}
          <KpiCard
            title="ACTIVE FLEET (ON ROAD)"
            value={kpis.fleet_on_trip.value}
            variant="blue"
            trend="up"
            trendValue={`${Math.round(((kpis.fleet_on_trip.value || 1) / ((kpis.fleet_on_trip.value || 0) + (kpis.fleet_available.value || 1))) * 100)}%`}
            description="Fleet active capacity"
            icon={FleetTruck}
            onClick={() => navigate('/vehicles')}
          >
            <SpeedometerGaugeKpi 
              percentage={Math.round(((kpis.fleet_on_trip.value || 1) / ((kpis.fleet_on_trip.value || 0) + (kpis.fleet_available.value || 1))) * 100)} 
              label="Fleet Capacity Utilized"
              subtext={`${kpis.fleet_available.value || 0} Standby Trucks`}
            />
          </KpiCard>

          {/* Card 4: Compliance Renewals — Urgency Segments */}
          <KpiCard
            title="COMPLIANCE RENEWALS"
            value={kpis.docs_expiring_soon.value}
            variant="amber"
            trend={kpis.docs_expiring_soon.value > 0 ? 'down' : 'neutral'}
            trendValue={kpis.docs_expiring_soon.value > 0 ? 'Action Required' : 'All Clear'}
            description="Permits expiring within 30d"
            icon={CalendarAlert}
            progressSegments={[
              { label: `${kpis.docs_expiring_soon.value} Due Soon`, value: kpis.docs_expiring_soon.value > 0 ? 80 : 0, color: 'bg-amber-500' },
              { label: 'Clear', value: kpis.docs_expiring_soon.value > 0 ? 20 : 100, color: 'bg-slate-300' },
            ]}
            onClick={() => navigate('/documents/expiring')}
          />
        </div>

        {/* Horizontal Trip Cards Swiper Section */}
        <div className="shrink-0 w-full">
          <TripCardSwiper />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 shrink-0">
          {/* Revenue / Trip Trend */}
          <Card className="lg:col-span-2 border-black/[0.06] shadow-sm rounded-2xl bg-white flex flex-col justify-between">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-extrabold uppercase tracking-wider text-slate-800 dark:text-slate-200">Revenue Trend</CardTitle>
              <CardDescription className="text-xs text-[#6E6E80]">Monthly completed freight payments (SAR)</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 min-h-[200px] pb-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData} margin={{ top: 10, right: 15, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#E8450F" stopOpacity={0.12} />
                      <stop offset="95%" stopColor="#E8450F" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F0F0F2" vertical={false} />
                  <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#6E6E80', fontWeight: 600 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: '#6E6E80', fontWeight: 600 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 12, fontSize: 11, border: '1px solid #F0F0F2', fontFamily: 'Plus Jakarta Sans' }} />
                  <Area type="monotone" dataKey="revenue" stroke="#E8450F" strokeWidth={2} fill="url(#revenueGrad)" name="Revenue" />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Trip Status Distribution */}
          <Card className="border-black/[0.06] shadow-sm rounded-2xl bg-white flex flex-col justify-between">
            <CardHeader className="pb-0">
              <CardTitle className="text-xs font-extrabold uppercase tracking-wider text-slate-800 dark:text-slate-200">Trip Status Distribution</CardTitle>
              <CardDescription className="text-xs text-[#6E6E80]">Manifest progress status overview</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col justify-between flex-1 pt-2 pb-4">
              <div className="flex items-center justify-center my-2">
                <PieChart width={160} height={140}>
                  <Pie 
                    data={pieData} 
                    cx="50%" 
                    cy="50%" 
                    innerRadius={42} 
                    outerRadius={62} 
                    dataKey="value" 
                    strokeWidth={0}
                  >
                    {pieData.map((e, index) => (
                      <Cell key={`cell-${index}`} fill={e.color} />
                    ))}
                  </Pie>
                </PieChart>
              </div>

              <div className="space-y-1.5 shrink-0 border-t border-black/[0.04] pt-3">
                {pieData.map((d) => (
                  <div key={d.name} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 font-medium text-[#444]">
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: d.color }} />
                      {d.name}
                    </span>
                    <span className="font-bold text-[#111]">{d.value}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Trips Table Ledger */}
        <Card className="border-black/[0.06] shadow-sm rounded-2xl bg-white overflow-hidden shrink-0">
          <CardHeader className="py-4 px-5 border-b border-[#F0F0F2] flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-xs font-extrabold uppercase tracking-wider text-slate-800 dark:text-slate-200">Recent Operations Trips</CardTitle>
              <CardDescription className="text-xs text-[#6E6E80]">Latest active and dispatched manifests</CardDescription>
            </div>
            <Button 
              variant="ghost"
              size="sm"
              onClick={() => navigate('/trips')}
              className="text-xs text-[#E8450F] font-bold gap-1 hover:text-[#d03d0c]"
            >
              <span>View All Trips</span>
              <ArrowRight size={13} />
            </Button>
          </CardHeader>

          <CardContent className="p-0">
            <Table>
              <TableHeader className="bg-[#FAFAFA]">
                <TableRow>
                  <TableHead className="text-[10px] font-bold text-[#9898A4] uppercase tracking-wider">Trip ID</TableHead>
                  <TableHead className="text-[10px] font-bold text-[#9898A4] uppercase tracking-wider">Customer</TableHead>
                  <TableHead className="text-[10px] font-bold text-[#9898A4] uppercase tracking-wider">Cargo Type</TableHead>
                  <TableHead className="text-[10px] font-bold text-[#9898A4] uppercase tracking-wider">Driver</TableHead>
                  <TableHead className="text-[10px] font-bold text-[#9898A4] uppercase tracking-wider">Vehicle</TableHead>
                  <TableHead className="text-[10px] font-bold text-[#9898A4] uppercase tracking-wider">Status</TableHead>
                  <TableHead className="text-[10px] font-bold text-[#9898A4] uppercase tracking-wider">Planned Start</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tripsLoading ? (
                  Array.from({ length: 3 }).map((_, index) => (
                    <TableRow key={index}>
                      <TableCell><div className="h-4 skeleton w-12" /></TableCell>
                      <TableCell><div className="h-4 skeleton w-24" /></TableCell>
                      <TableCell><div className="h-4 skeleton w-20" /></TableCell>
                      <TableCell><div className="h-4 skeleton w-28" /></TableCell>
                      <TableCell><div className="h-4 skeleton w-16" /></TableCell>
                      <TableCell><div className="h-5 skeleton w-16 rounded-full" /></TableCell>
                      <TableCell><div className="h-4 skeleton w-24" /></TableCell>
                    </TableRow>
                  ))
                ) : recentTrips.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-10 text-xs font-semibold text-[#9898A4]">
                      No recent trips available. Click 'New Trip' to create one.
                    </TableCell>
                  </TableRow>
                ) : (
                  recentTrips.map((t) => (
                    <TableRow 
                      key={t.id} 
                      onClick={() => navigate(`/trips/${t.id}`)}
                      className="cursor-pointer hover:bg-[#FAFAFA] transition-colors"
                    >
                      <TableCell className="font-mono text-xs font-bold text-[#E8450F]">{t.ref_id || 'Draft'}</TableCell>
                      <TableCell className="text-xs font-semibold text-[#111]">{t.customer?.name || '—'}</TableCell>
                      <TableCell className="text-xs font-medium text-[#444]">{t.cargo_type}</TableCell>
                      <TableCell className="text-xs font-medium text-[#444]">
                        {t.driver ? (
                          `${t.driver.first_name} ${t.driver.last_name}`
                        ) : (
                          <span className="italic text-slate-400 font-normal">Unassigned</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs font-semibold text-[#6E6E80]">
                        {t.vehicle?.plate_number ? (
                          <span className="font-mono">{t.vehicle.plate_number}</span>
                        ) : (
                          <span className="italic text-slate-400 font-normal">Unassigned</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={t.status} />
                      </TableCell>
                      <TableCell className="text-xs font-medium text-[#9898A4]">
                        {t.planned_start ? new Date(t.planned_start).toLocaleDateString() : '—'}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Post-Trip Settlement Modal */}
        <PostTripSettlementModal
          isOpen={!!selectedSettlementTrip}
          trip={selectedSettlementTrip}
          onClose={() => setSelectedSettlementTrip(null)}
          onSuccess={() => {
            refetchSummary();
            refetchUnsettled();
          }}
        />

      </div>
    </DashboardLayout>
  );
}

