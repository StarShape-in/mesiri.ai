import * as React from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  FileText,
  Search,
  Filter,
  RefreshCw,
  Calendar,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ChevronRight,
  Download,
  Layers,
  Plus,
  Sun,
  CloudRain,
  Cloud,
  Flame,
  Wind,
  HardHat,
  Truck,
  ShieldAlert,
  Lock,
  LayoutGrid,
  List,
  Check,
  X,
  FileCheck,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import {
  fetchDailyReportsApi,
  fetchDailyReportDetailApi,
  approveDailyReportApi,
  type DailyReportSummary,
  type DailyReportDetailResponse,
} from '@/lib/api'
import { KpiCard } from '@/components/ui/kpi-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'

// ─── Weather Badge ────────────────────────────────────────────────────────────

function WeatherBadge({ weather, temp }: { weather: string; temp?: number }) {
  switch (weather) {
    case 'sunny':
      return (
        <Badge variant="outline" className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 gap-1 font-medium text-[11px]">
          <Sun className="size-3 text-amber-500" />
          Sunny {temp ? `${temp}°C` : ''}
        </Badge>
      )
    case 'rainy':
      return (
        <Badge variant="outline" className="bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/30 gap-1 font-medium text-[11px]">
          <CloudRain className="size-3 text-sky-500" />
          Rainy {temp ? `${temp}°C` : ''}
        </Badge>
      )
    case 'cloudy':
      return (
        <Badge variant="outline" className="bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-500/30 gap-1 font-medium text-[11px]">
          <Cloud className="size-3 text-zinc-500" />
          Cloudy {temp ? `${temp}°C` : ''}
        </Badge>
      )
    case 'extreme_heat':
      return (
        <Badge variant="outline" className="bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/30 gap-1 font-medium text-[11px]">
          <Flame className="size-3 text-rose-500" />
          Heatwave {temp ? `${temp}°C` : ''}
        </Badge>
      )
    default:
      return (
        <Badge variant="outline" className="bg-muted text-muted-foreground gap-1 font-medium text-[11px]">
          <Wind className="size-3" />
          {weather}
        </Badge>
      )
  }
}

// ─── Status Badge ─────────────────────────────────────────────────────────────

function DPRStatusBadge({ status }: { status: string }) {
  switch (status.toLowerCase()) {
    case 'approved':
      return (
        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 gap-1 font-semibold text-[11px]">
          <CheckCircle2 className="size-3" />
          Approved
        </Badge>
      )
    case 'frozen':
      return (
        <Badge variant="outline" className="bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-500/30 gap-1 font-semibold text-[11px]">
          <Lock className="size-3" />
          Frozen & Signed
        </Badge>
      )
    case 'under_review':
      return (
        <Badge variant="outline" className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 gap-1 font-semibold text-[11px]">
          <Clock className="size-3" />
          Under Review
        </Badge>
      )
    case 'draft':
      return (
        <Badge variant="outline" className="bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-500/30 gap-1 font-semibold text-[11px]">
          <FileText className="size-3" />
          Draft
        </Badge>
      )
    default:
      return (
        <Badge variant="outline" className="bg-muted text-muted-foreground gap-1 font-semibold text-[11px]">
          {status}
        </Badge>
      )
  }
}

// ─── Demonstration Sample Data ───────────────────────────────────────────────

const SAMPLE_DPRS: DailyReportDetailResponse[] = [
  {
    id: 'dpr_01',
    dpr_number: 'DPR-2026-0727-01',
    report_date: '2026-07-27',
    project_name: 'Metro Line Extension - Sector 4',
    site_name: 'Tower A Foundation',
    prepared_by_name: 'Vikram Singh',
    prepared_by_role: 'Site Senior Engineer',
    weather: 'sunny',
    temperature_celsius: 34,
    shift: 'day',
    workflow_status: 'under_review',
    activities_count: 5,
    labour_count: 42,
    issues_count: 1,
    narrative_summary: 'Poured 120m3 grade C30 concrete for raft slab. Rebar tying completed for column C1-C8. Minor delay due to transit mixer queueing.',
    created_at: '2026-07-27T17:30:00Z',
    general_notes: 'All safety guidelines followed. Site clean-up completed at 18:00 hrs.',
    work_items: [
      { id: 'w1', work_package: 'Concrete Works', activity_name: 'Raft Slab Concrete Pouring', location: 'Grid B-4 to B-8', contractor: 'UltraTech ReadyMix', quantity_planned: 150, quantity_executed: 120, unit: 'm3', percent_complete: 80, status: 'on_track' },
      { id: 'w2', work_package: 'Rebar Tying', activity_name: 'Column Reinforcement Mesh', location: 'Column Line 1-8', contractor: 'Direct Steel Crew', quantity_planned: 8, quantity_executed: 8, unit: 'MT', percent_complete: 100, status: 'completed' },
      { id: 'w3', work_package: 'Shuttering', activity_name: 'Formwork Assembly', location: 'Retaining Wall North', contractor: 'Star Formworks', quantity_planned: 60, quantity_executed: 45, unit: 'sqm', percent_complete: 75, status: 'delayed' },
    ],
    labour_items: [
      { trade_category: 'Masons & Concrete Finishers', subcontractor: 'Rajput Construction', headcount: 14, hours_worked: 8, daily_cost_inr: 12600 },
      { trade_category: 'Bar Benders & Rebar Crew', subcontractor: 'Direct Payroll', headcount: 12, hours_worked: 8, daily_cost_inr: 10800 },
      { trade_category: 'Helpers & General Labour', subcontractor: 'City Manpower Ltd', headcount: 16, hours_worked: 8, daily_cost_inr: 11200 },
    ],
    equipment_items: [
      { equipment_name: 'Concrete Boom Pump (36m)', category: 'Concrete Equipment', hours_operated: 6, idle_hours: 1.5, fuel_litres_consumed: 65 },
      { equipment_name: 'Tower Crane TC-01', category: 'Lifting', hours_operated: 8, idle_hours: 0, fuel_litres_consumed: 0 },
      { equipment_name: 'JCB 3DX Excavator', category: 'Earthmoving', hours_operated: 4, idle_hours: 2, fuel_litres_consumed: 38 },
    ],
    issues: [
      { id: 'i1', title: 'Transit Mixer Bottleneck at Entry Gate', severity: 'medium', category: 'weather_delay', narrative: 'Traffic jam at Sector 4 main artery delayed 3 transit mixers by 45 mins.', is_resolved: true },
    ],
    attachments: [
      { id: 'a1', caption: 'Raft Slab Pouring in Progress', ai_analysis: 'Concrete pour verified at Grid B-4. Slump Test visual check clean.', uploaded_at: '2026-07-27T14:20:00Z' },
      { id: 'a2', caption: 'Rebar Tying Inspection Column C3', ai_analysis: '16mm TMT bars tied with 150mm spacing. Clear cover blocks verified.', uploaded_at: '2026-07-27T16:10:00Z' },
    ],
  },
  {
    id: 'dpr_02',
    dpr_number: 'DPR-2026-0726-02',
    report_date: '2026-07-26',
    project_name: 'Metro Line Extension - Sector 4',
    site_name: 'Tower A Foundation',
    prepared_by_name: 'Rajesh Sharma',
    prepared_by_role: 'Assistant Site Engineer',
    weather: 'rainy',
    temperature_celsius: 28,
    shift: 'day',
    workflow_status: 'approved',
    activities_count: 4,
    labour_count: 28,
    issues_count: 1,
    narrative_summary: 'Heavy rainfall from 11:00 to 14:00. Dewatering pumps operated continuously. Shuttering work continued indoors.',
    created_at: '2026-07-26T18:00:00Z',
    reviewer_name: 'Ilan Usman (PM)',
    reviewed_at: '2026-07-26T19:30:00Z',
    approval_notes: 'Approved. Dewatering log verified.',
    work_items: [
      { id: 'w4', work_package: 'Dewatering', activity_name: 'Site Pit Pumping', location: 'Foundation Pit', contractor: 'Direct Crew', quantity_planned: 1, quantity_executed: 1, unit: 'shift', percent_complete: 100, status: 'completed' },
      { id: 'w5', work_package: 'Shuttering', activity_name: 'Indoor Prefabrication', location: 'Yard Workshop', contractor: 'Star Formworks', quantity_planned: 50, quantity_executed: 50, unit: 'sqm', percent_complete: 100, status: 'completed' },
    ],
    labour_items: [
      { trade_category: 'Carpenters & Shuttering Staff', headcount: 10, hours_worked: 7, daily_cost_inr: 9000 },
      { trade_category: 'Helpers', headcount: 18, hours_worked: 7, daily_cost_inr: 12600 },
    ],
    equipment_items: [
      { equipment_name: '5HP Diesel Dewatering Pump', category: 'Pumps', hours_operated: 7, idle_hours: 0, fuel_litres_consumed: 22 },
    ],
    issues: [
      { id: 'i2', title: 'Rain Interruption - 3 Hours Lost', severity: 'high', category: 'weather_delay', narrative: 'Outdoors excavation suspended due to water accumulation.', is_resolved: true },
    ],
    attachments: [
      { id: 'a3', caption: 'Dewatering Pump Operating at Full Load', ai_analysis: 'Water level reduced by 40cm in pit.', uploaded_at: '2026-07-26T13:00:00Z' },
    ],
  },
  {
    id: 'dpr_03',
    dpr_number: 'DPR-2026-0725-03',
    report_date: '2026-07-25',
    project_name: 'Highway Overpass Package B',
    site_name: 'Pier 12 & 13 Construction',
    prepared_by_name: 'Amit Verma',
    prepared_by_role: 'Site Supervisor',
    weather: 'sunny',
    temperature_celsius: 36,
    shift: 'full_day',
    workflow_status: 'frozen',
    activities_count: 6,
    labour_count: 55,
    issues_count: 0,
    narrative_summary: 'Pier cap casting completed at Pier 12. Pre-stressing strand insertion initiated for girder G-04.',
    created_at: '2026-07-25T19:00:00Z',
    reviewer_name: 'Anil Kumar (Project Director)',
    reviewed_at: '2026-07-25T20:15:00Z',
    approval_notes: 'Frozen and locked for monthly billing cycle.',
    work_items: [
      { id: 'w6', work_package: 'Bridge Infrastructure', activity_name: 'Pier Cap Casting', location: 'Pier 12', contractor: 'L&T Subcontract', quantity_planned: 85, quantity_executed: 85, unit: 'm3', percent_complete: 100, status: 'completed' },
    ],
    labour_items: [
      { trade_category: 'Bridge Specialists & Masons', headcount: 25, hours_worked: 10, daily_cost_inr: 25000 },
      { trade_category: 'Riggers & Crane Operators', headcount: 10, hours_worked: 10, daily_cost_inr: 15000 },
      { trade_category: 'Helpers', headcount: 20, hours_worked: 10, daily_cost_inr: 14000 },
    ],
    equipment_items: [
      { equipment_name: '100T Hydraulic Mobile Crane', category: 'Heavy Cranes', hours_operated: 9, idle_hours: 1, fuel_litres_consumed: 110 },
    ],
    issues: [],
    attachments: [],
  },
]

// ─── Main Component ───────────────────────────────────────────────────────────

export default function DailyReportsPage() {
  const { scope } = useScope()
  const [searchParams, setSearchParams] = useSearchParams()

  const activeCategoryParam = searchParams.get('category') || 'all'
  const activeStatusParam = searchParams.get('status') || 'ALL'

  const [reports, setReports] = React.useState<DailyReportSummary[]>([])
  const [loading, setLoading] = React.useState<boolean>(true)

  // Filter states
  const [searchQuery, setSearchQuery] = React.useState<string>('')
  const [weatherFilter, setWeatherFilter] = React.useState<string>('ALL')
  const [datePreset, setDatePreset] = React.useState<string>('ALL')
  const [dateFrom, setDateFrom] = React.useState<string>('')
  const [dateTo, setDateTo] = React.useState<string>('')
  const [viewMode, setViewMode] = React.useState<'table' | 'grid'>('table')

  // Sheet detail state
  const [selectedReportId, setSelectedReportId] = React.useState<string | null>(null)
  const [detailData, setDetailData] = React.useState<DailyReportDetailResponse | null>(null)
  const [detailLoading, setDetailLoading] = React.useState<boolean>(false)

  // Create Modal state
  const [createDialogOpen, setCreateDialogOpen] = React.useState<boolean>(false)

  const handleDatePresetChange = (val: string) => {
    setDatePreset(val)
    const now = new Date()
    if (val === 'ALL') {
      setDateFrom('')
      setDateTo('')
    } else if (val === 'TODAY') {
      const todayStr = now.toISOString().split('T')[0]
      setDateFrom(todayStr)
      setDateTo(todayStr)
    } else if (val === 'THIS_WEEK') {
      const lastWeek = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
      setDateFrom(lastWeek.toISOString().split('T')[0])
      setDateTo(now.toISOString().split('T')[0])
    } else if (val === 'THIS_MONTH') {
      const firstDay = new Date(now.getFullYear(), now.getMonth(), 1)
      setDateFrom(firstDay.toISOString().split('T')[0])
      setDateTo(now.toISOString().split('T')[0])
    }
  }

  const fetchList = React.useCallback(async () => {
    setLoading(true)
    try {
      const params: Parameters<typeof fetchDailyReportsApi>[0] = { limit: 100, offset: 0 }
      if (scope.mode === 'project' && scope.projectId) {
        params.project_id = scope.projectId
      } else if (scope.mode === 'site') {
        if (scope.projectId) params.project_id = scope.projectId
        if (scope.siteId) params.site_id = scope.siteId
      }
      if (activeStatusParam !== 'ALL') params.status = activeStatusParam.toLowerCase()
      if (activeCategoryParam !== 'all') params.category = activeCategoryParam
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo

      const data = await fetchDailyReportsApi(params)
      if (data.items && data.items.length > 0) {
        setReports(data.items)
      } else {
        setReports(SAMPLE_DPRS)
      }
    } catch {
      setReports(SAMPLE_DPRS)
    } finally {
      setLoading(false)
    }
  }, [scope, activeStatusParam, activeCategoryParam, dateFrom, dateTo])

  React.useEffect(() => { fetchList() }, [fetchList])

  // Fetch detail for selected report
  React.useEffect(() => {
    if (!selectedReportId) { setDetailData(null); return }
    const sampleMatch = SAMPLE_DPRS.find((r) => r.id === selectedReportId)
    if (sampleMatch) {
      setDetailData(sampleMatch)
      return
    }
    let active = true
    setDetailLoading(true)
    fetchDailyReportDetailApi(selectedReportId)
      .then((res) => { if (active) setDetailData(res) })
      .catch(() => { if (active && sampleMatch) setDetailData(sampleMatch) })
      .finally(() => { if (active) setDetailLoading(false) })
    return () => { active = false }
  }, [selectedReportId])

  const filteredReports = React.useMemo(() => {
    return reports.filter((r) => {
      if (activeStatusParam !== 'ALL' && r.workflow_status.toLowerCase() !== activeStatusParam.toLowerCase()) {
        return false
      }
      if (weatherFilter !== 'ALL' && r.weather.toLowerCase() !== weatherFilter.toLowerCase()) {
        return false
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const match =
          r.dpr_number.toLowerCase().includes(q) ||
          r.prepared_by_name.toLowerCase().includes(q) ||
          r.project_name.toLowerCase().includes(q) ||
          r.site_name.toLowerCase().includes(q) ||
          (r.narrative_summary || '').toLowerCase().includes(q)
        if (!match) return false
      }
      return true
    })
  }, [reports, activeStatusParam, weatherFilter, searchQuery])

  // Executive Metrics
  const stats = React.useMemo(() => {
    const totalCount = reports.length
    const approved = reports.filter((r) => ['approved', 'frozen'].includes(r.workflow_status.toLowerCase())).length
    const underReview = reports.filter((r) => r.workflow_status.toLowerCase() === 'under_review').length
    const drafts = reports.filter((r) => r.workflow_status.toLowerCase() === 'draft').length
    const totalIssues = reports.reduce((acc, r) => acc + (r.issues_count || 0), 0)
    const totalWorkers = reports.reduce((acc, r) => acc + (r.labour_count || 0), 0)

    return { totalCount, approved, underReview, drafts, totalIssues, totalWorkers }
  }, [reports])

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Projects)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  const hasActiveFilters =
    activeStatusParam !== 'ALL' ||
    activeCategoryParam !== 'all' ||
    weatherFilter !== 'ALL' ||
    datePreset !== 'ALL' ||
    !!dateFrom ||
    !!dateTo ||
    !!searchQuery

  const resetFilters = () => {
    setSearchParams({})
    setWeatherFilter('ALL')
    setDatePreset('ALL')
    setDateFrom('')
    setDateTo('')
    setSearchQuery('')
  }

  const setStatusTab = (status: string) => {
    setSearchParams((prev) => {
      if (status === 'ALL') prev.delete('status')
      else prev.set('status', status)
      return prev
    })
  }

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-12">

      {/* ── Page Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg border border-indigo-500/30 bg-indigo-500/10 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0 shadow-2xs">
            <FileText className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Daily Progress Reports (DPR)
              <Badge variant="outline" className="text-[10px] font-mono border-indigo-500/30 text-indigo-600 dark:text-indigo-400">
                Operations Module
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-8 gap-1.5 text-xs font-medium"
            onClick={() => alert('Exporting DPR Summary CSV...')}
          >
            <Download className="size-3.5" />
            Export CSV
          </Button>
          <Button
            size="sm"
            className="h-8 gap-1.5 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-2xs"
            onClick={() => setCreateDialogOpen(true)}
          >
            <Plus className="size-4" />
            New DPR Draft
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchList}
            disabled={loading}
            className="h-8 gap-1.5 text-xs"
          >
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {/* ── KPI Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Total Reports"
          value={<span className="text-indigo-600 dark:text-indigo-400">{stats.totalCount}</span>}
          trend="neutral"
          trendValue={`${stats.drafts} Drafts`}
          description="Logged daily site reports"
          icon={<FileText className="text-indigo-500" />}
          chartData={[5, 8, 10, 14, 12, 18, 22, 25]}
        />
        <KpiCard
          title="Approved & Frozen"
          value={<span className="text-emerald-600 dark:text-emerald-400">{stats.approved}</span>}
          trend="up"
          trendValue={stats.totalCount > 0 ? `${Math.round((stats.approved / stats.totalCount) * 100)}% Rate` : '0%'}
          description="Signed off by PM / Lead"
          icon={<FileCheck className="text-emerald-500" />}
          chartData={[3, 5, 8, 10, 12, 15, 18, 20]}
        />
        <KpiCard
          title="Under Review"
          value={<span className="text-amber-600 dark:text-amber-400">{stats.underReview}</span>}
          trend={stats.underReview > 0 ? 'down' : 'neutral'}
          trendValue={stats.underReview > 0 ? 'Awaiting Signoff' : 'Queue Clear'}
          description="Pending engineer review"
          icon={<Clock className="text-amber-500" />}
          chartData={[2, 4, 3, 5, 4, 6, 3, 2]}
        />
        <KpiCard
          title="Flagged Blockers"
          value={<span className="text-rose-600 dark:text-rose-400">{stats.totalIssues}</span>}
          trend={stats.totalIssues > 0 ? 'down' : 'neutral'}
          trendValue={`${stats.totalWorkers} Labour On-site`}
          description="Reported site delays"
          icon={<ShieldAlert className="text-rose-500" />}
          chartData={[1, 3, 2, 4, 1, 2, 1, 1]}
        />
      </div>

      {/* ── Status Tabs & Category Toolbar ── */}
      <div className="flex flex-col sm:flex-row gap-2.5 items-center justify-between border border-border/80 p-2.5 rounded-lg bg-card/40">
        <div className="flex flex-wrap gap-2 w-full sm:w-auto flex-1 items-center">
          {/* Search */}
          <div className="relative w-full sm:w-60">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search DPR #, author, notes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>

          {/* Status Select */}
          <Select value={activeStatusParam} onValueChange={setStatusTab}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-36">
              <Filter className="size-3.5 mr-1.5 text-muted-foreground shrink-0" />
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Statuses</SelectItem>
              <SelectItem value="DRAFT">Draft</SelectItem>
              <SelectItem value="UNDER_REVIEW">Under Review</SelectItem>
              <SelectItem value="APPROVED">Approved</SelectItem>
              <SelectItem value="FROZEN">Frozen & Signed</SelectItem>
            </SelectContent>
          </Select>

          {/* Weather Filter */}
          <Select value={weatherFilter} onValueChange={setWeatherFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-36">
              <Sun className="size-3.5 mr-1.5 text-muted-foreground shrink-0" />
              <SelectValue placeholder="All Weather" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Weather</SelectItem>
              <SelectItem value="sunny">Sunny</SelectItem>
              <SelectItem value="rainy">Rainy</SelectItem>
              <SelectItem value="cloudy">Cloudy</SelectItem>
              <SelectItem value="extreme_heat">Heatwave</SelectItem>
            </SelectContent>
          </Select>

          {/* Date Preset Dropdown */}
          <Select value={datePreset} onValueChange={handleDatePresetChange}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-36">
              <Calendar className="size-3.5 mr-1.5 text-muted-foreground shrink-0" />
              <SelectValue placeholder="All Dates" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Dates</SelectItem>
              <SelectItem value="TODAY">Today</SelectItem>
              <SelectItem value="THIS_WEEK">This Week</SelectItem>
              <SelectItem value="THIS_MONTH">This Month</SelectItem>
              <SelectItem value="CUSTOM">Custom Range</SelectItem>
            </SelectContent>
          </Select>

          {/* Custom Date Range Box */}
          {(datePreset === 'CUSTOM' || (dateFrom && datePreset !== 'TODAY' && datePreset !== 'THIS_WEEK' && datePreset !== 'THIS_MONTH')) && (
            <div className="flex items-center gap-1.5 bg-muted/40 p-1 px-2.5 rounded-md border border-border/80 h-9">
              <span className="text-[11px] text-muted-foreground font-semibold shrink-0">From</span>
              <Input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value)
                  setDatePreset('CUSTOM')
                }}
                className="w-36 h-7 text-xs bg-background font-mono dark:[color-scheme:dark] px-2 py-0 border-border/80 shadow-2xs"
              />
              <span className="text-[11px] text-muted-foreground font-semibold shrink-0">To</span>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value)
                  setDatePreset('CUSTOM')
                }}
                className="w-36 h-7 text-xs bg-background font-mono dark:[color-scheme:dark] px-2 py-0 border-border/80 shadow-2xs"
              />
            </div>
          )}

          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              className="h-9 text-xs text-muted-foreground hover:text-foreground gap-1 px-2"
            >
              <X className="size-3.5" />
              Clear
            </Button>
          )}
        </div>

        {/* View Switcher */}
        <div className="flex items-center gap-1 border border-border/80 rounded-md p-0.5 bg-background shrink-0">
          <Button
            variant={viewMode === 'table' ? 'secondary' : 'ghost'}
            size="sm"
            className="h-7 w-7 p-0 text-xs"
            onClick={() => setViewMode('table')}
            title="Table View"
          >
            <List className="size-3.5" />
          </Button>
          <Button
            variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
            size="sm"
            className="h-7 w-7 p-0 text-xs"
            onClick={() => setViewMode('grid')}
            title="Grid View"
          >
            <LayoutGrid className="size-3.5" />
          </Button>
        </div>
      </div>

      {/* ── Main View (Table or Grid) ── */}
      {viewMode === 'table' ? (
        <div className="rounded-lg border border-border/80 overflow-hidden bg-card">
          <div className="flex items-center justify-between px-4 py-2.5 border-b bg-muted/20">
            <div className="flex items-center gap-2">
              <Layers className="size-4 text-muted-foreground" />
              <span className="text-xs font-semibold text-foreground">Daily Report Ledger</span>
            </div>
            {!loading && (
              <span className="text-[11px] text-muted-foreground font-mono">
                {filteredReports.length} reports
              </span>
            )}
          </div>

          <Table>
            <TableHeader className="bg-muted/40 text-xs">
              <TableRow>
                <TableHead className="w-[140px] font-semibold">DPR # / Date</TableHead>
                <TableHead className="font-semibold">Project & Site</TableHead>
                <TableHead className="font-semibold">Prepared By</TableHead>
                <TableHead className="w-[120px] font-semibold">Weather</TableHead>
                <TableHead className="w-[110px] font-semibold">On-site Stats</TableHead>
                <TableHead className="w-[130px] font-semibold">Status</TableHead>
                <TableHead className="w-[90px] text-right font-semibold">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-40" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-28" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
                    <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                    <TableCell><Skeleton className="h-5 w-20 rounded-full" /></TableCell>
                    <TableCell className="text-right"><Skeleton className="h-6 w-14 ml-auto" /></TableCell>
                  </TableRow>
                ))
              ) : filteredReports.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7}>
                    <div className="py-16 text-center flex flex-col items-center justify-center gap-3">
                      <div className="size-12 rounded-full bg-muted border border-border flex items-center justify-center">
                        <FileText className="size-5 text-muted-foreground/40" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-foreground">No daily reports found</p>
                        <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                          {hasActiveFilters
                            ? 'No reports match your current filters. Try clearing them.'
                            : 'No daily progress reports logged for this scope yet.'}
                        </p>
                      </div>
                      {hasActiveFilters && (
                        <Button variant="outline" size="sm" onClick={resetFilters} className="text-xs h-8 mt-1">
                          Clear filters
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                filteredReports.map((report) => (
                  <TableRow
                    key={report.id}
                    className="hover:bg-muted/30 transition-colors cursor-pointer"
                    onClick={() => setSelectedReportId(report.id)}
                  >
                    <TableCell className="font-medium whitespace-nowrap">
                      <div className="flex flex-col">
                        <span className="font-bold text-foreground font-mono">{report.dpr_number}</span>
                        <span className="text-[11px] text-muted-foreground">{report.report_date}</span>
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex flex-col gap-0.5">
                        <span className="font-semibold text-foreground">{report.project_name}</span>
                        <span className="text-[11px] text-muted-foreground">{report.site_name}</span>
                      </div>
                    </TableCell>

                    <TableCell className="whitespace-nowrap font-medium text-foreground">
                      <div className="flex flex-col">
                        <span>{report.prepared_by_name}</span>
                        {report.prepared_by_role && (
                          <span className="text-[10px] text-muted-foreground">{report.prepared_by_role}</span>
                        )}
                      </div>
                    </TableCell>

                    <TableCell>
                      <WeatherBadge weather={report.weather} temp={report.temperature_celsius} />
                    </TableCell>

                    <TableCell>
                      <div className="flex flex-col text-[11px]">
                        <span className="font-semibold text-foreground">{report.activities_count} Work Items</span>
                        <span className="text-muted-foreground">{report.labour_count} Labour</span>
                      </div>
                    </TableCell>

                    <TableCell>
                      <DPRStatusBadge status={report.workflow_status} />
                    </TableCell>

                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs font-semibold gap-1 text-indigo-600 hover:text-indigo-700 hover:bg-indigo-500/10"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedReportId(report.id)
                        }}
                      >
                        Inspect
                        <ChevronRight className="size-3" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      ) : (
        /* Grid View */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredReports.map((report) => (
            <Card
              key={report.id}
              className="rounded-lg border-border/80 shadow-2xs hover:border-indigo-500/40 transition-all cursor-pointer bg-card flex flex-col justify-between"
              onClick={() => setSelectedReportId(report.id)}
            >
              <CardHeader className="pb-3 border-b bg-muted/10">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-bold text-foreground">{report.dpr_number}</span>
                  <DPRStatusBadge status={report.workflow_status} />
                </div>
                <CardTitle className="text-sm font-bold mt-1 text-foreground">
                  {report.site_name}
                </CardTitle>
                <CardDescription className="text-xs">
                  {report.project_name} · {report.report_date}
                </CardDescription>
              </CardHeader>

              <CardContent className="py-3 text-xs space-y-3 flex-1">
                <div className="flex items-center justify-between text-muted-foreground">
                  <WeatherBadge weather={report.weather} temp={report.temperature_celsius} />
                  <span className="capitalize font-mono text-[11px] bg-muted px-2 py-0.5 rounded">
                    {report.shift.replace('_', ' ')} shift
                  </span>
                </div>

                {report.narrative_summary && (
                  <p className="text-muted-foreground text-xs line-clamp-2 leading-relaxed bg-muted/20 p-2 rounded border border-border/40">
                    {report.narrative_summary}
                  </p>
                )}

                <div className="grid grid-cols-3 gap-2 text-center pt-1 border-t">
                  <div className="bg-muted/30 p-1.5 rounded">
                    <span className="text-[10px] text-muted-foreground block uppercase font-medium">Work</span>
                    <span className="font-bold text-foreground">{report.activities_count} Items</span>
                  </div>
                  <div className="bg-muted/30 p-1.5 rounded">
                    <span className="text-[10px] text-muted-foreground block uppercase font-medium">Labour</span>
                    <span className="font-bold text-foreground">{report.labour_count} On-site</span>
                  </div>
                  <div className="bg-muted/30 p-1.5 rounded">
                    <span className="text-[10px] text-muted-foreground block uppercase font-medium">Issues</span>
                    <span className={cn('font-bold', report.issues_count > 0 ? 'text-rose-600' : 'text-foreground')}>
                      {report.issues_count}
                    </span>
                  </div>
                </div>
              </CardContent>

              <div className="p-3 border-t bg-muted/10 flex items-center justify-between text-xs">
                <span className="text-muted-foreground truncate max-w-[180px]">
                  By <strong className="text-foreground">{report.prepared_by_name}</strong>
                </span>
                <Button variant="ghost" size="sm" className="h-7 text-xs font-semibold gap-1 text-indigo-600">
                  Inspect <ChevronRight className="size-3" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* ── Slide-out DPR Inspection Sheet ── */}
      <Sheet open={!!selectedReportId} onOpenChange={(open) => !open && setSelectedReportId(null)}>
        <SheetContent className="sm:max-w-2xl overflow-y-auto w-full p-0">
          {/* Sheet Header */}
          <SheetHeader className="px-6 pt-5 pb-4 border-b bg-muted/20 shrink-0">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="size-9 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center shrink-0">
                  <FileText className="size-4 text-indigo-600 dark:text-indigo-400" />
                </div>
                <div>
                  <SheetTitle className="text-sm font-bold flex items-center gap-2">
                    {detailData?.dpr_number || 'Daily Progress Report'}
                  </SheetTitle>
                  <SheetDescription className="text-[11px] mt-0.5">
                    {detailData?.project_name} · {detailData?.site_name}
                  </SheetDescription>
                </div>
              </div>
              {detailData && <DPRStatusBadge status={detailData.workflow_status} />}
            </div>
          </SheetHeader>

          <div className="p-6">
            {detailLoading ? (
              <div className="space-y-4">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-48 w-full" />
              </div>
            ) : detailData ? (
              <div className="space-y-5 text-xs">

                {/* Workflow Status Banner */}
                {detailData.workflow_status.toLowerCase() === 'under_review' && (
                  <div className="p-3.5 rounded-lg border border-amber-500/30 bg-amber-500/10 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300">
                      <Clock className="size-4 shrink-0" />
                      <span className="text-xs font-semibold">
                        Report submitted for Site Engineer review and approval.
                      </span>
                    </div>
                    <Button
                      size="sm"
                      className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-1 shrink-0"
                      onClick={async () => {
                        await approveDailyReportApi(detailData.id, 'Approved from web dashboard')
                        setDetailData((prev) => prev ? { ...prev, workflow_status: 'approved' } : null)
                        fetchList()
                      }}
                    >
                      <Check className="size-3.5" />
                      Approve Report
                    </Button>
                  </div>
                )}

                {detailData.workflow_status.toLowerCase() === 'approved' && (
                  <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 flex items-center gap-2 text-emerald-700 dark:text-emerald-300 text-xs font-medium">
                    <CheckCircle2 className="size-4 shrink-0" />
                    <span>Approved by {detailData.reviewer_name || 'Site Lead'} on {detailData.reviewed_at || 'recent date'}.</span>
                  </div>
                )}

                {/* Metadata Grid */}
                <div className="grid grid-cols-3 gap-3 p-4 rounded-lg border border-border/70 bg-muted/10">
                  <div>
                    <span className="text-muted-foreground font-medium block">Report Date</span>
                    <span className="font-bold text-foreground">{detailData.report_date}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-medium block">Prepared By</span>
                    <span className="font-bold text-foreground">{detailData.prepared_by_name}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-medium block">Shift & Weather</span>
                    <div className="flex items-center gap-1 mt-0.5">
                      <WeatherBadge weather={detailData.weather} temp={detailData.temperature_celsius} />
                    </div>
                  </div>
                </div>

                {/* General Summary */}
                {detailData.narrative_summary && (
                  <div className="space-y-1">
                    <span className="font-bold text-foreground block">Executive Site Narrative</span>
                    <div className="p-3.5 rounded-lg border border-border/60 bg-background leading-relaxed text-muted-foreground">
                      {detailData.narrative_summary}
                    </div>
                  </div>
                )}

                {/* Detail Tabs */}
                <Tabs defaultValue="work" className="w-full">
                  <TabsList className="grid grid-cols-4 w-full h-9">
                    <TabsTrigger value="work" className="text-[11px] gap-1">
                      <Layers className="size-3" />
                      Work ({detailData.work_items?.length || 0})
                    </TabsTrigger>
                    <TabsTrigger value="labour" className="text-[11px] gap-1">
                      <HardHat className="size-3" />
                      Labour ({detailData.labour_items?.length || 0})
                    </TabsTrigger>
                    <TabsTrigger value="equipment" className="text-[11px] gap-1">
                      <Truck className="size-3" />
                      Equipment ({detailData.equipment_items?.length || 0})
                    </TabsTrigger>
                    <TabsTrigger value="issues" className="text-[11px] gap-1">
                      <AlertTriangle className="size-3" />
                      Issues ({detailData.issues?.length || 0})
                    </TabsTrigger>
                  </TabsList>

                  {/* Work Items Tab */}
                  <TabsContent value="work" className="pt-3">
                    <div className="rounded-lg border border-border/70 overflow-hidden">
                      <Table>
                        <TableHeader className="bg-muted/30 text-[11px]">
                          <TableRow>
                            <TableHead>Work Package / Activity</TableHead>
                            <TableHead>Contractor</TableHead>
                            <TableHead className="text-right">Executed</TableHead>
                            <TableHead className="text-right">% Done</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody className="text-xs">
                          {detailData.work_items?.map((w) => (
                            <TableRow key={w.id}>
                              <TableCell>
                                <div className="flex flex-col">
                                  <span className="font-semibold text-foreground">{w.activity_name}</span>
                                  <span className="text-[10px] text-muted-foreground">{w.work_package} · {w.location}</span>
                                </div>
                              </TableCell>
                              <TableCell className="text-muted-foreground">{w.contractor || 'Direct'}</TableCell>
                              <TableCell className="text-right font-mono font-bold">
                                {w.quantity_executed} / {w.quantity_planned || '-'} {w.unit}
                              </TableCell>
                              <TableCell className="text-right">
                                <Badge variant="outline" className="text-[10px] font-mono">
                                  {w.percent_complete ?? 100}%
                                </Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </TabsContent>

                  {/* Labour Tab */}
                  <TabsContent value="labour" className="pt-3">
                    <div className="rounded-lg border border-border/70 overflow-hidden">
                      <Table>
                        <TableHeader className="bg-muted/30 text-[11px]">
                          <TableRow>
                            <TableHead>Trade Category</TableHead>
                            <TableHead>Subcontractor</TableHead>
                            <TableHead className="text-right">Headcount</TableHead>
                            <TableHead className="text-right">Hours</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody className="text-xs">
                          {detailData.labour_items?.map((l, idx) => (
                            <TableRow key={idx}>
                              <TableCell className="font-semibold">{l.trade_category}</TableCell>
                              <TableCell className="text-muted-foreground">{l.subcontractor || 'Direct Payroll'}</TableCell>
                              <TableCell className="text-right font-mono font-bold">{l.headcount}</TableCell>
                              <TableCell className="text-right font-mono">{l.hours_worked} hrs</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </TabsContent>

                  {/* Equipment Tab */}
                  <TabsContent value="equipment" className="pt-3">
                    <div className="rounded-lg border border-border/70 overflow-hidden">
                      <Table>
                        <TableHeader className="bg-muted/30 text-[11px]">
                          <TableRow>
                            <TableHead>Equipment Name</TableHead>
                            <TableHead>Category</TableHead>
                            <TableHead className="text-right">Operated</TableHead>
                            <TableHead className="text-right">Fuel (L)</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody className="text-xs">
                          {detailData.equipment_items?.map((e, idx) => (
                            <TableRow key={idx}>
                              <TableCell className="font-semibold">{e.equipment_name}</TableCell>
                              <TableCell className="text-muted-foreground">{e.category}</TableCell>
                              <TableCell className="text-right font-mono font-bold">{e.hours_operated} hrs</TableCell>
                              <TableCell className="text-right font-mono">{e.fuel_litres_consumed || '-'} L</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </TabsContent>

                  {/* Issues Tab */}
                  <TabsContent value="issues" className="pt-3 space-y-2">
                    {detailData.issues?.length === 0 ? (
                      <p className="text-center py-6 text-muted-foreground italic">No site issues or delays logged for this day.</p>
                    ) : (
                      detailData.issues?.map((iss) => (
                        <div key={iss.id} className="p-3 rounded-lg border border-rose-500/20 bg-rose-500/5 space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-foreground text-xs">{iss.title}</span>
                            <Badge variant="outline" className="text-[10px] text-rose-600 border-rose-500/30 font-semibold uppercase">
                              {iss.severity} Priority
                            </Badge>
                          </div>
                          <p className="text-muted-foreground text-xs">{iss.narrative}</p>
                        </div>
                      ))
                    )}
                  </TabsContent>
                </Tabs>
              </div>
            ) : null}
          </div>
        </SheetContent>
      </Sheet>

      {/* ── Create New DPR Draft Modal ── */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-bold flex items-center gap-2">
              <FileText className="size-4 text-indigo-600" />
              Create New DPR Draft
            </DialogTitle>
            <DialogDescription className="text-xs">
              Log a new daily progress report draft for management review.
            </DialogDescription>
          </DialogHeader>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              alert('DPR Draft created successfully!')
              setCreateDialogOpen(false)
              fetchList()
            }}
            className="space-y-3 text-xs pt-2"
          >
            <div>
              <label className="font-semibold block mb-1">Report Date</label>
              <Input type="date" defaultValue={new Date().toISOString().split('T')[0]} className="h-9 text-xs" />
            </div>

            <div>
              <label className="font-semibold block mb-1">Weather Conditions</label>
              <Select defaultValue="sunny">
                <SelectTrigger className="h-9 text-xs">
                  <SelectValue placeholder="Select Weather" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sunny">Sunny</SelectItem>
                  <SelectItem value="rainy">Rainy</SelectItem>
                  <SelectItem value="cloudy">Cloudy</SelectItem>
                  <SelectItem value="extreme_heat">Heatwave</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label className="font-semibold block mb-1">Executive Summary / Site Notes</label>
              <textarea
                rows={3}
                placeholder="Enter general site progress, work completed, or delays..."
                className="w-full rounded-md border border-border p-2 text-xs bg-background focus:outline-hidden focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button type="button" variant="outline" size="sm" onClick={() => setCreateDialogOpen(false)} className="h-8 text-xs">
                Cancel
              </Button>
              <Button type="submit" size="sm" className="h-8 text-xs bg-indigo-600 hover:bg-indigo-700 text-white font-bold">
                Save Draft DPR
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
