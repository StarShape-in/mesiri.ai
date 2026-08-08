import { useMemo, useState } from 'react';
import { 
  UploadCloud, FileText, Search, FolderOpen, Shield, Car, User as UserIcon, Eye, Download, 
  RotateCw, AlertTriangle, CheckCircle2, FileCheck, Briefcase, Clock, ChevronLeft, ChevronRight,
  ChevronsLeft, ChevronsRight, FileBadge2, FileBarChart2, FileClock, FileKey2, LayoutGrid, List, Check, HardDrive,
  ExternalLink, Trash2, Filter, ShieldAlert, ArrowUpDown, X
} from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import DashboardLayout from '@/components/layout/DashboardLayout';
import KpiCard from '@/components/ui/KpiCard';
import DataTable, { Column } from '@/components/ui/DataTable';
import { CalendarAlert as CalendarAlertIcon, DriverBadge, FleetTruck, CheckBadge } from '@/components/ui/kpi-icons';
import { documentService, type MerconDocument } from '@/services/documentService';
import { downloadCSV } from '@/utils/exportUtils';
import { driverService } from '@/services/driverService';
import { vehicleService } from '@/services/vehicleService';
import { docTypeLabel, categoryForDocType, categoryForEntity, type DocCategory, daysUntil } from '@/lib/documents';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import UploadDocumentModal from '@/components/ui/UploadDocumentModal';
import { cn } from '@/lib/utils';

// ─── Category & Icon Config ──────────────────────────────────────────────────

const CATEGORY_TABS: Array<'All' | DocCategory> = ['All', 'Drivers', 'Vehicles', 'Operations', 'Company'];

const CATEGORY_CONFIG: Record<DocCategory, {
  icon: React.ElementType;
  color: string;
  iconBg: string;
  borderColor: string;
  label: string;
  description: string;
}> = {
  Drivers:    { icon: UserIcon,      color: 'text-[#E8450F]',   iconBg: 'bg-[#FFF0EB] dark:bg-[#E8450F]/10', borderColor: 'border-[#E8450F]/20', label: 'Driver Documents', description: 'Licenses, medical certificates & permits' },
  Vehicles:   { icon: Car,           color: 'text-blue-600',    iconBg: 'bg-blue-50 dark:bg-blue-950/30',    borderColor: 'border-blue-200/60',   label: 'Vehicle Documents', description: 'Registrations, insurance & Istimara' },
  Operations: { icon: Briefcase,     color: 'text-violet-600',  iconBg: 'bg-violet-50 dark:bg-violet-950/30',borderColor: 'border-violet-200/60', label: 'Operations Files', description: 'Waybills, PODs & customs clearance' },
  Company:    { icon: Shield,        color: 'text-emerald-600', iconBg: 'bg-emerald-50 dark:bg-emerald-950/30', borderColor: 'border-emerald-200/60', label: 'Company Records', description: 'Contracts, invoices & corporate filings' },
};

const DOC_TYPE_ICON: Record<string, React.ElementType> = {
  DriverLicense:       FileBadge2,
  VehicleRegistration: FileKey2,
  Insurance:           FileCheck,
  POD:                 FileBarChart2,
  CustomsClearance:    FileKey2,
  Waybill:             FileClock,
  Contract:            FileText,
  Invoice:             FileBarChart2,
};

const REGULATORY_BODY: Record<string, string> = {
  DriverLicense:       'Saudi MOT / Transport Auth',
  VehicleRegistration: 'MOMRAH / Istimara',
  Insurance:           'Najm Insurance Protection',
  POD:                 'MERCON Dispatch System',
  CustomsClearance:    'ZATCA Saudi Customs',
  Waybill:             'Saudi Land Transport Auth',
  Contract:            'Ministry of Commerce',
  Invoice:             'ZATCA Tax Authority',
};

// ─── Expiry Status Helpers ───────────────────────────────────────────────────

function expiryStatus(iso: string | null | undefined): 'expired' | 'critical' | 'warning' | 'valid' | 'none' {
  const days = daysUntil(iso);
  if (days === null) return 'none';
  if (days <= 0) return 'expired';
  if (days <= 7) return 'critical';
  if (days <= 30) return 'warning';
  return 'valid';
}

const EXPIRY_BADGE: Record<string, { label: string; className: string }> = {
  expired:  { label: 'Expired',      className: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/30 dark:text-rose-400 dark:border-rose-800/50' },
  critical: { label: 'Critical <7d', className: 'bg-rose-50 text-rose-600 border-rose-200 dark:bg-rose-950/20 dark:text-rose-400 dark:border-rose-800/40' },
  warning:  { label: 'Due Soon',     className: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/20 dark:text-amber-400 dark:border-amber-800/40' },
  valid:    { label: 'Valid',         className: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/20 dark:text-emerald-400 dark:border-emerald-800/40' },
  none:     { label: 'No Expiry',    className: 'bg-slate-50 text-slate-500 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700' },
};

// ─── Enriched Document Type ──────────────────────────────────────────────────

type EnrichedDocument = MerconDocument & {
  entityName: string;
  category: DocCategory;
  expStatus: 'expired' | 'critical' | 'warning' | 'valid' | 'none';
  daysLeft: number | null;
  issuer: string;
};

// ─── Main Page Component ──────────────────────────────────────────────────────

export default function DocumentsCenterPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // State
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [activeCategory, setActiveCategory] = useState<'All' | DocCategory>('All');
  const [expiryFilter, setExpiryFilter] = useState<'all' | 'expired' | 'critical' | 'warning' | 'valid'>('all');
  const [search, setSearch] = useState('');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [previewDoc, setPreviewDoc] = useState<EnrichedDocument | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Queries
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

  // Entity lookup name map
  const nameFor = useMemo(() => {
    const dMap = new Map(drivers.map((d) => [d.id, `${d.first_name} ${d.last_name}`.trim()]));
    const vMap = new Map(vehicles.map((v) => [v.id, v.plate_number || v.ref_id || '']));
    return (doc: MerconDocument): string => {
      if (doc.entity_type === 'Driver') return dMap.get(doc.entity_id) || 'Unknown Driver';
      if (doc.entity_type === 'Vehicle') return vMap.get(doc.entity_id) || 'Unknown Vehicle';
      return doc.entity_type;
    };
  }, [drivers, vehicles]);

  // Grouped Folders by Category
  const foldersByCategory = useMemo(() => {
    const map: Record<DocCategory, { count: number; docTypes: string[] }> = {
      Drivers: { count: 0, docTypes: [] },
      Vehicles: { count: 0, docTypes: [] },
      Operations: { count: 0, docTypes: [] },
      Company: { count: 0, docTypes: [] },
    };

    for (const d of docs) {
      const cat = categoryForEntity(d.entity_type);
      map[cat].count += 1;
      if (!map[cat].docTypes.includes(d.doc_type)) {
        map[cat].docTypes.push(d.doc_type);
      }
    }
    return map;
  }, [docs]);

  // Enriched & Filtered Documents
  const filteredDocs = useMemo(() => {
    return docs
      .map((d) => ({
        ...d,
        entityName: nameFor(d),
        category: categoryForEntity(d.entity_type),
        expStatus: expiryStatus(d.expiry_date),
        daysLeft: daysUntil(d.expiry_date),
        issuer: REGULATORY_BODY[d.doc_type] || 'Saudi Authority',
      }))
      .filter((d) => {
        const matchesCat = activeCategory === 'All' || d.category === activeCategory;
        const matchesExpiry = expiryFilter === 'all' || d.expStatus === expiryFilter;
        const q = search.toLowerCase();
        const matchesSearch =
          docTypeLabel(d.doc_type).toLowerCase().includes(q) ||
          d.entityName.toLowerCase().includes(q) ||
          d.issuer.toLowerCase().includes(q) ||
          d.id.toString().includes(q);
        return matchesCat && matchesExpiry && matchesSearch;
      });
  }, [docs, nameFor, activeCategory, expiryFilter, search]);

  // Calculated Vault Telematics
  const totalDocsCount = docs.length;
  const expiringDocs = docs.filter((d) => {
    const days = daysUntil(d.expiry_date);
    return days !== null && days <= 30;
  });
  const expiringCount = expiringDocs.length;
  const expiredCount = docs.filter((d) => (daysUntil(d.expiry_date) ?? 1) <= 0).length;
  const criticalCount = expiringDocs.filter((d) => {
    const days = daysUntil(d.expiry_date);
    return days !== null && days > 0 && days <= 7;
  }).length;
  const safeCount = Math.max(0, totalDocsCount - expiringCount);
  const compliancePct = totalDocsCount > 0 ? Math.round((safeCount / totalDocsCount) * 100) : 100;

  // Selection handlers
  const toggleSelectAll = () => {
    if (selectedDocIds.length === filteredDocs.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(filteredDocs.map((d) => d.id));
    }
  };

  const toggleSelectRow = (id: string) => {
    setSelectedDocIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  };

  return (
    <DashboardLayout active="Documents" title="Documents Center">
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col animate-fade-in gap-5 max-w-[1400px] mx-auto w-full">

        {/* ── Page Header ─────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 pb-1 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <FolderOpen className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />
            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  Documents Center
                </h1>
                <Badge variant="outline" className="bg-slate-100 text-slate-700 border-slate-200 text-[10px] font-bold tracking-wide uppercase px-2 py-0.5 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700">
                  Compliance Repository
                </Badge>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Centralized vault — driver licenses, Istimara permits, waybills, and compliance filings
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Expiry Radar Trigger */}
            <Button
              variant="outline"
              size="sm"
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 bg-white hover:bg-rose-50 shadow-2xs text-rose-600 hover:text-rose-700 dark:bg-slate-900 dark:border-slate-800"
              onClick={() => navigate('/documents/expiry')}
            >
              <AlertTriangle className="h-3.5 w-3.5 text-rose-500" />
              Expiry Radar {expiringCount > 0 && <span className="ml-0.5 bg-rose-500 text-white text-[9px] font-bold rounded-full px-1.5 py-0.5">{expiringCount}</span>}
            </Button>

            {/* View Mode Switcher */}
            <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-1 rounded-lg border border-slate-200/80 dark:border-slate-700">
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  'p-1.5 rounded-md transition-all text-xs flex items-center gap-1 font-semibold',
                  viewMode === 'list'
                    ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xs'
                    : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                )}
                title="List View"
              >
                <List size={14} />
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={cn(
                  'p-1.5 rounded-md transition-all text-xs flex items-center gap-1 font-semibold',
                  viewMode === 'grid'
                    ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xs'
                    : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                )}
                title="Grid View"
              >
                <LayoutGrid size={14} />
              </button>
            </div>

            {/* Upload Button */}
            <Button
              size="sm"
              className="h-9 gap-1.5 text-xs bg-[#E8450F] hover:bg-[#d03d0c] text-white font-bold shadow-xs rounded-lg px-4"
              onClick={() => setIsUploadOpen(true)}
            >
              <UploadCloud className="w-4 h-4" /> Upload Document
            </Button>

            {/* Refresh Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="h-9 w-9 p-0 text-slate-600 border-slate-200 bg-white hover:bg-slate-50 shadow-2xs dark:bg-slate-900 dark:border-slate-800"
              title="Refresh Vault"
            >
              <RotateCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>



        {/* ── Folder Explorer & Breadcrumb ─────────────────────────────────── */}
        <div className="shrink-0 space-y-3">
          {/* Path Breadcrumb */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
              <FolderOpen className="w-4 h-4 text-indigo-500" />
              <span>Vault Root</span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
              <span className="text-slate-900 dark:text-slate-100 font-bold">{activeCategory} Category</span>
              {expiryFilter !== 'all' && (
                <>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
                  <Badge variant="outline" className="text-[10px] font-bold capitalize bg-amber-50 text-amber-700 border-amber-200">
                    {expiryFilter} Expiry Filter
                  </Badge>
                </>
              )}
            </div>

            {/* Folder Tabs Switcher */}
            <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg border border-slate-200/60 dark:border-slate-700">
              {CATEGORY_TABS.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={cn(
                    'px-3 py-1.5 text-[11px] font-bold rounded-md transition-all whitespace-nowrap',
                    activeCategory === cat
                      ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-2xs'
                      : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* 4 Category Folder Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {(['Drivers', 'Vehicles', 'Operations', 'Company'] as DocCategory[]).map((cat) => {
              const cfg = CATEGORY_CONFIG[cat];
              const Icon = cfg.icon;
              const catData = foldersByCategory[cat];
              const isActive = activeCategory === cat;

              return (
                <Card
                  key={cat}
                  onClick={() => setActiveCategory(isActive ? 'All' : cat)}
                  className={cn(
                    'group border rounded-2xl overflow-hidden cursor-pointer transition-all duration-150 hover:shadow-xs hover:-translate-y-0.5 bg-white dark:bg-slate-900 outline-none focus-visible:ring-2 focus-visible:ring-[#E8450F]/30',
                    isActive ? `border-2 ${cfg.borderColor} shadow-xs` : 'border-slate-200 dark:border-slate-800 hover:border-[#E8450F]/45'
                  )}
                  tabIndex={0}
                  role="button"
                  aria-label={`${cfg.label} folder, ${catData.count} files`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setActiveCategory(isActive ? 'All' : cat);
                    }
                  }}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2.5">
                      <div className={cn('w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-transform group-hover:scale-105', cfg.iconBg)}>
                        <Icon className={cn('w-4 h-4', cfg.color)} />
                      </div>
                      <Badge variant="outline" className="text-[10px] font-bold text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700">
                        {catData.count} files
                      </Badge>
                    </div>

                    <h4 className={cn('font-extrabold text-sm mb-0.5 transition-colors group-hover:text-slate-900 dark:group-hover:text-white', cfg.color)}>{cfg.label}</h4>
                    <p className="text-[10px] text-slate-400 font-medium mb-3">{cfg.description}</p>

                    <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800">
                      <span>{catData.docTypes.length} Document Types</span>
                      <ChevronRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-slate-600 dark:group-hover:text-slate-200 transition-colors" />
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        {/* ── Control Toolbar & Filters ───────────────────────────────────── */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-3 shadow-2xs flex flex-wrap items-center justify-between gap-3 shrink-0">
          
          <div className="flex items-center gap-3 flex-1 min-w-[280px]">
            {/* Search Input */}
            <div className="relative flex-1 max-w-sm">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <Input
                type="text"
                placeholder="Search by file name, driver, vehicle plate, or issuer..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-9 text-xs pl-8 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F] rounded-lg font-medium"
              />
            </div>

            {/* Expiry Dropdown Filter */}
            <div className="w-44">
              <Select value={expiryFilter} onValueChange={(v) => setExpiryFilter(v as any)}>
                <SelectTrigger className="h-9 text-xs font-semibold border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus-visible:ring-[#E8450F]/20">
                  <div className="flex items-center gap-1.5">
                    <Filter className="w-3.5 h-3.5 text-slate-400" />
                    <SelectValue placeholder="Expiry Status" />
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all" className="text-xs font-semibold">All Statuses</SelectItem>
                  <SelectItem value="expired" className="text-xs text-rose-600 font-semibold">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-rose-600 shrink-0" />
                      <span>Expired</span>
                    </span>
                  </SelectItem>
                  <SelectItem value="critical" className="text-xs text-rose-500 font-semibold">
                    <span className="flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                      <span>Critical (&lt;7d)</span>
                    </span>
                  </SelectItem>
                  <SelectItem value="warning" className="text-xs text-amber-600 font-semibold">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                      <span>Due Soon (&lt;30d)</span>
                    </span>
                  </SelectItem>
                  <SelectItem value="valid" className="text-xs text-emerald-600 font-semibold">
                    <span className="flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      <span>Valid</span>
                    </span>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Bulk Action Controls */}
          <div className="flex items-center gap-2">
            {selectedDocIds.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="h-9 gap-1.5 text-xs font-bold border-indigo-200 bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
                onClick={() => alert(`Downloading ZIP archive for ${selectedDocIds.length} documents...`)}
              >
                <Download className="w-3.5 h-3.5" />
                Bulk Download ({selectedDocIds.length})
              </Button>
            )}

            <Badge variant="outline" className="text-[11px] font-mono font-bold text-slate-500 px-3 py-1 bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700">
              Showing {filteredDocs.length} of {totalDocsCount} files
            </Badge>
          </div>
        </div>

        {/* ── Document Vault Area (List vs Grid View) ──────────────────────── */}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
            <RotateCw className="w-8 h-8 animate-spin text-indigo-500 opacity-70" />
            <p className="text-xs font-medium">Loading compliance repository...</p>
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-20 gap-2 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
            <AlertTriangle className="w-8 h-8 text-rose-400 opacity-70" />
            <p className="text-xs text-rose-500 font-medium">Failed to load repository files.</p>
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
            <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
              <FolderOpen className="w-7 h-7 text-slate-300 dark:text-slate-600" />
            </div>
            <div className="text-center">
              <p className="text-sm font-bold text-slate-700 dark:text-slate-300">No documents found</p>
              <p className="text-xs text-slate-400 mt-0.5">Try clearing your search query or status filter</p>
            </div>
          </div>
        ) : viewMode === 'list' ? (
          <DataTable
            title={
              <span className="flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-indigo-500" />
                <span>Compliance Document Repository</span>
              </span>
            }
            columns={[
              {
                header: 'Document Name',
                accessor: (row) => {
                  const DocIcon = DOC_TYPE_ICON[row.doc_type] ?? FileText;
                  const catCfg = CATEGORY_CONFIG[row.category];
                  return (
                    <div className="flex items-center gap-3">
                      <div className={cn('w-9 h-9 rounded-xl flex items-center justify-center shrink-0', catCfg?.iconBg)}>
                        <DocIcon className={cn('w-4 h-4', catCfg?.color)} />
                      </div>
                      <div>
                        <span 
                          onClick={() => setPreviewDoc(row)}
                          className="font-bold text-slate-900 dark:text-slate-100 text-xs hover:text-indigo-600 dark:hover:text-indigo-400 cursor-pointer block"
                        >
                          {docTypeLabel(row.doc_type)}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">#{row.id.toString().slice(0, 8)}</span>
                      </div>
                    </div>
                  );
                }
              },
              {
                header: 'Entity Owner',
                accessor: (row) => {
                  const catCfg = CATEGORY_CONFIG[row.category];
                  return (
                    <div className="flex items-center gap-1.5">
                      {catCfg && <catCfg.icon className={cn('w-3.5 h-3.5 shrink-0', catCfg.color)} />}
                      <span className="text-xs text-slate-700 dark:text-slate-300 font-semibold truncate max-w-[160px]">{row.entityName}</span>
                    </div>
                  );
                }
              },
              {
                header: 'Issuer Authority',
                accessor: (row) => <span className="text-xs text-slate-500 font-medium">{row.issuer}</span>
              },
              {
                header: 'Expiry Status',
                accessor: (row) => {
                  const expBadge = EXPIRY_BADGE[row.expStatus];
                  return (
                    <span className={cn('inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full border', expBadge.className)}>
                      {row.expStatus === 'expired' || row.expStatus === 'critical' ? (
                        <AlertTriangle className="w-2.5 h-2.5" />
                      ) : row.expStatus === 'valid' ? (
                        <CheckCircle2 className="w-2.5 h-2.5" />
                      ) : row.expStatus === 'warning' ? (
                        <Clock className="w-2.5 h-2.5" />
                      ) : null}
                      {expBadge.label}
                    </span>
                  );
                }
              },
              {
                header: 'Days Left',
                accessor: (row) => (
                  row.expiry_date ? (
                    <div>
                      <span className="text-xs text-slate-700 dark:text-slate-300 font-mono block">
                        {new Date(row.expiry_date).toLocaleDateString()}
                      </span>
                      {row.daysLeft !== null && (
                        <span className={cn(
                          'text-[10px] font-bold',
                          row.daysLeft <= 0 ? 'text-rose-600' : row.daysLeft <= 7 ? 'text-rose-500' : row.daysLeft <= 30 ? 'text-amber-600' : 'text-emerald-600'
                        )}>
                          {row.daysLeft <= 0 ? `${Math.abs(row.daysLeft)}d overdue` : `${row.daysLeft}d remaining`}
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400">—</span>
                  )
                )
              },
              {
                header: 'Actions',
                headerClassName: 'text-right',
                accessor: (row) => (
                  <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => setPreviewDoc(row)}
                      className="w-8 h-8 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 flex items-center justify-center text-slate-500 hover:text-indigo-600 transition-colors"
                      title="Preview File"
                    >
                      <Eye size={14} />
                    </button>
                    <a
                      href={row.file_url}
                      download
                      className="w-8 h-8 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 flex items-center justify-center text-slate-500 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                      title="Download File"
                    >
                      <Download size={14} />
                    </a>
                  </div>
                )
              }
            ]}
            data={filteredDocs}
            bulkActions={[
              {
                label: 'Export CSV',
                icon: <Download size={13} />,
                variant: 'secondary' as const,
                onClick: (selectedRows: MerconDocument[]) => {
                  downloadCSV(selectedRows, 'documents_export.csv');
                }
              }
            ]}
            enableSelection={true}
            isLoading={isLoading}
            searchPlaceholder="Search document name or entity..."
            searchValue={search}
            onSearchChange={setSearch}
            onRowClick={(row) => setPreviewDoc(row)}
          />
        ) : (
          
          /* GRID VIEW MODE */
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5 shrink-0">
            {filteredDocs.map((doc) => {
              const DocIcon = DOC_TYPE_ICON[doc.doc_type] ?? FileText;
              const expBadge = EXPIRY_BADGE[doc.expStatus];
              const catCfg = CATEGORY_CONFIG[doc.category];

              return (
                <Card
                  key={doc.id}
                  className="border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-2xs hover:shadow-xs hover:border-[#E8450F]/45 hover:-translate-y-0.5 transition-all duration-150 ease-in-out bg-white dark:bg-slate-900 flex flex-col justify-between outline-none focus-visible:ring-2 focus-visible:ring-[#E8450F]/30"
                  tabIndex={0}
                  role="button"
                  aria-label={`Document: ${docTypeLabel(doc.doc_type)} for ${doc.entityName}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setPreviewDoc(doc);
                    }
                  }}
                >
                  <CardContent className="p-4 space-y-3">
                    {/* Header Top */}
                    <div className="flex items-center justify-between">
                      <div className={cn('w-9 h-9 rounded-xl flex items-center justify-center shrink-0', catCfg.iconBg)}>
                        <DocIcon className={cn('w-4.5 h-4.5', catCfg.color)} />
                      </div>
                      <span className={cn('text-[10px] font-bold px-2 py-0.5 rounded-full border', expBadge.className)}>
                        {expBadge.label}
                      </span>
                    </div>

                    {/* Document Info */}
                    <div>
                      <h4 
                        onClick={() => setPreviewDoc(doc)}
                        className="font-extrabold text-sm text-slate-900 dark:text-slate-100 hover:text-indigo-600 cursor-pointer truncate"
                      >
                        {docTypeLabel(doc.doc_type)}
                      </h4>
                      <p className="text-xs text-slate-500 font-medium truncate mt-0.5">{doc.entityName}</p>
                    </div>

                    {/* Issuer & Expiry */}
                    <div className="bg-slate-50 dark:bg-slate-800/50 p-2 rounded-lg border border-slate-100 dark:border-slate-800 space-y-1 text-[11px]">
                      <div className="flex justify-between text-slate-500">
                        <span>Issuer:</span>
                        <span className="font-semibold text-slate-700 dark:text-slate-300 truncate max-w-[120px]">{doc.issuer}</span>
                      </div>
                      {doc.expiry_date && (
                        <div className="flex justify-between text-slate-500">
                          <span>Expires:</span>
                          <span className="font-mono font-semibold text-slate-700 dark:text-slate-300">
                            {new Date(doc.expiry_date).toLocaleDateString()}
                          </span>
                        </div>
                      )}
                    </div>
                  </CardContent>

                  {/* Actions Footer */}
                  <div className="p-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPreviewDoc(doc)}
                      className="h-7 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:text-indigo-600 gap-1"
                    >
                      <Eye size={13} /> Preview
                    </Button>

                    <a
                      href={doc.file_url}
                      download
                      className="h-7 px-2.5 rounded-md bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-bold text-slate-700 dark:text-slate-200 hover:bg-slate-50 flex items-center gap-1 shadow-2xs"
                    >
                      <Download size={13} /> Download
                    </a>
                  </div>
                </Card>
              );
            })}
          </div>
        )}

      </div>

      {/* ── Document Preview Modal Drawer ─────────────────────────────────── */}
      <Dialog open={!!previewDoc} onOpenChange={(open) => !open && setPreviewDoc(null)}>
        <DialogContent className="max-w-xl rounded-2xl p-0 overflow-hidden border-slate-200 dark:border-slate-800">
          <DialogHeader className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-600" />
                <DialogTitle className="text-base font-extrabold text-slate-900 dark:text-slate-100">
                  {previewDoc ? docTypeLabel(previewDoc.doc_type) : 'Document Preview'}
                </DialogTitle>
              </div>
            </div>
          </DialogHeader>

          {previewDoc && (
            <div className="p-6 space-y-5">
              {/* Document File Viewer Placeholder Card */}
              <div className="w-full h-48 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex flex-col items-center justify-center gap-3 p-4 text-center">
                <FileText className="w-8 h-8 text-orange-500 dark:text-orange-400" />
                <div>
                  <h4 className="text-xs font-extrabold text-slate-900 dark:text-slate-100">
                    {docTypeLabel(previewDoc.doc_type)} File
                  </h4>
                  <p className="text-[11px] text-slate-400 font-mono mt-0.5">#{previewDoc.id}</p>
                </div>
                <a
                  href={previewDoc.file_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs font-bold text-indigo-600 dark:text-indigo-400 hover:underline"
                >
                  <ExternalLink size={13} /> Open Full Resolution File
                </a>
              </div>

              {/* Metadata Key-Value Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div className="space-y-1">
                  <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Entity Owner</span>
                  <p className="font-semibold text-slate-800 dark:text-slate-200">{nameFor(previewDoc)}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Category</span>
                  <p className="font-semibold text-slate-800 dark:text-slate-200">{categoryForEntity(previewDoc.entity_type)}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Issuing Regulatory Body</span>
                  <p className="font-semibold text-slate-800 dark:text-slate-200">{REGULATORY_BODY[previewDoc.doc_type] || 'Saudi Authority'}</p>
                </div>

                <div className="space-y-1">
                  <span className="text-slate-400 font-bold uppercase text-[10px] tracking-wider">Expiry Date</span>
                  <p className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                    {previewDoc.expiry_date ? new Date(previewDoc.expiry_date).toLocaleDateString() : 'N/A'}
                  </p>
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="px-6 py-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900 flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setPreviewDoc(null)} className="text-xs">
              Close
            </Button>
            {previewDoc && (
              <a
                href={previewDoc.file_url}
                download
                className="h-8 px-4 rounded-md bg-[#E8450F] text-white text-xs font-bold hover:bg-[#d03d0c] inline-flex items-center gap-1.5"
              >
                <Download size={14} /> Download Document
              </a>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Upload Document Modal ────────────────────────────────────────── */}
      <UploadDocumentModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        entityType="Driver"
        entityId={drivers[0]?.id || '1'}
        onUploadSuccess={() => queryClient.invalidateQueries({ queryKey: ['documents'] })}
      />
    </DashboardLayout>
  );
}
