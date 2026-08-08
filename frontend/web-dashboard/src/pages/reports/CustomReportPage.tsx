import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, FileText, Truck, TrendingUp, BarChart3 } from 'lucide-react';
import { format, subDays, startOfMonth, subMonths, startOfWeek } from 'date-fns';

import DashboardLayout from '@/components/layout/DashboardLayout';
import KpiCard from '@/components/ui/KpiCard';
import { TruckMotion, RevenueChart } from '@/components/ui/kpi-icons';
import Btn from '@/components/ui/Btn';
import DataTable from '@/components/ui/DataTable';
import StatusBadge from '@/components/ui/StatusBadge';
import { reportsService } from '@/services/reportsService';
import { customerService } from '@/services/customerService';

import { downloadExcel } from '@/utils/exportUtils';

type DatePreset = 'this_week' | 'this_month' | 'last_month' | 'custom';

import ReportsHeader from '@/components/reports/ReportsHeader';

export default function CustomReportPage() {
  const [preset, setPreset] = useState<DatePreset>('this_month');
  const [customerId, setCustomerId] = useState<string>('all');
  
  // Custom date range state
  const [customStart, setCustomStart] = useState<string>('');
  const [customEnd, setCustomEnd] = useState<string>('');

  const { data: customersResponse } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customerService.getAll(),
  });

  const customers = useMemo(() => {
    return Array.isArray(customersResponse) ? customersResponse : (customersResponse as any)?.data || [];
  }, [customersResponse]);

  // Compute active dates based on preset
  const { startDate, endDate } = useMemo(() => {
    const today = new Date();
    if (preset === 'this_week') {
      return { 
        startDate: format(startOfWeek(today, { weekStartsOn: 1 }), 'yyyy-MM-dd'), 
        endDate: format(today, 'yyyy-MM-dd') 
      };
    }
    if (preset === 'this_month') {
      return { 
        startDate: format(startOfMonth(today), 'yyyy-MM-dd'), 
        endDate: format(today, 'yyyy-MM-dd') 
      };
    }
    if (preset === 'last_month') {
      const lastMonth = subMonths(today, 1);
      const start = startOfMonth(lastMonth);
      const end = subDays(startOfMonth(today), 1);
      return { 
        startDate: format(start, 'yyyy-MM-dd'), 
        endDate: format(end, 'yyyy-MM-dd') 
      };
    }
    return { startDate: customStart, endDate: customEnd };
  }, [preset, customStart, customEnd]);

  // Query custom report
  const { data: reportData, isLoading, refetch } = useQuery({
    queryKey: ['custom-report', startDate, endDate, customerId],
    queryFn: () => reportsService.getCustomReport({
      startDate: startDate || undefined,
      endDate: endDate || undefined,
      customerId: customerId !== 'all' ? customerId : undefined,
    }),
  });

  const handleExportCSV = () => {
    if (!reportData?.trips || reportData.trips.length === 0) return;
    
    const headers = [
      'S/L',
      'DATE',
      'JOB #',
      'DRIVER NAME',
      'VEHICLE NO:',
      'VEHICLE TYPE',
      'MOBILE NUMBER',
      'ASTOOL AL SHAHLA OR 3RD PARTY',
      'SENDER/CUSTOMER',
      'RECEIVER',
      'WAITING/LABOR CHARGES',
      'ADDITIONAL STOPS',
      'BILLING AMOUNT',
      'TOTAL AMOUNT',
      'TRIP CHARGES',
      'BALANCE AMOUNT',
      'COMPANY NAME'
    ];

    let sumWaitingLabor = 0;
    let sumAdditionalStops = 0;
    let sumBilling = 0;
    let sumTotal = 0;
    let sumTripCharges = 0;
    let sumBalance = 0;

    const rows = reportData.trips.map((t: any, index: number) => {
      const waiting = Number(t.waiting_labor_charges || 0);
      const stops = Number(t.additional_stop_charges || 0);
      const billing = Number(t.billing_amount || 0);
      const total = Number(t.total_amount || 0);
      const tripCharges = Number(t.trip_charges || 0);
      const balance = Number(t.balance_amount || 0);

      sumWaitingLabor += waiting;
      sumAdditionalStops += stops;
      sumBilling += billing;
      sumTotal += total;
      sumTripCharges += tripCharges;
      sumBalance += balance;

      return [
        index + 1,
        format(new Date(t.date), 'dd-MM-yyyy'),
        t.ref_id || 'N/A',
        t.driver,
        t.vehicle,
        t.vehicle_type || '10 TON',
        t.driver_phone || '',
        t.carrier_name || 'MERCON LOGISTICS',
        t.customer,
        t.receiver || '',
        waiting,
        stops,
        billing,
        total,
        tripCharges,
        balance,
        t.company_name || t.customer
      ];
    });

    const summaryRow = [
      'TOTALS',
      '',
      '',
      '',
      '',
      '',
      '',
      '',
      '',
      '',
      sumWaitingLabor,
      sumAdditionalStops,
      sumBilling,
      sumTotal,
      sumTripCharges,
      sumBalance,
      ''
    ];

    const selectedCust = customers.find((c: any) => c.id === customerId);
    const titleText = selectedCust 
      ? `MERCON Trip Ledger Report - ${selectedCust.name || selectedCust.company_name}`
      : 'MERCON Custom Operational & Trip Ledger Report';

    downloadExcel(titleText, headers, [...rows, summaryRow], `mercon_trip_ledger_${format(new Date(), 'yyyyMMdd_HHmm')}.xls`);
  };


  const columns = [
    { header: 'S/L', accessor: (_row: any, idx: number) => <span className="text-gray-400 font-mono text-xs">{idx + 1}</span> },
    { header: 'Date', accessor: (row: any) => format(new Date(row.date), 'dd-MM-yyyy') },
    { header: 'Job #', accessor: (row: any) => <span className="font-mono text-xs font-bold text-[#E8450F]">{row.ref_id}</span> },
    { header: 'Driver Name', accessor: (row: any) => <span className="font-semibold text-[#111]">{row.driver}</span> },
    { header: 'Vehicle No:', accessor: (row: any) => <span className="font-mono text-xs">{row.vehicle}</span> },
    { header: 'Carrier / Provider', accessor: (row: any) => <span className="text-xs text-gray-600">{row.carrier_name || 'MERCON LOGISTICS'}</span> },
    { header: 'Sender / Customer', accessor: (row: any) => <span className="font-semibold text-[#111]">{row.customer}</span> },
    { header: 'Waiting / Labor', accessor: (row: any) => <span className="font-mono text-xs font-semibold text-amber-700">SAR {Number(row.waiting_labor_charges || 0).toLocaleString()}</span> },
    { header: 'Billing Amount', accessor: (row: any) => <span className="font-mono text-xs font-semibold">SAR {Number(row.billing_amount || 0).toLocaleString()}</span> },
    { header: 'Total Amount', accessor: (row: any) => <span className="font-mono text-xs font-bold text-green-700">SAR {Number(row.total_amount || 0).toLocaleString()}</span> },
    { header: 'Trip Charges', accessor: (row: any) => <span className="font-mono text-xs font-bold text-red-600">SAR {Number(row.trip_charges || 0).toLocaleString()}</span> },
    { header: 'Balance Amount', accessor: (row: any) => <span className="font-mono text-xs font-bold text-indigo-700">SAR {Number(row.balance_amount || 0).toLocaleString()}</span> },
    { header: 'Status', accessor: (row: any) => <StatusBadge status={row.status} /> },
  ];


  return (
    <DashboardLayout active="Reports" title="Custom Generator">
      <div className="px-4 sm:px-6 pb-6 animate-fade-in max-w-[1400px] mx-auto">
        <ReportsHeader 
          activeTab="custom" 
          onRefresh={() => refetch()}
          onExport={handleExportCSV}
        />
        {/* Filters Section */}
        <div className="bg-white rounded-lg border border-black/[0.08] p-6 mb-6 shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
              <label className="block text-xs font-bold text-[#111] mb-2">Time Range</label>
              <select 
                value={preset} 
                onChange={(e) => setPreset(e.target.value as DatePreset)}
                className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#E8450F]"
              >
                <option value="this_week">This Week</option>
                <option value="this_month">This Month</option>
                <option value="last_month">Last Month</option>
                <option value="custom">Custom Range</option>
              </select>
            </div>

            {preset === 'custom' && (
              <>
                <div>
                  <label className="block text-xs font-bold text-[#111] mb-2">Start Date</label>
                  <input 
                    type="date"
                    value={customStart}
                    onChange={e => setCustomStart(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#E8450F]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-[#111] mb-2">End Date</label>
                  <input 
                    type="date"
                    value={customEnd}
                    onChange={e => setCustomEnd(e.target.value)}
                    className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#E8450F]"
                  />
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-bold text-[#111] mb-2">Customer</label>
              <select 
                value={customerId} 
                onChange={(e) => setCustomerId(e.target.value)}
                className="w-full bg-gray-50 border border-gray-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-[#E8450F]"
              >
                <option value="all">All Customers</option>
                {customers.map((c: any) => (
                  <option key={c.id} value={c.id}>{c.name || c.company_name}</option>
                ))}
              </select>
            </div>

            {(preset === 'custom') ? (
              <div className="md:col-span-1">
                <Btn label="Generate Report" onClick={() => refetch()} className="w-full" disabled={!customStart || !customEnd} />
              </div>
            ) : null}
          </div>
        </div>

        {/* KPIs */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6 animate-pulse">
            <div className="h-28 bg-black/5 rounded-lg"></div>
            <div className="h-28 bg-black/5 rounded-lg"></div>
            <div className="h-28 bg-black/5 rounded-lg"></div>
          </div>
        ) : reportData ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
              <KpiCard
                label="Total Trips"
                value={reportData.kpis.total_trips.toString()}
                icon={TruckMotion}
                color="#E8450F"
                bg="#E8450F1A"
                iconVariant="light"
              />
              <KpiCard
                label="Total Revenue"
                value={`SAR ${reportData.kpis.total_revenue.toLocaleString()}`}
                icon={RevenueChart}
                color="#16A34A"
                bg="#F0FDF4"
                iconVariant="light"
              />
              <div className="bg-white border border-black/[0.08] rounded-lg p-4 shadow-sm flex items-center gap-4">
                <FileText size={28} className="text-orange-500 dark:text-orange-400" />
                <div>
                  <p className="text-xs font-bold text-[#6E6E80] uppercase tracking-wider mb-0.5">Top Status</p>
                  <h3 className="text-xl font-black text-[#111]">
                    {Object.entries(reportData.trip_status_distribution)
                      .sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A'}
                  </h3>
                </div>
              </div>
            </div>

            <div className="flex-1 min-h-0 flex flex-col">
              <DataTable
                title={
                  <span className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-[#E8450F]" />
                    <span>
                      {customerId !== 'all' && customers.find((c: any) => c.id === customerId)
                        ? `Customer Report: ${customers.find((c: any) => c.id === customerId)?.name || customers.find((c: any) => c.id === customerId)?.company_name}`
                        : "Custom Operational & Trip Ledger Report"}
                    </span>
                  </span>
                }
                columns={columns}
                data={reportData.trips}
                enableSelection={true}
                isLoading={false}
              />
            </div>
          </>

        ) : (
          <div className="text-center text-[#6E6E80] py-12">
            No data generated yet. Adjust your filters above to build a report.
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
