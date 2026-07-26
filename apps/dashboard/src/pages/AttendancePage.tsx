import * as React from 'react'
import {
  ClipboardCheck,
  Calendar,
  DollarSign,
  Users,
  HardHat,
  Bot,
  Globe,
  Eye,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
  type LabourAttendanceSummaryItem,
} from '@/lib/api'
import { AttendanceDetailSheet } from '@/components/workforce/attendance-detail-sheet'

export default function AttendancePage() {
  const { scope } = useScope()
  const [reports, setReports] = React.useState<LabourAttendanceSummaryItem[]>([])
  const [loading, setLoading] = React.useState(true)
  const [dateFilter, setDateFilter] = React.useState<string>('all')

  // Selected Report for Detail Sheet
  const [selectedReportId, setSelectedReportId] = React.useState<string | null>(null)
  const [detailOpen, setDetailOpen] = React.useState(false)

  const loadReports = React.useCallback(async () => {
    setLoading(true)
    try {
      let date_from: string | undefined
      const now = new Date()

      if (dateFilter === 'today') {
        date_from = now.toISOString().split('T')[0]
      } else if (dateFilter === 'week') {
        const lastWeek = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        date_from = lastWeek.toISOString().split('T')[0]
      } else if (dateFilter === 'month') {
        const firstDay = new Date(now.getFullYear(), now.getMonth(), 1)
        date_from = firstDay.toISOString().split('T')[0]
      }

      const res = await fetchAttendanceReportsApi({
        project_id: scope.mode === 'project' || scope.mode === 'site' ? scope.projectId : undefined,
        site_id: scope.mode === 'site' ? scope.siteId : undefined,
        date_from,
      })
      setReports(res.items || [])
    } catch (err) {
      console.warn('Failed to load attendance reports:', err)
    } finally {
      setLoading(false)
    }
  }, [scope, dateFilter])

  React.useEffect(() => {
    loadReports()
  }, [loadReports])

  // Derived KPI Metrics
  const totalHeadcount = reports.reduce((acc, r) => acc + (r.total_headcount || 0), 0)
  const totalSpend = reports.reduce((acc, r) => acc + (r.total_cost || 0), 0)
  const whatsappCount = reports.filter((r) => r.recorded_via?.includes('whatsapp')).length

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
            <ClipboardCheck className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Labour Attendance & Site Logs
              <Badge variant="outline" className="text-[10px] font-mono border-amber-500/30 text-amber-600 dark:text-amber-400">
                Workforce Module
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>
      </div>

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Total Headcount Logged"
          value={<span className="text-emerald-600 dark:text-emerald-400">{totalHeadcount} Man-Days</span>}
          trend="up"
          trendValue="Site Labor"
          description="Cumulative headcount"
          icon={<Users className="text-emerald-500" />}
          chartData={[20, 35, 50, 65, 80, 95]}
        />
        <KpiCard
          title="Total Labor Spend"
          value={
            <span className="text-amber-600 dark:text-amber-400">
              ₹{totalSpend.toLocaleString('en-IN')}
            </span>
          }
          trend="up"
          trendValue="Wage Cost"
          description="Total labor expense"
          icon={<DollarSign className="text-amber-500" />}
        />
        <KpiCard
          title="WhatsApp Submissions"
          value={<span className="text-blue-600 dark:text-blue-400">{whatsappCount} Bot Submissions</span>}
          trend="neutral"
          trendValue="AI Assistant"
          description="Bot-parsed site logs"
          icon={<Bot className="text-blue-500" />}
        />
        <KpiCard
          title="Attendance Reports"
          value={<span className="text-purple-600 dark:text-purple-400">{reports.length} Reports</span>}
          trend="neutral"
          trendValue="Site Entries"
          description="Logged daily reports"
          icon={<HardHat className="text-purple-500" />}
        />
      </div>

      {/* Toolbar & Filters */}
      <Card className="p-3 border shadow-2xs flex flex-col sm:flex-row gap-3 items-center justify-between bg-card">
        <div className="flex items-center gap-2">
          <Calendar className="size-4 text-amber-500 shrink-0" />
          <span className="text-xs font-bold text-foreground">Date Range Filter:</span>
        </div>

        <div className="flex items-center gap-1.5 bg-muted/60 p-1 rounded-lg border w-full sm:w-auto justify-center">
          <button
            onClick={() => setDateFilter('today')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              dateFilter === 'today'
                ? 'bg-background text-foreground shadow-2xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Today
          </button>
          <button
            onClick={() => setDateFilter('week')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              dateFilter === 'week'
                ? 'bg-background text-foreground shadow-2xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Last 7 Days
          </button>
          <button
            onClick={() => setDateFilter('month')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              dateFilter === 'month'
                ? 'bg-background text-foreground shadow-2xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            This Month
          </button>
          <button
            onClick={() => setDateFilter('all')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              dateFilter === 'all'
                ? 'bg-background text-foreground shadow-2xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            All Time
          </button>
        </div>
      </Card>

      {/* Attendance Reports Table */}
      <Card className="border shadow-2xs overflow-hidden bg-card">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent border-b">
              <TableHead className="text-xs font-semibold h-10">Report Date</TableHead>
              <TableHead className="text-xs font-semibold h-10">Recorded Via</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-center">Trade Lines</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-center">Total Headcount</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-right">Total Daily Cost</TableHead>
              <TableHead className="text-xs font-semibold h-10">Notes / Summary</TableHead>
              <TableHead className="text-xs font-semibold h-10 w-12 text-right">Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                  Loading attendance reports...
                </TableCell>
              </TableRow>
            ) : reports.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                  No attendance reports logged for the selected scope & date filter.
                </TableCell>
              </TableRow>
            ) : (
              reports.map((item) => (
                <TableRow
                  key={item.id}
                  onClick={() => {
                    setSelectedReportId(item.id)
                    setDetailOpen(true)
                  }}
                  className="hover:bg-muted/30 transition-colors cursor-pointer"
                >
                  <TableCell className="font-semibold text-xs py-3 text-foreground">
                    <div className="flex items-center gap-2">
                      <Calendar className="size-3.5 text-amber-500 shrink-0" />
                      <span>{item.occurred_date}</span>
                    </div>
                  </TableCell>

                  <TableCell className="text-xs py-3">
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
                          <Globe className="size-3" /> Web Dashboard
                        </span>
                      )}
                    </Badge>
                  </TableCell>

                  <TableCell className="text-xs py-3 text-center font-semibold">
                    <Badge variant="outline" className="text-[10px]">
                      {item.line_count || 0} Lines
                    </Badge>
                  </TableCell>

                  <TableCell className="text-xs py-3 text-center font-bold text-foreground">
                    {item.total_headcount} Workers
                  </TableCell>

                  <TableCell className="text-xs py-3 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                    ₹{item.total_cost ? item.total_cost.toLocaleString('en-IN') : '0'}
                  </TableCell>

                  <TableCell className="text-xs py-3 text-muted-foreground truncate max-w-xs">
                    {item.notes || 'Daily site attendance log'}
                  </TableCell>

                  <TableCell className="text-xs py-3 text-right">
                    <Button variant="ghost" size="icon" className="size-7">
                      <Eye className="size-3.5 text-muted-foreground hover:text-foreground" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Report Detail Sheet */}
      <AttendanceDetailSheet
        reportId={selectedReportId}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />
    </div>
  )
}
