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
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
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
  fetchLabourReportApi,
  type LabourReportStatementItem,
} from '@/lib/api'

const REPORT_TYPES = [
  { id: 'trade_breakdown', label: 'Trade Skill Cost Audit', icon: PieIcon, desc: 'Aggregated daily costs & headcount by trade skill' },
  { id: 'subcontractor_ledger', label: 'Subcontractor Agency Ledger', icon: Building, desc: 'Subcontractor agency allocations & wage commitments' },
  { id: 'daily_attendance', label: 'Daily Site Attendance Audit', icon: Calendar, desc: 'Historical daily site logs & wage disbursements' },
  { id: 'worker_wages', label: 'Worker Baseline Wage Audit', icon: HardHat, desc: 'Worker master daily baseline rates & payroll' },
]

export default function LabourReportsPage() {
  const { scope } = useScope()

  const [activeReport, setActiveReport] = React.useState('trade_breakdown')
  const [datePreset, setDatePreset] = React.useState('ALL')
  const [search, setSearch] = React.useState('')
  const [statement, setStatement] = React.useState<LabourReportStatementItem | null>(null)
  const [loading, setLoading] = React.useState(true)

  const loadStatement = React.useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchLabourReportApi({
        report_type: activeReport,
        project_id: scope.mode === 'project' || scope.mode === 'site' ? scope.projectId : undefined,
      })
      if (data) setStatement(data)
    } catch (err) {
      console.warn('Failed to load labour report statement:', err)
    } finally {
      setLoading(false)
    }
  }, [activeReport, scope])

  React.useEffect(() => {
    loadStatement()
  }, [loadStatement])

  const filteredRows = React.useMemo(() => {
    if (!statement?.rows) return []
    return statement.rows.filter((r) => {
      const query = search.toLowerCase()
      return (
        r.title.toLowerCase().includes(query) ||
        (r.category && r.category.toLowerCase().includes(query)) ||
        (r.contractor && r.contractor.toLowerCase().includes(query)) ||
        (r.code && r.code.toLowerCase().includes(query))
      )
    })
  }, [statement, search])

  const handleExportCSV = () => {
    if (!statement || !statement.rows) return

    const headers = ['Ref Code', 'Title', 'Category / Trade', 'Contractor Agency', 'Headcount (Man-Days)', 'Avg Daily Wage (INR)', 'Total Cost (INR)', '% Contribution']
    const rows = filteredRows.map((r) => [
      r.code || '',
      `"${r.title.replace(/"/g, '""')}"`,
      `"${r.category || ''}"`,
      `"${r.contractor || ''}"`,
      r.headcount,
      r.avg_daily_wage,
      r.total_cost,
      `${r.percentage}%`,
    ])

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `Labour_Report_${activeReport}_${new Date().toISOString().split('T')[0]}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Sites)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

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
              Labour Cost & Headcount Statements
              <Badge variant="outline" className="text-[10px] font-mono border-amber-500/30 text-amber-600 dark:text-amber-400">
                Workforce Module
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
            Print Statement
          </Button>

          <Button
            size="sm"
            onClick={handleExportCSV}
            disabled={!statement}
            className="h-8 gap-1.5 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white shadow-2xs"
          >
            <Download className="size-3.5" />
            Export Statement CSV
          </Button>
        </div>
      </div>

      {/* Top 4 KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Total Statement Cost"
          value={<span className="text-amber-600 dark:text-amber-400">₹{statement ? statement.total_cost.toLocaleString('en-IN') : '0'}</span>}
          trend="up"
          trendValue="Statement Total"
          description="Total labor spend in statement"
          icon={<DollarSign className="text-amber-500" />}
          chartData={[25, 40, 55, 70, 85, 100]}
        />
        <KpiCard
          title="Statement Man-Days"
          value={<span className="text-emerald-600 dark:text-emerald-400">{statement ? statement.total_headcount : 0} Headcount</span>}
          trend="up"
          trendValue="Cumulative"
          description="Total man-days in statement"
          icon={<Users className="text-emerald-500" />}
        />
        <KpiCard
          title="Active Trades / Agencies"
          value={<span className="text-blue-600 dark:text-blue-400">{statement ? statement.rows.length : 0} Items</span>}
          trend="neutral"
          trendValue="Breakdown"
          description="Categorized statement lines"
          icon={<Building className="text-blue-500" />}
        />
        <KpiCard
          title="Average Daily Wage"
          value={<span className="text-purple-600 dark:text-purple-400">₹{statement ? statement.avg_wage.toLocaleString('en-IN') : '0'}/day</span>}
          trend="neutral"
          trendValue="Rate Baseline"
          description="Average daily wage rate"
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

      {/* Filter & Toolbar (Matching ExpensesPage container styling) */}
      <div className="flex flex-col sm:flex-row gap-2.5 items-center justify-between border border-border/80 p-2.5 rounded-lg bg-card/40">
        <div className="flex flex-wrap gap-2 w-full sm:w-auto flex-1 items-center">
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search trade, code, contractor, title..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>

          <Select value={datePreset} onValueChange={setDatePreset}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-40">
              <Calendar className="size-3.5 mr-1 text-amber-500" />
              <SelectValue placeholder="All Dates" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Time</SelectItem>
              <SelectItem value="TODAY">Today</SelectItem>
              <SelectItem value="THIS_MONTH">This Month</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={loadStatement}
          disabled={loading}
          className="h-9 text-xs gap-1 text-muted-foreground hover:text-foreground self-end sm:self-auto"
        >
          <RefreshCw className={`size-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh Statement
        </Button>
      </div>

      {/* Statement Header Banner */}
      {statement && (
        <div className="flex items-center justify-between text-xs px-1 text-muted-foreground font-medium">
          <div>
            <span className="font-bold text-foreground">{statement.title}</span> • {statement.subtitle}
          </div>
          <span className="text-[10px] font-mono text-muted-foreground">
            Generated: {new Date(statement.generated_at).toLocaleString('en-IN')}
          </span>
        </div>
      )}

      {/* Executive Statement Table Container (Matching ExpensesPage table styling) */}
      <div className="border rounded-lg overflow-hidden bg-card shadow-2xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent border-b">
              <TableHead className="text-xs font-semibold h-10 w-28">Ref Code</TableHead>
              <TableHead className="text-xs font-semibold h-10">Item Title / Trade Skill</TableHead>
              <TableHead className="text-xs font-semibold h-10">Subcontractor / Agency</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-center">Headcount (Man-Days)</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-right">Avg Rate (₹/day)</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-right">Total Cost (₹)</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-right w-32">% Contribution</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                  Aggregating executive labour statement...
                </TableCell>
              </TableRow>
            ) : filteredRows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                  No statement items found matching current filters.
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
                      <span className="text-[10px] text-muted-foreground font-normal">{row.category}</span>
                    </div>
                  </TableCell>

                  <TableCell className="text-xs py-3 text-muted-foreground">
                    {row.contractor || 'Direct Payroll'}
                  </TableCell>

                  <TableCell className="text-xs py-3 text-center font-semibold">
                    {row.headcount}
                  </TableCell>

                  <TableCell className="text-xs py-3 text-right font-mono">
                    ₹{row.avg_daily_wage.toLocaleString('en-IN')}
                  </TableCell>

                  <TableCell className="text-xs py-3 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                    ₹{row.total_cost.toLocaleString('en-IN')}
                  </TableCell>

                  <TableCell className="text-xs py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 bg-muted rounded-full h-1.5 overflow-hidden hidden sm:block">
                        <div
                          className="bg-amber-500 h-full rounded-full"
                          style={{ width: `${Math.min(100, row.percentage)}%` }}
                        />
                      </div>
                      <span className="font-mono font-bold text-[11px] text-foreground">{row.percentage}%</span>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        {/* Statement Signoff Footer */}
        {statement && (
          <div className="border-t bg-muted/20 px-4 py-3 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
            <div className="text-muted-foreground text-[11px]">
              Certified Executive Labour Statement • Audit Verified by Mesiri AI Platform
            </div>

            <div className="flex items-center gap-6 font-mono text-[10px] text-muted-foreground">
              <span>Prepared by: Site Auditor</span>
              <span>Approved by: CFO / Project Director</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
