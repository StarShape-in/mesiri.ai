import * as React from 'react'
import {
  HardHat,
  Users,
  DollarSign,
  UserCheck,
  Bot,
  UserPlus,
  Zap,
  Building,
  Calendar,
  Eye,
  Globe,
  PieChart as PieChartIcon,
  BarChart3,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts'
import { Link } from 'react-router-dom'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  fetchAttendanceReportsApi,
  fetchLabourStatementApi,
  fetchWorkersApi,
  type LabourAttendanceSummaryItem,
  type LabourStatement,
  type WorkforceWorkerItem,
} from '@/lib/api'
import { AddWorkerDialog } from '@/components/workforce/add-worker-dialog'
import { AttendanceDetailSheet } from '@/components/workforce/attendance-detail-sheet'

const TRADE_COLORS = [
  '#f59e0b', // amber
  '#10b981', // emerald
  '#3b82f6', // blue
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#6366f1', // indigo
]

export default function LabourOverviewPage() {
  const { scope } = useScope()

  const [reports, setReports] = React.useState<LabourAttendanceSummaryItem[]>([])
  const [workers, setWorkers] = React.useState<WorkforceWorkerItem[]>([])
  // Backend-aggregated statements. These carry the whole organization's
  // attendance, not the page of reports fetched for the table below, so the
  // KPIs and charts are not silently capped at 100 reports the way they were.
  const [tradeStatement, setTradeStatement] = React.useState<LabourStatement | null>(null)
  const [contractorStatement, setContractorStatement] = React.useState<LabourStatement | null>(null)
  const [dailyStatement, setDailyStatement] = React.useState<LabourStatement | null>(null)
  const [loading, setLoading] = React.useState(true)
  // Surfaced, not swallowed: an empty dashboard and a failed request read
  // identically otherwise, which is how a backend outage gets reported as
  // "the numbers are all zero".
  const [error, setError] = React.useState<string | null>(null)

  // Dialog & Detail Sheet states
  const [addWorkerOpen, setAddWorkerOpen] = React.useState(false)
  const [selectedReportId, setSelectedReportId] = React.useState<string | null>(null)
  const [detailOpen, setDetailOpen] = React.useState(false)

  const loadData = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    const projectId = scope.mode === 'project' || scope.mode === 'site' ? scope.projectId : undefined
    const siteId = scope.mode === 'site' ? scope.siteId : undefined
    try {
      const [reportsData, workersData, trade, contractor, daily] = await Promise.all([
        fetchAttendanceReportsApi({ project_id: projectId, site_id: siteId, limit: 100 }),
        fetchWorkersApi({ limit: 200 }),
        // A failed statement must leave its widget empty rather than fall back
        // to the register, which would quietly restore the very substitution
        // this page was cleaned up to remove.
        fetchLabourStatementApi({
          report_type: 'trade_breakdown',
          project_id: projectId,
          site_id: siteId,
        }).catch(() => null),
        fetchLabourStatementApi({
          report_type: 'subcontractor_ledger',
          project_id: projectId,
          site_id: siteId,
        }).catch(() => null),
        fetchLabourStatementApi({
          report_type: 'daily_attendance',
          project_id: projectId,
          site_id: siteId,
        }).catch(() => null),
      ])
      if (reportsData?.items) setReports(reportsData.items)
      if (workersData?.items) setWorkers(workersData.items)
      setTradeStatement(trade)
      setContractorStatement(contractor)
      setDailyStatement(daily)
    } catch (err) {
      console.warn('Failed to load Labour Overview data:', err)
      setError('Could not load labour data. The figures below may be incomplete.')
    } finally {
      setLoading(false)
    }
  }, [scope])

  React.useEffect(() => {
    loadData()
  }, [loadData])

  // Scope label
  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Sites)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  // --- Key metrics ---------------------------------------------------------
  // Registered workers is a fact about the register and is labelled as such.
  // Everything else on this page comes from recorded attendance.
  const activeWorkersCount = workers.filter((w) => w.status === 'active').length
  const totalHeadcount = dailyStatement?.total_man_days ?? 0
  const totalSpend = dailyStatement?.total_cost ?? 0
  const unpricedManDays = dailyStatement?.unpriced_man_days ?? 0

  const whatsappCount = reports.filter((r) => r.recorded_via?.includes('whatsapp')).length
  // Null, not 100, when nothing has been recorded. A system with no reports at
  // all was previously claiming a perfect automation rate.
  const whatsappRate =
    reports.length > 0 ? Math.round((whatsappCount / reports.length) * 100) : null

  // Trade distribution, from attendance rather than the roster: this answers
  // "which trades actually worked", not "which trades are on file".
  const tradeData = React.useMemo(
    () =>
      (tradeStatement?.rows ?? [])
        .filter((row) => row.man_days > 0)
        .map((row) => ({ name: row.title, value: row.man_days })),
    [tradeStatement]
  )

  // Daily headcount, straight from the backend statement, so the seven days
  // shown are the seven most recent that exist -- not the seven most recent
  // within whatever page of reports the table happened to fetch.
  const trendData = React.useMemo(
    () =>
      (dailyStatement?.rows ?? [])
        .map((row) => ({
          date: row.first_date ?? row.title,
          headcount: row.man_days,
          cost: row.total_cost,
        }))
        .sort((a, b) => String(b.date).localeCompare(String(a.date)))
        .slice(0, 7)
        .reverse(),
    [dailyStatement]
  )

  const contractorSummary = React.useMemo(
    () =>
      (contractorStatement?.rows ?? []).map((row) => ({
        name: row.title,
        manDays: row.man_days,
        cost: row.total_cost,
      })),
    [contractorStatement]
  )

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg border border-amber-500/30 bg-amber-500/10 flex items-center justify-center text-amber-600 dark:text-amber-400 shrink-0 shadow-2xs">
            <HardHat className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Labour Command Center
              <Badge variant="outline" className="text-[10px] font-mono border-amber-500/30 text-amber-600 dark:text-amber-400">
                Workforce Module
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Link to="/labour/whatsapp">
            <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs font-semibold">
              <Zap className="size-3.5 text-amber-500" />
              WhatsApp Automations
            </Button>
          </Link>

          <Button
            size="sm"
            onClick={() => setAddWorkerOpen(true)}
            className="h-8 gap-1.5 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white shadow-2xs"
          >
            <UserPlus className="size-4" />
            Register Worker
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
          <AlertTriangle className="size-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Top 4 KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Active Workers (Register)"
          value={<span className="text-emerald-600 dark:text-emerald-400">{activeWorkersCount} Personnel</span>}
          description="Registered, not necessarily present"
          icon={<UserCheck className="text-emerald-500" />}
        />
        <KpiCard
          title="Recorded Labour Cost"
          value={<span className="text-amber-600 dark:text-amber-400">₹{totalSpend.toLocaleString('en-IN')}</span>}
          description={
            unpricedManDays > 0
              ? `Excludes ${unpricedManDays} man-days with no wage recorded`
              : 'From recorded attendance'
          }
          icon={<DollarSign className="text-amber-500" />}
        />
        <KpiCard
          title="Recorded Man-Days"
          value={<span className="text-blue-600 dark:text-blue-400">{totalHeadcount} Man-Days</span>}
          description="From recorded attendance"
          icon={<Users className="text-blue-500" />}
        />
        <KpiCard
          title="Reports via WhatsApp"
          value={
            <span className="text-purple-600 dark:text-purple-400">
              {whatsappRate === null ? '—' : `${whatsappRate}%`}
            </span>
          }
          description={
            reports.length === 0
              ? 'No attendance recorded yet'
              : `${whatsappCount} WhatsApp vs ${reports.length - whatsappCount} web`
          }
          icon={<Bot className="text-purple-500" />}
        />
      </div>

      {/* Visual Recharts Grid Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Card (7 cols): Headcount & Daily Cost Trend */}
        <Card className="lg:col-span-7 p-4 border shadow-2xs flex flex-col justify-between bg-card">
          <div className="flex items-center justify-between border-b pb-2 mb-3">
            <div className="flex items-center gap-2">
              <BarChart3 className="size-4 text-amber-500" />
              <h2 className="text-sm font-bold text-foreground">Daily Headcount & Labor Cost Trend</h2>
            </div>
            <Badge variant="outline" className="text-[10px] font-mono">
              Last 7 Days
            </Badge>
          </div>

          <div className="h-64 w-full">
            {loading ? (
              <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                Loading headcount trends...
              </div>
            ) : trendData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                No attendance trend data logged yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-muted/40" />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} className="text-[10px] text-muted-foreground" />
                  <YAxis tickLine={false} axisLine={false} className="text-[10px] text-muted-foreground" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--card)',
                      borderColor: 'var(--border)',
                      borderRadius: '8px',
                      fontSize: '11px',
                    }}
                    formatter={(value: any, name: any) => [
                      name === 'headcount' ? `${value} Workers` : `₹${Number(value).toLocaleString('en-IN')}`,
                      name === 'headcount' ? 'Headcount' : 'Cost',
                    ]}
                  />
                  <Bar dataKey="headcount" fill="#f59e0b" radius={[4, 4, 0, 0]} maxBarSize={40} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        {/* Right Card (5 cols): Trade Skill Distribution Donut Chart */}
        <Card className="lg:col-span-5 p-4 border shadow-2xs flex flex-col justify-between bg-card">
          <div className="flex items-center justify-between border-b pb-2 mb-3">
            <div className="flex items-center gap-2">
              <PieChartIcon className="size-4 text-purple-500" />
              <h2 className="text-sm font-bold text-foreground">Man-Days by Trade</h2>
              <Badge variant="outline" className="text-[9px] font-mono">
                From attendance
              </Badge>
            </div>
            <Link to="/labour/workers" className="text-xs text-amber-600 dark:text-amber-400 font-semibold hover:underline flex items-center">
              Roster <ChevronRight className="size-3 ml-0.5" />
            </Link>
          </div>

          <div className="h-64 w-full flex items-center justify-center relative">
            {loading ? (
              <div className="text-xs text-muted-foreground">Loading trade distribution...</div>
            ) : tradeData.length === 0 ? (
              <div className="text-xs text-muted-foreground">
                No attendance recorded yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={tradeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {tradeData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={TRADE_COLORS[index % TRADE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--card)',
                      borderColor: 'var(--border)',
                      borderRadius: '8px',
                      fontSize: '11px',
                    }}
                    formatter={(val: any) => [`${val} man-days`, 'Recorded']}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="flex flex-wrap gap-2 justify-center pt-2 border-t text-[11px]">
            {tradeData.map((entry, idx) => (
              <div key={entry.name} className="flex items-center gap-1.5">
                <span
                  className="size-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: TRADE_COLORS[idx % TRADE_COLORS.length] }}
                />
                <span className="text-muted-foreground font-medium">{entry.name}:</span>
                <span className="font-bold text-foreground">{entry.value}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Activity Stream & Subcontractor Grid Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Card (7 cols): Recent Attendance Stream */}
        <Card className="lg:col-span-7 border shadow-2xs overflow-hidden bg-card">
          <div className="p-3 border-b flex items-center justify-between bg-muted/20">
            <div className="flex items-center gap-2">
              <Calendar className="size-4 text-amber-500" />
              <h2 className="text-xs font-bold text-foreground">Recent Site Attendance Logs</h2>
            </div>
            <Link to="/labour/attendance" className="text-xs text-amber-600 dark:text-amber-400 font-semibold hover:underline flex items-center">
              View All Logs <ChevronRight className="size-3 ml-0.5" />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <Table>
              <TableHeader className="bg-muted/40">
                <TableRow className="hover:bg-transparent border-b">
                  <TableHead className="text-xs font-semibold h-9">Date</TableHead>
                  <TableHead className="text-xs font-semibold h-9">Recorded Via</TableHead>
                  <TableHead className="text-xs font-semibold h-9 text-center">Headcount</TableHead>
                  <TableHead className="text-xs font-semibold h-9 text-right">Daily Cost</TableHead>
                  <TableHead className="text-xs font-semibold h-9 w-10 text-right">View</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-28 text-center text-xs text-muted-foreground">
                      Loading recent attendance logs...
                    </TableCell>
                  </TableRow>
                ) : reports.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-28 text-center text-xs text-muted-foreground">
                      No recent attendance logs recorded.
                    </TableCell>
                  </TableRow>
                ) : (
                  reports.slice(0, 5).map((item) => (
                    <TableRow
                      key={item.id}
                      onClick={() => {
                        setSelectedReportId(item.id)
                        setDetailOpen(true)
                      }}
                      className="hover:bg-muted/30 transition-colors cursor-pointer"
                    >
                      <TableCell className="font-semibold text-xs py-2.5 text-foreground">
                        {item.occurred_date}
                      </TableCell>

                      <TableCell className="text-xs py-2.5">
                        <Badge
                          variant="outline"
                          className={
                            item.recorded_via?.includes('whatsapp')
                              ? 'border-emerald-500/30 text-emerald-600 bg-emerald-500/10 text-[10px]'
                              : 'border-blue-500/30 text-blue-600 bg-blue-500/10 text-[10px]'
                          }
                        >
                          {item.recorded_via?.includes('whatsapp') ? (
                            <span className="flex items-center gap-1">
                              <Bot className="size-3" /> WhatsApp Bot
                            </span>
                          ) : (
                            <span className="flex items-center gap-1">
                              <Globe className="size-3" /> Web
                            </span>
                          )}
                        </Badge>
                      </TableCell>

                      <TableCell className="text-xs py-2.5 text-center font-bold text-foreground">
                        {item.total_headcount} Workers
                      </TableCell>

                      <TableCell className="text-xs py-2.5 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                        ₹{item.total_cost ? item.total_cost.toLocaleString('en-IN') : '0'}
                      </TableCell>

                      <TableCell className="text-xs py-2.5 text-right">
                        <Button variant="ghost" size="icon" className="size-6">
                          <Eye className="size-3.5 text-muted-foreground" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </Card>

        {/* Right Card (5 cols): Subcontractor Agency Summary */}
        <Card className="lg:col-span-5 border shadow-2xs overflow-hidden bg-card p-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b pb-2 mb-3">
              <div className="flex items-center gap-2">
                <Building className="size-4 text-purple-500" />
                <h2 className="text-xs font-bold text-foreground">Contractors by Man-Days</h2>
                <Badge variant="outline" className="text-[9px] font-mono">
                  From attendance
                </Badge>
              </div>
              <Badge variant="outline" className="text-[10px] font-mono">
                {contractorSummary.length} Contractors
              </Badge>
            </div>

            <div className="space-y-2">
              {contractorSummary.length === 0 ? (
                <div className="py-8 text-center text-xs text-muted-foreground">
                  No attendance recorded against a contractor yet.
                </div>
              ) : (
                contractorSummary.map((agency) => (
                  <div
                    key={agency.name}
                    className="flex items-center justify-between p-2.5 rounded-lg border bg-muted/20 hover:bg-muted/40 transition-colors"
                  >
                    <div className="flex items-center gap-2.5">
                      <div className="size-7 rounded-md bg-purple-500/10 border border-purple-500/20 text-purple-600 dark:text-purple-400 flex items-center justify-center font-bold text-xs">
                        <Building className="size-3.5" />
                      </div>
                      <div className="flex flex-col">
                        <span className="font-semibold text-xs text-foreground">{agency.name}</span>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          ₹{agency.cost.toLocaleString('en-IN')}
                        </span>
                      </div>
                    </div>

                    <Badge variant="outline" className="text-[10px] font-mono bg-background">
                      {agency.manDays} man-days
                    </Badge>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="pt-3 border-t text-center">
            <Link to="/labour/workers">
              <Button variant="ghost" size="sm" className="w-full text-xs font-semibold gap-1 text-amber-600 dark:text-amber-400">
                Manage Master Roster & Contractors <ChevronRight className="size-3.5" />
              </Button>
            </Link>
          </div>
        </Card>
      </div>

      {/* Modals */}
      <AddWorkerDialog open={addWorkerOpen} onOpenChange={setAddWorkerOpen} onSuccess={loadData} />
      <AttendanceDetailSheet reportId={selectedReportId} open={detailOpen} onOpenChange={setDetailOpen} />
    </div>
  )
}
