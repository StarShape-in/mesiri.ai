import * as React from 'react'
import {
  BarChart3,
  Building,
  Calendar,
  DollarSign,
  HardHat,
  RefreshCw,
  Users,
  AlertTriangle,
  PieChart as PieChartIcon,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { toLocalISODate } from '@/lib/utils'
import { fetchLabourStatementApi, type LabourStatement } from '@/lib/api'

const TRADE_COLORS = [
  '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899', '#06b6d4', '#6366f1',
]

type RangePreset = 'ALL' | 'TODAY' | 'THIS_WEEK' | 'THIS_MONTH'

/** Resolved against the browser's local date, matching the Attendance and
 *  Reports screens so the three never disagree about which day "today" is. */
function resolveRange(preset: RangePreset): { date_from?: string; date_to?: string } {
  const now = new Date()
  if (preset === 'TODAY') {
    const d = toLocalISODate(now)
    return { date_from: d, date_to: d }
  }
  if (preset === 'THIS_WEEK') {
    const from = new Date(now.getTime() - 6 * 24 * 60 * 60 * 1000)
    return { date_from: toLocalISODate(from), date_to: toLocalISODate(now) }
  }
  if (preset === 'THIS_MONTH') {
    const first = new Date(now.getFullYear(), now.getMonth(), 1)
    return { date_from: toLocalISODate(first), date_to: toLocalISODate(now) }
  }
  return {}
}

/** Days between two ISO dates, inclusive. Used only to express reporting
 *  coverage as a fraction of the range actually asked for. */
function inclusiveDays(from?: string, to?: string): number | null {
  if (!from || !to) return null
  const a = new Date(`${from}T00:00:00`).getTime()
  const b = new Date(`${to}T00:00:00`).getTime()
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return null
  return Math.floor((b - a) / 86_400_000) + 1
}

function fmtManDays(value: number): string {
  // Man-days are fractional now (a half day is 0.5), so a whole number should
  // still read as a whole number rather than "17.0".
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export default function LabourAnalyticsPage() {
  const { scope } = useScope()
  const [preset, setPreset] = React.useState<RangePreset>('THIS_MONTH')
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const [daily, setDaily] = React.useState<LabourStatement | null>(null)
  const [trades, setTrades] = React.useState<LabourStatement | null>(null)
  const [contractors, setContractors] = React.useState<LabourStatement | null>(null)
  const [workers, setWorkers] = React.useState<LabourStatement | null>(null)
  const [today, setToday] = React.useState<LabourStatement | null>(null)

  const range = React.useMemo(() => resolveRange(preset), [preset])

  const load = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    const projectId =
      scope.mode === 'project' || scope.mode === 'site' ? scope.projectId : undefined
    const siteId = scope.mode === 'site' ? scope.siteId : undefined
    const common = { project_id: projectId, site_id: siteId, ...range }
    const todayIso = toLocalISODate(new Date())

    try {
      const [d, t, c, w, td] = await Promise.all([
        fetchLabourStatementApi({ report_type: 'daily_attendance', ...common }),
        fetchLabourStatementApi({ report_type: 'trade_breakdown', ...common }),
        fetchLabourStatementApi({ report_type: 'subcontractor_ledger', ...common }),
        fetchLabourStatementApi({ report_type: 'worker_wages', ...common }),
        // Always today, regardless of the range filter -- "present today" is a
        // fixed question and must not silently mean "present this month".
        fetchLabourStatementApi({
          report_type: 'daily_attendance',
          project_id: projectId,
          site_id: siteId,
          date_from: todayIso,
          date_to: todayIso,
        }),
      ])
      setDaily(d); setTrades(t); setContractors(c); setWorkers(w); setToday(td)
    } catch (err) {
      console.warn('Failed to load labour analytics:', err)
      // An empty chart and a failed request are different claims.
      setError('Could not load analytics. The figures below may be incomplete or missing.')
      setDaily(null); setTrades(null); setContractors(null); setWorkers(null); setToday(null)
    } finally {
      setLoading(false)
    }
  }, [scope, range])

  React.useEffect(() => { load() }, [load])

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio (all projects)'
    if (scope.mode === 'project') return `Project: ${scope.projectName}`
    return `Site: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  // --- Derived, all from recorded attendance -------------------------------

  const trendData = React.useMemo(
    () =>
      (daily?.rows ?? [])
        .map((r) => ({ date: r.first_date ?? r.title, manDays: r.man_days, cost: r.total_cost }))
        .sort((a, b) => String(a.date).localeCompare(String(b.date))),
    [daily]
  )

  const tradeData = React.useMemo(
    () =>
      (trades?.rows ?? [])
        .filter((r) => r.man_days > 0)
        .map((r) => ({ name: r.title, value: r.man_days })),
    [trades]
  )

  const presentToday = today?.total_man_days ?? 0
  const daysReported = daily?.rows.length ?? 0
  const rangeDays = inclusiveDays(daily?.date_from ?? undefined, daily?.date_to ?? undefined)
  // Reporting coverage, not worker attendance rate: it answers "did the site
  // report every day?", which is derivable from attendance alone. A true
  // attendance rate would need an expected roster per day, which nothing
  // records -- inventing one is exactly what this module removed.
  const coverage = rangeDays && rangeDays > 0
    ? Math.min(100, Math.round((daysReported / rangeDays) * 100))
    : null

  const workerRows = workers?.rows ?? []
  const contractorRows = contractors?.rows ?? []
  const unpriced = daily?.unpriced_man_days ?? 0

  const empty = !loading && !error && daysReported === 0

  return (
    <div className="flex flex-col gap-4 w-full max-w-full pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg border border-amber-500/30 bg-amber-500/10 flex items-center justify-center text-amber-600 dark:text-amber-400 shrink-0">
            <BarChart3 className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Labour Analytics
              <Badge variant="outline" className="text-[10px] font-mono border-amber-500/30 text-amber-600 dark:text-amber-400">
                From attendance
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Select value={preset} onValueChange={(v) => setPreset(v as RangePreset)}>
            <SelectTrigger className="h-9 text-xs w-40">
              <Calendar className="size-3.5 mr-1 text-amber-500" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Time</SelectItem>
              <SelectItem value="TODAY">Today</SelectItem>
              <SelectItem value="THIS_WEEK">This Week</SelectItem>
              <SelectItem value="THIS_MONTH">This Month</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="ghost" size="sm" onClick={load} disabled={loading} className="h-9 text-xs gap-1">
            <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
          <AlertTriangle className="size-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Present Today"
          value={
            <span className="text-emerald-600 dark:text-emerald-400">
              {fmtManDays(presentToday)} Man-Days
            </span>
          }
          description={presentToday === 0 ? 'Nothing recorded for today yet' : 'Recorded today'}
          icon={<Users className="text-emerald-500" />}
        />
        <KpiCard
          title="Labour Cost"
          value={
            <span className="text-amber-600 dark:text-amber-400">
              ₹{(daily?.total_cost ?? 0).toLocaleString('en-IN')}
            </span>
          }
          description={
            unpriced > 0
              ? `Excludes ${fmtManDays(unpriced)} man-days with no wage recorded`
              : 'In selected range'
          }
          icon={<DollarSign className="text-amber-500" />}
        />
        <KpiCard
          title="Contractors"
          value={
            <span className="text-purple-600 dark:text-purple-400">{contractorRows.length}</span>
          }
          description="With recorded attendance"
          icon={<Building className="text-purple-500" />}
        />
        <KpiCard
          title="Reporting Coverage"
          value={
            <span className="text-blue-600 dark:text-blue-400">
              {coverage === null ? '—' : `${coverage}%`}
            </span>
          }
          description={
            coverage === null
              ? `${daysReported} day(s) reported`
              : `${daysReported} of ${rangeDays} days reported`
          }
          icon={<Calendar className="text-blue-500" />}
        />
      </div>

      {empty && (
        <div className="border rounded-lg bg-card p-8 text-center text-sm text-muted-foreground">
          No attendance recorded for this scope and date range.
        </div>
      )}

      {/* Trend + trade split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <Card className="lg:col-span-7 p-4 border flex flex-col">
          <div className="flex items-center justify-between border-b pb-2 mb-3">
            <div className="flex items-center gap-2">
              <BarChart3 className="size-4 text-amber-500" />
              <h2 className="text-sm font-bold text-foreground">Daily Man-Days</h2>
            </div>
            <Badge variant="outline" className="text-[10px] font-mono">
              {daysReported} day{daysReported === 1 ? '' : 's'}
            </Badge>
          </div>
          <div className="h-64 w-full">
            {loading ? (
              <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                Loading trend...
              </div>
            ) : trendData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                No attendance in this range.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-muted/40" />
                  <XAxis dataKey="date" tickLine={false} axisLine={false} className="text-[10px]" />
                  <YAxis tickLine={false} axisLine={false} className="text-[10px]" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--card)',
                      borderColor: 'var(--border)',
                      borderRadius: '8px',
                      fontSize: '11px',
                    }}
                    formatter={(v: any, n: any) => [
                      n === 'manDays' ? `${fmtManDays(Number(v))} man-days` : `₹${Number(v).toLocaleString('en-IN')}`,
                      n === 'manDays' ? 'Man-days' : 'Cost',
                    ]}
                  />
                  <Bar dataKey="manDays" fill="#f59e0b" radius={[4, 4, 0, 0]} maxBarSize={40} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        <Card className="lg:col-span-5 p-4 border flex flex-col">
          <div className="flex items-center justify-between border-b pb-2 mb-3">
            <div className="flex items-center gap-2">
              <PieChartIcon className="size-4 text-purple-500" />
              <h2 className="text-sm font-bold text-foreground">Man-Days by Trade</h2>
            </div>
          </div>
          <div className="h-64 w-full flex items-center justify-center">
            {loading ? (
              <div className="text-xs text-muted-foreground">Loading trades...</div>
            ) : tradeData.length === 0 ? (
              <div className="text-xs text-muted-foreground">No attendance in this range.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={tradeData} cx="50%" cy="50%" innerRadius={55} outerRadius={80} paddingAngle={3} dataKey="value">
                    {tradeData.map((_, i) => (
                      <Cell key={i} fill={TRADE_COLORS[i % TRADE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'var(--card)',
                      borderColor: 'var(--border)',
                      borderRadius: '8px',
                      fontSize: '11px',
                    }}
                    formatter={(v: any) => [`${fmtManDays(Number(v))} man-days`, 'Recorded']}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="flex flex-wrap gap-2 justify-center pt-2 border-t text-[11px]">
            {tradeData.slice(0, 7).map((e, i) => (
              <div key={e.name} className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-full" style={{ backgroundColor: TRADE_COLORS[i % TRADE_COLORS.length] }} />
                <span className="text-muted-foreground">{e.name}:</span>
                <span className="font-bold text-foreground">{fmtManDays(e.value)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Contractor workforce */}
      <Card className="border overflow-hidden">
        <div className="p-3 border-b flex items-center justify-between bg-muted/20">
          <div className="flex items-center gap-2">
            <Building className="size-4 text-purple-500" />
            <h2 className="text-xs font-bold text-foreground">Contractor Workforce</h2>
          </div>
          <Badge variant="outline" className="text-[10px] font-mono">From attendance</Badge>
        </div>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow className="hover:bg-transparent border-b">
                <TableHead className="text-xs font-semibold h-9">Contractor</TableHead>
                <TableHead className="text-xs font-semibold h-9 text-center">Man-Days</TableHead>
                <TableHead className="text-xs font-semibold h-9 text-center">Days Active</TableHead>
                <TableHead className="text-xs font-semibold h-9 text-right">Avg Rate (₹/day)</TableHead>
                <TableHead className="text-xs font-semibold h-9 text-right">Cost (₹)</TableHead>
                <TableHead className="text-xs font-semibold h-9 text-right w-24">% of Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-xs text-muted-foreground">
                    Loading contractors...
                  </TableCell>
                </TableRow>
              ) : contractorRows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center text-xs text-muted-foreground">
                    No attendance recorded against a contractor in this range.
                  </TableCell>
                </TableRow>
              ) : (
                contractorRows.map((r) => (
                  <TableRow key={r.id} className="hover:bg-muted/30">
                    <TableCell className="text-xs py-2.5 font-semibold text-foreground">{r.title}</TableCell>
                    <TableCell className="text-xs py-2.5 text-center">
                      {fmtManDays(r.man_days)}
                      {r.priced_man_days < r.man_days && (
                        <span className="block text-[10px] text-amber-600 dark:text-amber-400">
                          {fmtManDays(r.man_days - r.priced_man_days)} unpriced
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs py-2.5 text-center">{r.days_worked}</TableCell>
                    <TableCell className="text-xs py-2.5 text-right font-mono">
                      {r.priced_man_days > 0 ? `₹${r.avg_daily_wage.toLocaleString('en-IN')}` : '—'}
                    </TableCell>
                    <TableCell className="text-xs py-2.5 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                      ₹{r.total_cost.toLocaleString('en-IN')}
                    </TableCell>
                    <TableCell className="text-xs py-2.5 text-right font-mono">{r.percentage}%</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </Card>

      {/* Most active workers */}
      <Card className="border overflow-hidden">
        <div className="p-3 border-b flex items-center justify-between bg-muted/20">
          <div className="flex items-center gap-2">
            <HardHat className="size-4 text-amber-500" />
            <h2 className="text-xs font-bold text-foreground">Most Active Workers</h2>
          </div>
          <Badge variant="outline" className="text-[10px] font-mono">
            Excludes unnamed groups
          </Badge>
        </div>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow className="hover:bg-transparent border-b">
                <TableHead className="text-xs font-semibold h-9">Worker</TableHead>
                <TableHead className="text-xs font-semibold h-9">Trade</TableHead>
                <TableHead className="text-xs font-semibold h-9 text-center">Days Worked</TableHead>
                <TableHead className="text-xs font-semibold h-9 text-right">Earnings (₹)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center text-xs text-muted-foreground">
                    Loading workers...
                  </TableCell>
                </TableRow>
              ) : workerRows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center text-xs text-muted-foreground">
                    No named workers recorded in this range.
                  </TableCell>
                </TableRow>
              ) : (
                [...workerRows]
                  .sort((a, b) => b.days_worked - a.days_worked)
                  .slice(0, 10)
                  .map((r) => (
                    <TableRow key={r.id} className="hover:bg-muted/30">
                      <TableCell className="text-xs py-2.5 font-semibold text-foreground">{r.title}</TableCell>
                      <TableCell className="text-xs py-2.5 text-muted-foreground">{r.category || '—'}</TableCell>
                      <TableCell className="text-xs py-2.5 text-center font-mono">{r.days_worked}</TableCell>
                      <TableCell className="text-xs py-2.5 text-right font-mono">
                        ₹{r.total_cost.toLocaleString('en-IN')}
                      </TableCell>
                    </TableRow>
                  ))
              )}
            </TableBody>
          </Table>
        </div>
      </Card>

      <p className="text-[11px] text-muted-foreground px-1">
        Every figure on this page is derived from recorded attendance. Nothing is estimated from
        the worker register.
      </p>
    </div>
  )
}
