import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Clock, Search, ShieldAlert, ArrowLeft, RotateCw, Download } from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import DataTable from '@/components/ui/DataTable';
import KpiCard from '@/components/ui/KpiCard';
import { RiskAlert, CalendarAlert, CheckBadge } from '@/components/ui/kpi-icons';
import { documentService, type MerconDocument } from '@/services/documentService';
import { downloadCSV } from '@/utils/exportUtils';
import { driverService } from '@/services/driverService';
import { vehicleService } from '@/services/vehicleService';
import { docTypeLabel, daysUntil } from '@/lib/documents';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';

interface ExpiryRow extends MerconDocument {
  entityName: string;
  daysRemaining: number;
}

export default function ExpiryManagementPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const { data: docs = [], isLoading, isError } = useQuery({
    queryKey: ['documents', 'all'],
    queryFn: async () => (await documentService.getAll({ per_page: 200 })).data,
  });
  const { data: drivers = [] } = useQuery({
    queryKey: ['drivers', 'lookup'],
    queryFn: async () => (await driverService.getAll()).data,
  });
  const { data: vehicles = [] } = useQuery({
    queryKey: ['vehicles', 'lookup'],
    queryFn: async () => (await vehicleService.getAll()).data,
  });

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['documents'] });
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const nameFor = useMemo(() => {
    const dMap = new Map(drivers.map((d) => [d.id, `${d.first_name} ${d.last_name}`.trim()]));
    const vMap = new Map(vehicles.map((v) => [v.id, v.plate_number || v.ref_id || '']));
    return (doc: MerconDocument): string => {
      if (doc.entity_type === 'Driver') return dMap.get(doc.entity_id) || 'Unknown Driver';
      if (doc.entity_type === 'Vehicle') return vMap.get(doc.entity_id) || 'Unknown Vehicle';
      return doc.entity_type;
    };
  }, [drivers, vehicles]);

  // Documents that have an expiry date within the next 30 days (or already expired).
  const items = useMemo<ExpiryRow[]>(() => {
    return docs
      .map((doc) => ({ ...doc, entityName: nameFor(doc), daysRemaining: daysUntil(doc.expiry_date) ?? Infinity }))
      .filter((row) => row.daysRemaining <= 30)
      .sort((a, b) => a.daysRemaining - b.daysRemaining);
  }, [docs, nameFor]);

  const expiredCount = items.filter((i) => i.daysRemaining <= 0).length;
  const criticalCount = items.filter((i) => i.daysRemaining > 0 && i.daysRemaining <= 7).length;
  const upcomingCount = items.filter((i) => i.daysRemaining > 7 && i.daysRemaining <= 30).length;
  const totalRadarCount = items.length;

  const filteredItems = items.filter((i) => {
    const q = search.toLowerCase();
    return i.entityName.toLowerCase().includes(q) || docTypeLabel(i.doc_type).toLowerCase().includes(q);
  });

  const entityDocsLink = (row: MerconDocument): string | null => {
    if (row.entity_type === 'Driver') return `/drivers/${row.entity_id}/documents`;
    if (row.entity_type === 'Vehicle') return `/vehicles/${row.entity_id}/documents`;
    return null;
  };

  const columns = [
    {
      header: 'Document Type',
      accessor: (row: ExpiryRow) => (
        <span className="font-extrabold text-slate-900 dark:text-slate-100 text-xs">{docTypeLabel(row.doc_type)}</span>
      ),
    },
    {
      header: 'Entity / Owner',
      accessor: (row: ExpiryRow) => (
        <div>
          <span className="font-bold text-slate-800 dark:text-slate-200 text-xs">{row.entityName}</span>
          <Badge variant="outline" className="ml-2 text-[9px] font-bold bg-slate-100 text-slate-600 border-slate-200">
            {row.entity_type}
          </Badge>
        </div>
      ),
    },
    {
      header: 'Expiry Date',
      accessor: (row: ExpiryRow) => (
        <span className="font-mono text-xs font-semibold text-slate-600 dark:text-slate-400">
          {row.expiry_date ? new Date(row.expiry_date).toLocaleDateString() : '—'}
        </span>
      ),
    },
    {
      header: 'Expiry Radar Status',
      accessor: (row: ExpiryRow) => {
        if (row.daysRemaining <= 0) {
          return (
            <Badge variant="outline" className="bg-rose-50 text-rose-700 border-rose-200 font-bold uppercase text-[10px]">
              <ShieldAlert className="w-3 h-3 mr-1" /> Expired
            </Badge>
          );
        } else if (row.daysRemaining <= 7) {
          return (
            <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-300 font-bold uppercase text-[10px]">
              <AlertTriangle className="w-3 h-3 mr-1" /> Critical ({row.daysRemaining}d)
            </Badge>
          );
        }
        return (
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 font-bold uppercase text-[10px]">
            <Clock className="w-3 h-3 mr-1" /> {row.daysRemaining} days left
          </Badge>
        );
      },
    },
    {
      header: 'Actions',
      accessor: (row: ExpiryRow) => {
        const link = entityDocsLink(row);
        return link ? (
          <Button
            size="sm"
            onClick={() => navigate(link)}
            className="h-7 text-xs font-bold bg-[#E8450F] hover:bg-[#d03d0c] text-white px-3 shadow-2xs rounded-md"
          >
            Update Permit
          </Button>
        ) : (
          <span className="text-xs text-slate-400">—</span>
        );
      },
    },
  ];

  return (
    <DashboardLayout
      active="Documents"
      title="Expiry Management"
    >
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col animate-fade-in gap-5 max-w-[1400px] mx-auto w-full">

        {/* Page Content Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 pb-1 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => navigate('/documents')}
              className="h-9 w-9 p-0 text-slate-600 border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
            >
              <ArrowLeft className="w-4 h-4" />
            </Button>

            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  Document Expiry Radar
                </h1>
                <Badge variant="outline" className="bg-rose-50 text-rose-700 border-rose-200 font-bold text-[10px] uppercase px-2 py-0.5">
                  Compliance Action
                </Badge>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Radar: Active monitoring for licenses and permits expiring within 30 days
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
            >
              <RotateCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh Radar
            </Button>
          </div>
        </div>

        {/* 4-Card Instrument Panel KPI Section */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 shrink-0">
          
          {/* Card 1: Expired Files — Urgency Bar */}
          <KpiCard
            title="ALREADY EXPIRED"
            value={expiredCount}
            variant="rose"
            trend={expiredCount > 0 ? 'down' : 'neutral'}
            trendValue={expiredCount > 0 ? 'Immediate Risk' : 'Zero Expired'}
            description="Lapsed legal permits"
            icon={RiskAlert}
            progressSegments={[
              { label: 'Expired', value: expiredCount > 0 ? 100 : 0, color: 'bg-rose-600' },
            ]}
          />

          {/* Card 2: Critical Expiry (<=7d) — Urgency Bar */}
          <KpiCard
            title="CRITICAL (<=7 DAYS)"
            value={criticalCount}
            variant="amber"
            trend={criticalCount > 0 ? 'down' : 'neutral'}
            trendValue={criticalCount > 0 ? 'Action Due' : 'All Clear'}
            description="Renewal required this week"
            icon={CalendarAlert}
            progressSegments={[
              { label: 'Critical (<7d)', value: criticalCount > 0 ? 100 : 0, color: 'bg-amber-500' },
            ]}
          />

          {/* Card 3: Upcoming Horizon (30d) — Progress Bar */}
          <KpiCard
            title="UPCOMING (30 DAYS)"
            value={upcomingCount}
            variant="blue"
            trend="neutral"
            trendValue="30-Day Window"
            description="Scheduled for renewal"
            icon={Clock}
            progressSegments={[
              { label: 'Upcoming (30d)', value: upcomingCount > 0 ? 100 : 0, color: 'bg-indigo-600' },
            ]}
          />

          {/* Card 4: Total Radar Items — Gauge */}
          <KpiCard
            title="TOTAL RADAR ITEMS"
            value={totalRadarCount}
            variant="brand"
            trend="neutral"
            trendValue="Filtered Active"
            description="Items needing renewal focus"
            icon={CheckBadge}
            completionGauge={{
              percentage: totalRadarCount > 0 ? Math.round((expiredCount / totalRadarCount) * 100) : 0,
              label: `${expiredCount} Expired of ${totalRadarCount}`,
              subtext: `${criticalCount} Critical • ${upcomingCount} Upcoming`
            }}
          />
        </div>

        {/* Content Workspace: Data Table */}
        {isError ? (
          <div className="p-12 text-center text-rose-600 text-xs font-bold bg-white rounded-xl border border-slate-200">Failed to load radar documents.</div>
        ) : (
          <DataTable
            title={
              <span className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <span>Document Expiry Radar Ledger</span>
              </span>
            }
            columns={columns}
            data={filteredItems}
            bulkActions={[
              {
                label: 'Export CSV',
                icon: <Download size={13} />,
                variant: 'secondary' as const,
                onClick: (selectedRows: ExpiryRow[]) => {
                  downloadCSV(selectedRows, 'expiry_radar_export.csv');
                }
              }
            ]}
            enableSelection={true}
            isLoading={isLoading}
            searchPlaceholder="Search entity name or document type..."
            searchValue={search}
            onSearchChange={setSearch}
          />
        )}

      </div>
    </DashboardLayout>
  );
}
