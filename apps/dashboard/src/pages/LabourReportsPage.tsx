import * as React from 'react'
import {
  FileText,
  Download,
  Printer,
  Calendar,
  Search,
  DollarSign,
  PieChart as PieIcon,
  Building,
  Users,
  HardHat,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { toLocalISODate } from '@/lib/utils'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  fetchLabourStatementApi,
  type LabourStatement,
  type LabourStatementType,
} from '@/lib/api'

const REPORT_TYPES: {
  id: LabourStatementType
  label: string
  icon: typeof PieIcon
  desc: string
}[] = [
  { id: 'trade_breakdown', label: 'Trade Summary', icon: PieIcon, desc: 'Man-days and cost per trade' },
  { id: 'subcontractor_ledger', label: 'Contractor Summary', icon: Building, desc: 'Man-days and cost per contractor' },
  { id: 'daily_attendance', label: 'Daily Attendance', icon: Calendar, desc: 'Man-days and cost per day' },
  { id: 'worker_wages', label: 'Worker History', icon: HardHat, desc: 'Days worked and earnings per worker' },
]

/** The column heading for the grouping key changes per report, because a row
 *  means a different thing in each. Everything else is common. */
const TITLE_COLUMN: Record<LabourStatementType, string> = {
  trade_breakdown: 'Trade',
  subcontractor_ledger: 'Contractor',
  daily_attendance: 'Date',
  worker_wages: 'Worker',
}

type DatePreset = 'ALL' | 'TODAY' | 'THIS_WEEK' | 'THIS_MONTH' | 'CUSTOM'

/** Presets resolve against the *browser's* local date, matching the Attendance
 *  page. The server deliberately takes an explicit range rather than a named
 *  period: which day is "today" depends on the reader's timezone, and the
 *  backend does not know it. */
function resolveRange(
  preset: DatePreset,
  customFrom: string,
  customTo: string
): { date_from?: string; date_to?: string } {
  const now = new Date()
  if (preset === 'TODAY') {
    const today = toLocalISODate(now)
    return { date_from: today, date_to: today }
  }
  if (preset === 'THIS_WEEK') {
    // Last 7 days including today -- the same span the Attendance page's
    // "This Week" already means, so the two screens agree.
    const from = new Date(now.getTime() - 6 * 24 * 60 * 60 * 1000)
    return { date_from: toLocalISODate(from), date_to: toLocalISODate(now) }
  }
  if (preset === 'THIS_MONTH') {
    const first = new Date(now.getFullYear(), now.getMonth(), 1)
    return { date_from: toLocalISODate(first), date_to: toLocalISODate(now) }
  }
  if (preset === 'CUSTOM') {
    return { date_from: customFrom || undefined, date_to: customTo || undefined }
  }
  return {}
}

export default function LabourReportsPage() {
  const { scope } = useScope()

  const [activeReport, setActiveReport] = React.useState<LabourStatementType>('trade_breakdown')
  const [datePreset, setDatePreset] = React.useState<DatePreset>('ALL')
  const [customFrom, setCustomFrom] = React.useState('')
  const [customTo, setCustomTo] = React.useState('')
  const [search, setSearch] = React.useState('')
  const [statement, setStatement] = React.useState<LabourStatement | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  const loadStatement = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const range = resolveRange(datePreset, customFrom, customTo)
      const data = await fetchLabourStatementApi({
        report_type: activeReport,
        project_id:
          scope.mode === 'project' || scope.mode === 'site' ? scope.projectId : undefined,
        site_id: scope.mode === 'site' ? scope.siteId : undefined,
        ...range,
      })
      setStatement(data)
    } catch (err) {
      console.warn('Failed to load labour statement:', err)
      // Surfaced rather than swallowed: an empty table and an error are very
      // different claims, and the old page could not tell them apart.
      setError('Could not load this statement. The figures below may be missing entirely.')
      setStatement(null)
    } finally {
      setLoading(false)
    }
  }, [activeReport, scope, datePreset, customFrom, customTo])

  React.useEffect(() => {
    loadStatement()
  }, [loadStatement])

  const filteredRows = React.useMemo(() => {
    if (!statement?.rows) return []
    const query = search.trim().toLowerCase()
    if (!query) return statement.rows
    return statement.rows.filter(
      (r) =>
        r.title.toLowerCase().includes(query) ||
        (r.category && r.category.toLowerCase().includes(query)) ||
        (r.contractor && r.contractor.toLowerCase().includes(query)) ||
        (r.code && r.code.toLowerCase().includes(query))
    )
  }, [statement, search])

  const handleExportCSV = () => {
    if (!statement) return

    const headers = [
      'Ref Code',
      TITLE_COLUMN[activeReport],
      'Trade',
      'Contractor',
      'Man-Days',
      'Priced Man-Days',
      'Days Worked',
      'First Date',
      'Last Date',
      'Reports',
      'Avg Daily Wage (INR)',
      'Total Cost (INR)',
      '% of Cost',
    ]
    const rows = filteredRows.map((r) => [
      r.code || '',
      `"${r.title.replace(/"/g, '""')}"`,
      `"${r.category || ''}"`,
      `"${r.contractor || ''}"`,
      r.man_days,
      r.priced_man_days,
      r.days_worked,
      r.first_date || '',
      r.last_date || '',
      r.report_count,
      r.avg_daily_wage,
      r.total_cost,
      `${r.percentage}%`,
    ])

    // A trailing note so an exported file cannot be read as a complete costing
    // when part of the attendance behind it carried no wage.
    const footer: (string | number)[][] = [
      [],
      ['Total man-days', statement.total_man_days],
      ['Man-days with a recorded wage', statement.priced_man_days],
      ['Man-days with no recorded wage', statement.unpriced_man_days],
      ['Total cost (INR)', statement.total_cost],
      ['Range', `${statement.date_from || 'all time'} to ${statement.date_to || 'today'}`],
      ['Generated', new Date(statement.generated_at).toISOString()],
    ]

    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(',')), ...footer.map((e) => e.join(','))].join(
        '\n'
      )
    const link = document.createElement('a')
    link.setAttribute('href', encodeURI(csvContent))
    link.setAttribute('download', `Labour_${activeReport}_${toLocalISODate()}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Sites)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  const rangeLabel = React.useMemo(() => {
    if (!statement) return ''
    if (!statement.date_from && !statement.date_to) return 'All recorded attendance'
    return `${statement.date_from || 'earliest'} → ${statement.date_to || 'latest'}`
  }, [statement])

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg border border-amber-500/30 bg-amber-500/10 flex items-center justify-center text-amber-600 dark:text-amber-400 shrink-0 shadow-2xs">
            <FileText className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Labour Reports
              <Badge variant="outline" className="text-[10px] font-mono border-amber-500/30 text-amber-600 dark:text-amber-400">
                From attendance
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <Button
            size="sm"
            variant="outline"
            onClick={() => window.print()}
            className="h-8 gap-1.5 text-xs font-medium"
          >
            <Printer className="size-3.5" />
            Print
          </Button>

          <Button
            size="sm"
            onClick={handleExportCSV}
            disabled={!statement}
            className="h-8 gap-1.5 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white shadow-2xs"
          >
            <Download className="size-3.5" />
            Export CSV
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
          <AlertTriangle className="size-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Top 4 KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Recorded Cost"
          value={
            <span className="text-amber-600 dark:text-amber-400">
              ₹{statement ? statement.total_cost.toLocaleString('en-IN') : '0'}
            </span>
          }
          description={
            statement && statement.unpriced_man_days > 0
              ? `Excludes ${statement.unpriced_man_days} man-days with no wage recorded`
              : 'From recorded attendance'
          }
          icon={<DollarSign className="text-amber-500" />}
        />
        <KpiCard
          title="Man-Days"
          value={
            <span className="text-emerald-600 dark:text-emerald-400">
              {statement ? statement.total_man_days : 0}
            </span>
          }
          description="Person-days recorded in range"
          icon={<Users className="text-emerald-500" />}
        />
        <KpiCard
          title="Rows"
          value={
            <span className="text-blue-600 dark:text-blue-400">
              {statement ? statement.rows.length : 0}
            </span>
          }
          description="Groups in this statement"
          icon={<Building className="text-blue-500" />}
        />
        <KpiCard
          title="Average Daily Wage"
          value={
            <span className="text-purple-600 dark:text-purple-400">
              ₹{statement ? statement.avg_daily_wage.toLocaleString('en-IN') : '0'}
            </span>
          }
          description="Across priced man-days only"
          icon={<HardHat className="text-purple-500" />}
        />
      </div>

      {/* Report Type Selector Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
        {REPORT_TYPES.map((type) => {
          const Icon = type.icon
          const isActive = activeReport === type.id
          return (
            <button
              key={type.id}
              onClick={() => setActiveReport(type.id)}
              className={`p-3 rounded-lg border text-left transition-all flex flex-col justify-between gap-2 ${
                isActive
                  ? 'border-amber-500 bg-amber-500/5 dark:bg-amber-500/10 shadow-2xs'
                  : 'border-border/80 bg-card hover:bg-muted/40'
              }`}
            >
              <div className="flex items-center justify-between w-full">
                <div className={`p-1.5 rounded-md ${isActive ? 'bg-amber-500 text-white' : 'bg-muted text-muted-foreground'}`}>
                  <Icon className="size-4" />
                </div>
                {isActive && (
                  <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-300 text-[9px]">Active</Badge>
                )}
              </div>
              <div>
                <h3 className="font-bold text-xs text-foreground">{type.label}</h3>
                <p className="text-[10px] text-muted-foreground line-clamp-1">{type.desc}</p>
              </div>
            </button>
          )
        })}
      </div>

      {/* Filter & Toolbar */}
      <div className="flex flex-col sm:flex-row gap-2.5 items-center justify-between border border-border/80 p-2.5 rounded-lg bg-card/40">
        <div className="flex flex-wrap gap-2 w-full sm:w-auto flex-1 items-center">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search this statement..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>

          <Select value={datePreset} onValueChange={(v) => setDatePreset(v as DatePreset)}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-40">
              <Calendar className="size-3.5 mr-1 text-amber-500" />
              <SelectValue placeholder="All Dates" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Time</SelectItem>
              <SelectItem value="TODAY">Today</SelectItem>
              <SelectItem value="THIS_WEEK">This Week</SelectItem>
              <SelectItem value="THIS_MONTH">This Month</SelectItem>
              <SelectItem value="CUSTOM">Custom Range</SelectItem>
            </SelectContent>
          </Select>

          {datePreset === 'CUSTOM' && (
            <div className="flex items-center gap-1.5">
              <Input
                type="date"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                className="h-9 text-xs w-36"
                aria-label="From date"
              />
              <span className="text-xs text-muted-foreground">to</span>
              <Input
                type="date"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                className="h-9 text-xs w-36"
                aria-label="To date"
              />
            </div>
          )}
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={loadStatement}
          disabled={loading}
          className="h-9 text-xs gap-1 text-muted-foreground hover:text-foreground self-end sm:self-auto"
        >
          <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Statement Header Banner */}
      {statement && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs px-1 text-muted-foreground font-medium">
          <div>
            <span className="font-bold text-foreground">{statement.title}</span> • {statement.subtitle}
          </div>
          <span className="text-[10px] font-mono text-muted-foreground">{rangeLabel}</span>
        </div>
      )}

      {/* Statement Table */}
      <div className="border rounded-lg overflow-hidden bg-card shadow-2xs">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow className="hover:bg-transparent border-b">
                <TableHead className="text-xs font-semibold h-10 w-24">Ref</TableHead>
                <TableHead className="text-xs font-semibold h-10">{TITLE_COLUMN[activeReport]}</TableHead>
                <TableHead className="text-xs font-semibold h-10 text-center">Man-Days</TableHead>
                <TableHead className="text-xs font-semibold h-10 text-center">Days Worked</TableHead>
                <TableHead className="text-xs font-semibold h-10 text-right">Avg Rate (₹/day)</TableHead>
                <TableHead className="text-xs font-semibold h-10 text-right">Total Cost (₹)</TableHead>
                <TableHead className="text-xs font-semibold h-10 text-right w-32">% of Cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                    Loading statement...
                  </TableCell>
                </TableRow>
              ) : filteredRows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                    {search
                      ? 'No rows match your search.'
                      : 'No attendance recorded for this scope and date range.'}
                  </TableCell>
                </TableRow>
              ) : (
                filteredRows.map((row) => (
                  <TableRow key={row.id} className="hover:bg-muted/30 transition-colors">
                    <TableCell className="font-mono text-xs font-bold text-amber-600 dark:text-amber-400 py-3">
                      {row.code || '—'}
                    </TableCell>

                    <TableCell className="font-semibold text-xs py-3 text-foreground">
                      <div className="flex flex-col">
                        <span>{row.title}</span>
                        {(row.category || row.contractor) && (
                          <span className="text-[10px] text-muted-foreground font-normal">
                            {[row.category, row.contractor].filter(Boolean).join(' • ')}
                          </span>
                        )}
                        {row.first_date && row.last_date && row.first_date !== row.last_date && (
                          <span className="text-[10px] text-muted-foreground font-normal font-mono">
                            {row.first_date} → {row.last_date}
                          </span>
                        )}
                      </div>
                    </TableCell>

                    <TableCell className="text-xs py-3 text-center font-semibold">
                      {row.man_days}
                      {row.priced_man_days < row.man_days && (
                        <span
                          className="block text-[10px] font-normal text-amber-600 dark:text-amber-400"
                          title="Some of these man-days had no wage recorded, so they add no cost"
                        >
                          {row.man_days - row.priced_man_days} unpriced
                        </span>
                      )}
                    </TableCell>

                    <TableCell className="text-xs py-3 text-center">{row.days_worked}</TableCell>

                    <TableCell className="text-xs py-3 text-right font-mono">
                      {row.priced_man_days > 0 ? `₹${row.avg_daily_wage.toLocaleString('en-IN')}` : '—'}
                    </TableCell>

                    <TableCell className="text-xs py-3 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                      ₹{row.total_cost.toLocaleString('en-IN')}
                    </TableCell>

                    <TableCell className="text-xs py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <div className="w-16 bg-muted rounded-full h-1.5 overflow-hidden hidden sm:block">
                          <div
                            className="bg-amber-500 h-full rounded-full"
                            style={{ width: `${Math.min(100, Number(row.percentage))}%` }}
                          />
                        </div>
                        <span className="font-mono font-bold text-[11px] text-foreground">
                          {row.percentage}%
                        </span>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {/* Statement footer. States what the figures rest on -- it does not
            claim an audit, a preparer or an approver, none of which exist. */}
        {statement && (
          <div className="border-t bg-muted/20 px-4 py-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 text-[11px] text-muted-foreground">
            <div>
              Generated from recorded attendance
              {statement.unpriced_man_days > 0 && (
                <span className="text-amber-600 dark:text-amber-400">
                  {' '}
                  • {statement.unpriced_man_days} of {statement.total_man_days} man-days have no
                  wage recorded and add no cost
                </span>
              )}
            </div>
            <span className="font-mono text-[10px] shrink-0">
              {new Date(statement.generated_at).toLocaleString('en-IN')}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
