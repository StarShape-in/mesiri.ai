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
  fetchWorkersApi,
  type LabourAttendanceSummaryItem,
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
  const [loading, setLoading] = React.useState(true)

  // Dialog & Detail Sheet states
  const [addWorkerOpen, setAddWorkerOpen] = React.useState(false)
  const [selectedReportId, setSelectedReportId] = React.useState<string | null>(null)
  const [detailOpen, setDetailOpen] = React.useState(false)

  const loadData = React.useCallback(async () => {
    setLoading(true)
    try {
      const [reportsData, workersData] = await Promise.all([
        fetchAttendanceReportsApi({
          project_id: scope.mode === 'project' || scope.mode === 'site' ? scope.projectId : undefined,
          site_id: scope.mode === 'site' ? scope.siteId : undefined,
          limit: 100,
        }),
        fetchWorkersApi({ limit: 200 }),
      ])
      if (reportsData?.items) setReports(reportsData.items)
      if (workersData?.items) setWorkers(workersData.items)
    } catch (err) {
      console.warn('Failed to load Labour Overview data:', err)
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

  // Key Metrics
  const activeWorkersCount = workers.filter((w) => w.status === 'active').length
  const totalHeadcount = reports.reduce((acc, r) => acc + (r.total_headcount || 0), 0)
  const totalSpend = reports.reduce((acc, r) => acc + (r.total_cost || 0), 0)
  const whatsappCount = reports.filter((r) => r.recorded_via?.includes('whatsapp')).length
  const whatsappRate = reports.length > 0 ? Math.round((whatsappCount / reports.length) * 100) : 100

  // Trade Distribution Chart Data
  const tradeData = React.useMemo(() => {
    const counts: Record<string, number> = {}
    for (const w of workers) {
      const trade = w.trade || 'General Labor'
      counts[trade] = (counts[trade] || 0) + 1
    }
    return Object.entries(counts).map(([name, value]) => ({ name, value }))
  }, [workers])

  // Attendance Trend Chart Data
  const trendData = React.useMemo(() => {
    const map: Record<string, { date: string; headcount: number; cost: number }> = {}
    for (const r of reports) {
      const date = r.occurred_date || 'Today'
      if (!map[date]) {
        map[date] = { date, headcount: 0, cost: 0 }
      }
      map[date].headcount += r.total_headcount || 0
      map[date].cost += r.total_cost || 0
    }
    // Sort explicitly rather than relying on insertion order. `reports`
    // arrives occurred_date DESC, so Object.values() was newest-first and
    // `.slice(-7)` took the seven *oldest* days in the fetched window --
    // with 100 reports loaded, a chart captioned "Last 7 Days" could be
    // plotting three months ago, and today never appeared on it at all.
    // Take the seven most recent, then flip to chronological so the x-axis
    // reads left-to-right oldest-to-newest.
    return Object.values(map)
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, 7)
      .reverse()
  }, [reports])

  // Subcontractor Summary
  const contractorSummary = React.useMemo(() => {
    const map: Record<string, number> = {}
    for (const w of workers) {
      if (w.contractor) {
        map[w.contractor] = (map[w.contractor] || 0) + 1
      }
    }
    return Object.entries(map).map(([name, count]) => ({ name, count }))
  }, [workers])

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

      {/* Top 4 KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Active Workers Roster"
          value={<span className="text-emerald-600 dark:text-emerald-400">{activeWorkersCount} Personnel</span>}
          trend="up"
          trendValue="Master Roster"
          description="Registered site labor"
          icon={<UserCheck className="text-emerald-500" />}
          chartData={[15, 25, 35, 50, 65, 85]}
        />
        <KpiCard
          title="Cumulative Labor Spend"
          value={<span className="text-amber-600 dark:text-amber-400">₹{totalSpend.toLocaleString('en-IN')}</span>}
          trend="up"
          trendValue="Wage Cost"
          description="Logged daily wage cost"
          icon={<DollarSign className="text-amber-500" />}
        />
        <KpiCard
          title="Cumulative Man-Days"
          value={<span className="text-blue-600 dark:text-blue-400">{totalHeadcount} Man-Days</span>}
          trend="up"
          trendValue="Daily Attendance"
          description="Logged headcount"
          icon={<Users className="text-blue-500" />}
        />
        <KpiCard
          title="WhatsApp Automation Rate"
          value={<span className="text-purple-600 dark:text-purple-400">{whatsappRate}% Submissions</span>}
          trend="neutral"
          trendValue="AI Assistant"
          description={`${whatsappCount} Bot vs ${reports.length - whatsappCount} Web`}
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
              <h2 className="text-sm font-bold text-foreground">Trade Skill Distribution</h2>
            </div>
            <Link to="/labour/workers" className="text-xs text-amber-600 dark:text-amber-400 font-semibold hover:underline flex items-center">
              Roster <ChevronRight className="size-3 ml-0.5" />
            </Link>
          </div>

          <div className="h-64 w-full flex items-center justify-center relative">
            {loading ? (
              <div className="text-xs text-muted-foreground">Loading trade distribution...</div>
            ) : tradeData.length === 0 ? (
              <div className="text-xs text-muted-foreground">No registered trades found.</div>
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
                    formatter={(val: any) => [`${val} Workers`, 'Count']}
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
        </Card>

        {/* Right Card (5 cols): Subcontractor Agency Summary */}
        <Card className="lg:col-span-5 border shadow-2xs overflow-hidden bg-card p-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b pb-2 mb-3">
              <div className="flex items-center gap-2">
                <Building className="size-4 text-purple-500" />
                <h2 className="text-xs font-bold text-foreground">Subcontractor Agencies</h2>
              </div>
              <Badge variant="outline" className="text-[10px] font-mono">
                {contractorSummary.length} Agencies
              </Badge>
            </div>

            <div className="space-y-2">
              {contractorSummary.length === 0 ? (
                <div className="py-8 text-center text-xs text-muted-foreground">
                  No subcontractor agencies assigned to active workers.
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
                      <span className="font-semibold text-xs text-foreground">{agency.name}</span>
                    </div>

                    <Badge variant="outline" className="text-[10px] font-mono bg-background">
                      {agency.count} Workers
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
