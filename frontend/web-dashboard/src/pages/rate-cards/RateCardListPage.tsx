import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { 
  Plus, 
  Edit2, 
  FileText, 
  Download, 
  Trash2, 
  RotateCw, 
  Filter, 
  Search, 
  ArrowRight, 
  Building2, 
  MapPin, 
  CreditCard,
  LayoutGrid,
  List,
  MoreVertical,
  XCircle
} from 'lucide-react';

import DashboardLayout from '@/components/layout/DashboardLayout';
import DataTable from '@/components/ui/DataTable';
import KpiCard from '@/components/ui/KpiCard';
import { RouteCorridorKpi } from '@/components/ui/CustomKpiWidgets';
import { RevenueChart, CustomerBuilding, RouteLine, CheckBadge } from '@/components/ui/kpi-icons';
import { rateCardService, RateCard } from '@/services/rateCardService';
import { downloadCSV } from '@/utils/exportUtils';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select';
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

export default function RateCardListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedStatus, setSelectedStatus] = useState<string>('All');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [viewMode, setViewMode] = useState<'ledger' | 'grid'>('ledger');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showTariffModal, setShowTariffModal] = useState(false);

  const { data: response, isLoading, isError, error } = useQuery({
    queryKey: ['rate-cards'],
    queryFn: () => rateCardService.getAll(),
  });

  const rateCards = response?.data || [];

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await queryClient.invalidateQueries({ queryKey: ['rate-cards'] });
    setTimeout(() => setIsRefreshing(false), 500);
  };

  // Filtered rate cards
  const filteredData = useMemo(() => {
    return rateCards.filter((rc) => {
      const matchesSearch = 
        rc.name.toLowerCase().includes(search.toLowerCase()) || 
        (rc.customer?.name || '').toLowerCase().includes(search.toLowerCase()) ||
        rc.route_origin.toLowerCase().includes(search.toLowerCase()) ||
        rc.route_destination.toLowerCase().includes(search.toLowerCase());

      const matchesStatus = 
        statusFilter === 'all' ? true :
        statusFilter === 'active' ? rc.is_active : !rc.is_active;

      return matchesSearch && matchesStatus;
    });
  }, [rateCards, search, statusFilter]);

  // Calculated KPIs
  const kpis = useMemo(() => {
    const total = rateCards.length;
    const activeCount = rateCards.filter(rc => rc.is_active).length;
    const activePct = total > 0 ? Math.round((activeCount / total) * 100) : 0;

    const totalPrice = rateCards.reduce((acc, rc) => acc + (Number(rc.base_price) || 0), 0);
    const avgPrice = total > 0 ? Math.round(totalPrice / total) : 0;

    // Unique customers count
    const uniqueCustomers = new Set(rateCards.map(rc => rc.customerId).filter(Boolean)).size;

    // Top route lane
    const routeCounts: Record<string, number> = {};
    rateCards.forEach(rc => {
      const routeKey = `${rc.route_origin} → ${rc.route_destination}`;
      routeCounts[routeKey] = (routeCounts[routeKey] || 0) + 1;
    });
    let topRoute = 'Riyadh → Jeddah';
    let maxRouteCount = 0;
    Object.entries(routeCounts).forEach(([route, count]) => {
      if (count > maxRouteCount) {
        maxRouteCount = count;
        topRoute = route;
      }
    });

    const pricesArray = rateCards.map(rc => Number(rc.base_price) || 1200);

    return { total, activeCount, activePct, avgPrice, uniqueCustomers, topRoute, pricesArray };
  }, [rateCards]);

  const handleExportAll = () => {
    downloadCSV(filteredData, `rate_cards_${new Date().toISOString().slice(0, 10)}.csv`);
  };

  const handleDeleteRateCard = async (id: string) => {
    if (!confirm('Are you sure you want to delete this rate card?')) return;
    try {
      await rateCardService.delete(id);
      queryClient.invalidateQueries({ queryKey: ['rate-cards'] });
    } catch (e) {
      alert('Failed to delete rate card.');
    }
  };

  const columns = [
    {
      header: 'Rate Card ID',
      accessor: (row: RateCard) => (
        <span className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
          #{row.id.slice(0, 8).toUpperCase()}
        </span>
      ),
    },
    {
      header: 'Tariff Agreement',
      accessor: (row: RateCard) => (
        <div>
          <div className="font-extrabold text-slate-900 dark:text-slate-100 text-xs">{row.name}</div>
          <div className="text-[11px] text-slate-500 flex items-center gap-1 mt-0.5">
            <Building2 className="w-3 h-3 text-slate-400" /> {row.customer?.name || 'Standard Commercial Tariff'}
          </div>
        </div>
      ),
    },
    {
      header: 'Route Lane',
      accessor: (row: RateCard) => (
        <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300">
          <span>{row.route_origin}</span>
          <ArrowRight className="w-3.5 h-3.5 text-[#E8450F] shrink-0" />
          <span>{row.route_destination}</span>
        </div>
      ),
    },
    {
      header: 'Base Tariff Rate',
      accessor: (row: RateCard) => (
        <div className="font-mono text-xs font-extrabold text-slate-900 dark:text-slate-100">
          {row.currency || 'SAR'} {Number(row.base_price).toLocaleString()}
        </div>
      ),
    },
    {
      header: 'Status',
      accessor: (row: RateCard) => (
        <Badge 
          variant="outline" 
          className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 ${
            row.is_active 
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800' 
              : 'bg-slate-100 text-slate-500 border-slate-200 dark:bg-slate-800 dark:text-slate-400'
          }`}
        >
          {row.is_active ? 'Active' : 'Inactive'}
        </Badge>
      ),
    },
    {
      header: 'Actions',
      accessor: (row: RateCard) => (
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
              Rate Card Actions
            </DropdownMenuLabel>
            <DropdownMenuItem 
              onClick={() => navigate(`/rate-cards/${row.id}/edit`)}
              className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md"
            >
              <Edit2 className="w-3.5 h-3.5 mr-2 text-indigo-600" /> Edit Tariff Agreement
            </DropdownMenuItem>
            <DropdownMenuSeparator className="my-1 bg-slate-100 dark:bg-slate-800" />
            <DropdownMenuItem 
              onClick={() => handleDeleteRateCard(row.id)}
              className="cursor-pointer text-xs font-semibold py-1.5 px-2 rounded-md text-rose-600 focus:bg-rose-50"
            >
              <Trash2 className="w-3.5 h-3.5 mr-2 text-rose-600" /> Delete Tariff
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  const bulkActions = [
    {
      label: 'Export Selected',
      icon: <Download className="w-3.5 h-3.5" />,
      variant: 'secondary' as const,
      onClick: (selectedRows: RateCard[]) => {
        downloadCSV(selectedRows, 'selected_rate_cards.csv');
      }
    },
    {
      label: 'Delete Selected',
      icon: <Trash2 className="w-3.5 h-3.5" />,
      variant: 'danger' as const,
      onClick: async (selectedRows: RateCard[]) => {
        if (!confirm(`Are you sure you want to delete ${selectedRows.length} rate cards?`)) return;
        try {
          await rateCardService.bulkDelete(selectedRows.map(r => r.id));
          queryClient.invalidateQueries({ queryKey: ['rate-cards'] });
        } catch (e) { 
          alert('Failed to delete selected rate cards'); 
        }
      }
    }
  ];

  return (
    <DashboardLayout active="RateCards" title="Rate Cards">
      <div className="px-4 sm:px-6 pb-6 h-full flex flex-col animate-fade-in gap-5 max-w-[1400px] mx-auto w-full">
        
        {/* Page Content Header Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 shrink-0 pb-1">
          <div className="flex items-center gap-3">
            <FileText className="w-6 h-6 text-orange-500 dark:text-orange-400 shrink-0" />

            <div className="flex flex-col">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
                  Rate Cards
                </h1>
              </div>
              <p className="text-xs text-slate-500 font-medium">
                Commercial route tariffs, base rates, and contracted billing agreements
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportAll}
              className="h-9 gap-1.5 text-xs font-semibold border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
            >
              <Download className="w-3.5 h-3.5" /> Export CSV
            </Button>

            <Button 
              size="sm" 
              onClick={() => navigate('/rate-cards/new')}
              className="h-9 gap-1.5 text-xs bg-[#E8450F] hover:bg-[#d03d0c] text-white font-bold shadow-xs rounded-md px-4"
            >
              <Plus className="w-4 h-4" /> Create Rate Card
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="h-9 w-9 p-0 text-slate-600 border-slate-200 bg-white hover:bg-slate-50 shadow-2xs"
              title="Refresh Data"
            >
              <RotateCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* 4-Card Instrument Panel KPI Section */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 shrink-0">
          
          {/* Card 1: Active Rate Cards — Donut Ring Gauge */}
          <KpiCard
            title="ACTIVE TARIFF CARDS"
            value={kpis.activeCount}
            variant="emerald"
            trend="up"
            trendValue={`${kpis.activePct}% Active`}
            description="Active contracted tariffs"
            icon={CheckBadge}
            completionGauge={{
              percentage: kpis.activePct || 85,
              label: `${kpis.activePct}% Active Tariffs`,
              subtext: `${kpis.activeCount} Active • ${kpis.total - kpis.activeCount} Inactive`
            }}
            onClick={() => setSelectedStatus('Active')}
          />

          {/* Card 2: Avg Base Tariff Rate — Financial Sparkline */}
          <KpiCard
            title="AVERAGE BASE TARIFF"
            value={`SAR ${kpis.avgPrice.toLocaleString()}`}
            variant="brand"
            trend="up"
            trendValue="+4.2%"
            description="Tariff benchmark index"
            icon={RevenueChart}
            onClick={() => setShowTariffModal(true)}
          />

          {/* Card 3: Top Route Lane — Route Segment Bar */}
          <KpiCard
            title="PRIMARY ROUTE LANE"
            value={kpis.topRoute}
            variant="blue"
            trend="neutral"
            trendValue="High Volume"
            description="Riyadh transport corridor"
            icon={RouteLine}
            onClick={() => setSearch('Riyadh')}
          >
            <RouteCorridorKpi origin="Riyadh" destination="Jeddah" tripCount={42} />
          </KpiCard>

          {/* Card 4: Contracted Organizations — Donut Gauge */}
          <KpiCard
            title="CONTRACTED CLIENTS"
            value={kpis.uniqueCustomers}
            variant="amber"
            trend="neutral"
            trendValue="Corporate SLA"
            description="Active corporate accounts"
            icon={CustomerBuilding}
            completionGauge={{
              percentage: 90,
              label: '100% Contract Coverage',
              subtext: `${kpis.uniqueCustomers} Corporate Clients`
            }}
          />
        </div>

        {/* Toolbar & Control Bar Section (Strictly Horizontal) */}
        <div className="bg-white dark:bg-slate-900 rounded-xl p-2.5 shadow-2xs border border-slate-200 dark:border-slate-800 shrink-0">
          <div className="flex items-center justify-between gap-3 overflow-x-auto">
            
            {/* Left: Search Input + Status Dropdown */}
            <div className="flex items-center gap-3 shrink-0">
              
              {/* Search Bar */}
              <div className="relative w-64">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                <Input
                  placeholder="Search contract, customer, route..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="h-9 text-xs pl-8 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 focus-visible:ring-[#E8450F]/20 focus-visible:border-[#E8450F] rounded-lg font-medium"
                />
              </div>

              {/* Status Filter Dropdown */}
              <Select value={statusFilter} onValueChange={(val: any) => setStatusFilter(val)}>
                <SelectTrigger className="h-9 px-3 w-44 shrink-0 border-slate-200 bg-white rounded-lg text-xs font-semibold text-slate-800 shadow-2xs focus-visible:ring-[#E8450F]/20">
                  <div className="flex items-center gap-2">
                    <Filter className="h-3.5 w-3.5 text-indigo-600 shrink-0" />
                    <SelectValue placeholder="Tariff Status" />
                  </div>
                </SelectTrigger>
                <SelectContent align="start" className="w-48 p-1.5 shadow-lg border border-slate-200 bg-white rounded-xl">
                  <SelectGroup>
                    <SelectLabel className="text-[10px] font-bold tracking-wider uppercase text-slate-400 px-2 py-1">
                      Status Filter
                    </SelectLabel>
                    <SelectItem value="all" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md">All Statuses</SelectItem>
                    <SelectItem value="active" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-emerald-700">Active Only</SelectItem>
                    <SelectItem value="inactive" className="cursor-pointer text-xs font-medium py-1.5 px-2 rounded-md text-slate-500">Inactive Only</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>

            </div>

            {/* Right: Record Ledger Counter & View Switcher */}
            <div className="flex items-center gap-3 shrink-0 ml-auto">
              
              <div className="text-xs font-semibold text-slate-500">
                <span className="font-extrabold text-slate-900 dark:text-slate-100">{filteredData.length}</span> tariff agreements
              </div>

              {/* View Mode Segmented Control */}
              <div className="bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg flex items-center border border-slate-200 dark:border-slate-700">
                <button
                  onClick={() => setViewMode('ledger')}
                  className={`p-1.5 rounded-md text-xs font-bold transition-all flex items-center gap-1 ${
                    viewMode === 'ledger' 
                      ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-xs' 
                      : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                  }`}
                  title="Ledger Table View"
                >
                  <List className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setViewMode('grid')}
                  className={`p-1.5 rounded-md text-xs font-bold transition-all flex items-center gap-1 ${
                    viewMode === 'grid' 
                      ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 shadow-xs' 
                      : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-100'
                  }`}
                  title="Grid Card View"
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                </button>
              </div>

            </div>

          </div>
        </div>

        {/* Content Workspace: Ledger Table vs Grid Cards */}
        {viewMode === 'ledger' ? (
          <div className="flex-1 min-h-0 flex flex-col">
            <DataTable
              title={
                <span className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-orange-500" />
                  <span>Tariff & Rate Card Ledger</span>
                </span>
              }
              columns={columns}
              data={filteredData}
              bulkActions={bulkActions}
              enableSelection={true}
              isLoading={isLoading}
              isError={isError}
              errorMessage={(error as Error)?.message || 'Failed to load rate cards.'}
              searchPlaceholder="Search contract name, customer..."
              onSearchChange={setSearch}
              onRowClick={(row) => navigate(`/rate-cards/${row.id}`)}
            />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {isLoading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="bg-white rounded-xl border border-slate-100 p-4 h-[200px] skeleton"></div>
              ))
            ) : isError ? (
              <div className="col-span-full py-16 flex flex-col items-center justify-center">
                <div className="w-14 h-14 rounded-2xl bg-rose-50 flex items-center justify-center text-rose-500 mb-2">
                  <XCircle size={28} />
                </div>
                <p className="text-sm font-bold text-slate-900">Data Unavailable</p>
                <p className="text-xs text-slate-500 mt-1">{(error as Error)?.message || 'Failed to load rate cards.'}</p>
              </div>
            ) : filteredData.length === 0 ? (
              <div className="col-span-full py-16 flex flex-col items-center justify-center">
                <p className="text-sm font-bold text-slate-900">No Records Found</p>
                <p className="text-xs text-slate-500 mt-1">There are no rate cards matching your filters.</p>
              </div>
            ) : filteredData.map((rc) => (
              <Card 
                key={rc.id} 
                onClick={() => navigate(`/rate-cards/${rc.id}`)}
                className="border border-slate-200 dark:border-slate-800 shadow-2xs hover:shadow-xs hover:border-[#E8450F]/45 hover:-translate-y-0.5 transition-all duration-150 ease-in-out cursor-pointer bg-white dark:bg-slate-900 flex flex-col justify-between group rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-[#E8450F]/30"
                tabIndex={0}
                role="button"
                aria-label={`Rate card ${rc.name}, base tariff ${rc.currency || 'SAR'} ${rc.base_price}`}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    navigate(`/rate-cards/${rc.id}`);
                  }
                }}
              >
                <CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-indigo-600 dark:text-indigo-400 font-bold">
                      #{rc.id.slice(0, 8).toUpperCase()}
                    </span>
                    <Badge 
                      variant="outline" 
                      className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0 ${
                        rc.is_active 
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200' 
                          : 'bg-slate-100 text-slate-500 border-slate-200'
                      }`}
                    >
                      {rc.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                  <CardTitle className="text-sm font-extrabold text-slate-955 dark:text-slate-50 group-hover:text-[#E8450F] transition-colors mt-1">
                    {rc.name}
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500 flex items-center gap-1">
                    <Building2 className="w-3 h-3 text-slate-400" /> {rc.customer?.name || 'Standard Commercial Contract'}
                  </CardDescription>
                </CardHeader>

                <CardContent className="py-3 space-y-2">
                  <div className="bg-slate-50 dark:bg-slate-800/40 p-2.5 rounded-lg border border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-700 dark:text-slate-300">{rc.route_origin}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-[#E8450F]/70" />
                    <span className="font-bold text-slate-700 dark:text-slate-300">{rc.route_destination}</span>
                  </div>
                </CardContent>

                <CardFooter className="bg-slate-50 dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800 p-3 flex items-center justify-between text-xs rounded-b-xl">
                  <span className="text-[10px] text-slate-500 font-medium">Base Tariff Rate:</span>
                  <span className="font-mono font-extrabold text-slate-955 dark:text-slate-50">
                    {rc.currency || 'SAR'} {Number(rc.base_price).toLocaleString()}
                  </span>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}

        {/* Tariff Market Benchmark Modal */}
        <Dialog open={showTariffModal} onOpenChange={setShowTariffModal}>
          <DialogContent className="max-w-md rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6">
            <DialogHeader>
              <RevenueChart className="w-7 h-7 text-orange-500 dark:text-orange-400 mb-2" />
              <DialogTitle className="text-lg font-extrabold text-slate-900 dark:text-slate-100">
                Tariff Market Benchmark Summary
              </DialogTitle>
              <DialogDescription className="text-xs text-slate-500">
                Quarterly base price averages across Saudi freight transport corridors.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 my-4 text-xs">
              <div className="flex items-center justify-between p-3 rounded-xl bg-indigo-50/60 dark:bg-indigo-950/20 border border-indigo-200/60">
                <div>
                  <div className="font-bold text-indigo-900 dark:text-indigo-300">Average Freight Tariff</div>
                  <div className="text-[10px] text-indigo-700 dark:text-indigo-400">Mean base rate across active corridors</div>
                </div>
                <span className="font-mono font-extrabold text-indigo-700 dark:text-indigo-300 text-sm">SAR {kpis.avgPrice.toLocaleString()}</span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                <div>
                  <div className="font-bold text-slate-900 dark:text-slate-100">Active Rate Contracts</div>
                  <div className="text-[10px] text-slate-400">Total tariff agreements in effect</div>
                </div>
                <Badge className="bg-[#E8450F] text-white font-mono font-bold text-xs">{kpis.activeCount} Active</Badge>
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                size="sm"
                className="w-full text-xs font-bold border-slate-200"
                onClick={() => setShowTariffModal(false)}
              >
                Close Benchmark Summary
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

      </div>
    </DashboardLayout>
  );
}
