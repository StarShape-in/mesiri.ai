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
  Download,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Trash2,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { toLocalISODate } from '@/lib/utils'
import { KpiCard } from '@/components/ui/kpi-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { BulkActionBar } from '@/components/ui/bulk-action-bar'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  deleteAttendanceReportApi,
  fetchAttendanceReportsApi,
  fetchLabourStatementApi,
  type LabourAttendanceSummaryItem,
  type LabourStatement,
} from '@/lib/api'
import { AttendanceDetailSheet } from '@/components/workforce/attendance-detail-sheet'

type SortField = 'date' | 'via' | 'lines' | 'headcount' | 'cost'
type SortOrder = 'asc' | 'desc'

export default function AttendancePage() {
  const { scope } = useScope()
  // Always rendered. Hiding it behind a role guessed in the browser is what
  // made this undiagnosable: the button silently vanished and there was no way
  // to tell whether the role, the flag, or the deploy was at fault. The server
  // enforces both gates and returns a reason, which the UI now shows.
  const [deletingId, setDeletingId] = React.useState<string | null>(null)
  const [reports, setReports] = React.useState<LabourAttendanceSummaryItem[]>([])
  const [statement, setStatement] = React.useState<LabourStatement | null>(null)
  const [loading, setLoading] = React.useState(true)
  // A failed fetch must not render as "no attendance recorded".
  const [error, setError] = React.useState<string | null>(null)

  // Filters state
  const [dateFilter, setDateFilter] = React.useState<string>('ALL')
  const [sourceFilter, setSourceFilter] = React.useState<string>('ALL')

  // Selection & Bulk Action state
  const [selectedIds, setSelectedIds] = React.useState<string[]>([])

  // Sorting state
  const [sortField, setSortField] = React.useState<SortField>('date')
  const [sortOrder, setSortOrder] = React.useState<SortOrder>('desc')

  // Pagination state
  const [currentPage, setCurrentPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState(10)

  // Selected Report for Detail Sheet
  const [selectedReportId, setSelectedReportId] = React.useState<string | null>(null)
  const [detailOpen, setDetailOpen] = React.useState(false)

  const loadReports = React.useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      let date_from: string | undefined
      const now = new Date()

      if (dateFilter === 'TODAY') {
        date_from = toLocalISODate(now)
      } else if (dateFilter === 'THIS_WEEK') {
        const lastWeek = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        date_from = toLocalISODate(lastWeek)
      } else if (dateFilter === 'THIS_MONTH') {
        const firstDay = new Date(now.getFullYear(), now.getMonth(), 1)
        date_from = toLocalISODate(firstDay)
      }

      const projectId =
        scope.mode === 'project' || scope.mode === 'site' ? scope.projectId : undefined
      const siteId = scope.mode === 'site' ? scope.siteId : undefined

      const [res, stmt] = await Promise.all([
        fetchAttendanceReportsApi({
          project_id: projectId,
          site_id: siteId,
          date_from,
          // Explicit, because the backend default is 50 and this table
          // presents what it receives as the complete list. 100 is the
          // endpoint's documented maximum; beyond that the totals above
          // still come from the statement, which is not paginated.
          limit: 100,
        }),
        // Same scope and range as the list, so the totals above the table
        // describe exactly what the filters select -- not the page of rows
        // that happened to load.
        fetchLabourStatementApi({
          report_type: 'daily_attendance',
          project_id: projectId,
          site_id: siteId,
          date_from,
        }).catch(() => null),
      ])
      setReports(res.items || [])
      setStatement(stmt)
    } catch (err) {
      console.warn('Failed to load attendance reports:', err)
      setError('Could not load attendance reports. This list may be incomplete.')
    } finally {
      setLoading(false)
    }
  }, [scope, dateFilter])

  React.useEffect(() => {
    loadReports()
  }, [loadReports])

  // Handle Sort Toggle
  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) return <ArrowUpDown className="size-3 text-muted-foreground/60 ml-1 inline" />
    return sortOrder === 'asc' ? (
      <ArrowUp className="size-3 text-amber-500 ml-1 inline" />
    ) : (
      <ArrowDown className="size-3 text-amber-500 ml-1 inline" />
    )
  }

  // Filtered & Sorted reports
  const filteredReports = React.useMemo(() => {
    return reports
      .filter((r) => {
        if (sourceFilter === 'WHATSAPP' && !r.recorded_via?.includes('whatsapp')) return false
        if (sourceFilter === 'WEB' && r.recorded_via?.includes('whatsapp')) return false
        return true
      })
      .sort((a, b) => {
        const modifier = sortOrder === 'asc' ? 1 : -1
        if (sortField === 'date') return a.occurred_date.localeCompare(b.occurred_date) * modifier
        if (sortField === 'via') return a.recorded_via.localeCompare(b.recorded_via) * modifier
        if (sortField === 'lines') return ((a.line_count || 0) - (b.line_count || 0)) * modifier
        if (sortField === 'headcount') return ((a.total_headcount || 0) - (b.total_headcount || 0)) * modifier
        if (sortField === 'cost') return ((a.total_cost || 0) - (b.total_cost || 0)) * modifier
        return 0
      })
  }, [reports, sourceFilter, sortField, sortOrder])

  // Pagination calculation
  const totalPages = Math.ceil(filteredReports.length / pageSize) || 1
  const paginatedReports = React.useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredReports.slice(start, start + pageSize)
  }, [filteredReports, currentPage, pageSize])

  // Bulk Selection Handlers
  const isAllSelected = paginatedReports.length > 0 && paginatedReports.every((r) => selectedIds.includes(r.id))

  const toggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds([])
    } else {
      setSelectedIds(paginatedReports.map((r) => r.id))
    }
  }

  const toggleSelectRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  const handleDelete = async (reportId: string, occurredDate: string) => {
    if (
      !confirm(
        [
          `Permanently delete the attendance report for ${occurredDate}?`,
          '',
          'This removes the report and its worker lines for good. It cannot be undone.',
          '',
          'To correct a mistake instead, re-send that day over WhatsApp and choose',
          '"Replace" — that supersedes the old report while keeping it auditable.',
        ].join('\n')
      )
    ) {
      return
    }
    setDeletingId(reportId)
    setError(null)
    try {
      const result = await deleteAttendanceReportApi(reportId)
      // Reload rather than splice locally: the totals above the table come from
      // the statement endpoint and would otherwise still include this report.
      await loadReports()
      if (result.unlinked_corrections > 0) {
        setError(
          `Deleted. Note: ${result.unlinked_corrections} report(s) referenced this one as a ` +
            'correction and no longer do, so that day may now count twice.'
        )
      }
    } catch (err: any) {
      const status = err?.response?.status
      setError(
        status === 403
          ? err?.response?.data?.detail ||
            'Deleting attendance is not permitted for your role or this environment.'
          : 'Could not delete that attendance report.'
      )
    } finally {
      setDeletingId(null)
    }
  }

  // Export CSV
  const exportCsv = () => {
    const headers = ['ID', 'Occurred Date', 'Recorded Via', 'Line Items Count', 'Total Headcount', 'Total Daily Cost (INR)', 'Notes']
    const rows = filteredReports.map((r) => [
      r.id,
      r.occurred_date,
      r.recorded_via,
      r.line_count || 0,
      r.total_headcount || 0,
      r.total_cost || 0,
      `"${(r.notes || '').replace(/"/g, '""')}"`,
    ])
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `Labour_Attendance_Reports_${toLocalISODate()}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Man-days and cost come from the backend statement for the same scope and
  // date range, not from summing the table below. The table is a page of at
  // most 50 reports, so totalling it reported a truncated figure as if it
  // were the whole range.
  const totalHeadcount = statement?.total_man_days ?? 0
  const totalSpend = statement?.total_cost ?? 0
  const unpricedManDays = statement?.unpriced_man_days ?? 0
  // These two are honestly about the loaded page, and say so on the card.
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

        <Button
          size="sm"
          variant="outline"
          onClick={exportCsv}
          className="h-8 gap-1.5 text-xs font-medium self-start sm:self-auto"
        >
          <Download className="size-3.5" />
          Export Statement CSV
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-700 dark:text-rose-300">
          <AlertTriangle className="size-3.5 shrink-0" />
          {error}
        </div>
      )}

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Man-Days in Range"
          value={<span className="text-emerald-600 dark:text-emerald-400">{totalHeadcount} Man-Days</span>}
          description="Every report in the selected range"
          icon={<Users className="text-emerald-500" />}
        />
        <KpiCard
          title="Labour Cost in Range"
          value={
            <span className="text-amber-600 dark:text-amber-400">
              ₹{totalSpend.toLocaleString('en-IN')}
            </span>
          }
          description={
            unpricedManDays > 0
              ? `Excludes ${unpricedManDays} man-days with no wage recorded`
              : 'From recorded attendance'
          }
          icon={<DollarSign className="text-amber-500" />}
        />
        <KpiCard
          title="WhatsApp Submissions"
          value={<span className="text-blue-600 dark:text-blue-400">{whatsappCount} Reports</span>}
          description="Of the reports loaded below"
          icon={<Bot className="text-blue-500" />}
        />
        <KpiCard
          title="Attendance Reports"
          value={<span className="text-purple-600 dark:text-purple-400">{reports.length} Reports</span>}
          description="Loaded in the table below"
          icon={<HardHat className="text-purple-500" />}
        />
      </div>

      {/* Filter & Toolbar (Matching ExpensesPage container styling) */}
      <div className="flex flex-col sm:flex-row gap-2.5 items-center justify-between border border-border/80 p-2.5 rounded-lg bg-card/40">
        <div className="flex flex-wrap gap-2 w-full sm:w-auto flex-1 items-center">
          <Select value={dateFilter} onValueChange={setDateFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-40">
              <Calendar className="size-3.5 mr-1 text-amber-500" />
              <SelectValue placeholder="Date Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Time</SelectItem>
              <SelectItem value="TODAY">Today</SelectItem>
              <SelectItem value="THIS_WEEK">Last 7 Days</SelectItem>
              <SelectItem value="THIS_MONTH">This Month</SelectItem>
            </SelectContent>
          </Select>

          <Select value={sourceFilter} onValueChange={setSourceFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-40">
              <SelectValue placeholder="Recorded Via" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Sources</SelectItem>
              <SelectItem value="WHATSAPP">WhatsApp Bot</SelectItem>
              <SelectItem value="WEB">Web Dashboard</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Source Tab Filter */}
        <Tabs value={sourceFilter} onValueChange={setSourceFilter} className="w-full sm:w-auto">
          <TabsList className="h-9 text-xs grid grid-cols-3 w-full sm:w-auto">
            <TabsTrigger value="ALL" className="text-xs">All</TabsTrigger>
            <TabsTrigger value="WHATSAPP" className="text-xs">WhatsApp</TabsTrigger>
            <TabsTrigger value="WEB" className="text-xs">Web</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Filter Summary Banner */}
      <div className="flex items-center justify-between text-xs px-1 text-muted-foreground font-medium">
        <div>
          Showing <span className="text-foreground font-semibold">{filteredReports.length}</span> of {reports.length} records
        </div>
        {selectedIds.length > 0 && (
          <span className="text-amber-600 font-semibold text-xs">
            {selectedIds.length} items checked
          </span>
        )}
      </div>

      {/* Main Attendance Table Container (Matching ExpensesPage table styling) */}
      <div className="border rounded-lg overflow-hidden bg-card shadow-2xs">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow className="hover:bg-transparent border-b">
                <TableHead className="w-[40px] px-3">
                  <input
                    type="checkbox"
                    checked={isAllSelected}
                    onChange={toggleSelectAll}
                    className="size-4 rounded border-border text-amber-600 focus:ring-amber-500 cursor-pointer accent-amber-600"
                    title="Select All"
                  />
                </TableHead>

                <TableHead
                  className="text-xs font-semibold h-10 cursor-pointer select-none"
                  onClick={() => toggleSort('date')}
                >
                  Report Date {renderSortIcon('date')}
                </TableHead>

                <TableHead
                  className="text-xs font-semibold h-10 cursor-pointer select-none"
                  onClick={() => toggleSort('via')}
                >
                  Recorded Via {renderSortIcon('via')}
                </TableHead>

                <TableHead
                  className="text-xs font-semibold h-10 text-center cursor-pointer select-none"
                  onClick={() => toggleSort('lines')}
                >
                  Trade Lines {renderSortIcon('lines')}
                </TableHead>

                <TableHead
                  className="text-xs font-semibold h-10 text-center cursor-pointer select-none"
                  onClick={() => toggleSort('headcount')}
                >
                  Total Headcount {renderSortIcon('headcount')}
                </TableHead>

                <TableHead
                  className="text-xs font-semibold h-10 text-right cursor-pointer select-none"
                  onClick={() => toggleSort('cost')}
                >
                  Total Daily Cost {renderSortIcon('cost')}
                </TableHead>

                <TableHead className="text-xs font-semibold h-10">Notes / Summary</TableHead>

                <TableHead className="text-xs font-semibold h-10 w-12 text-right">Detail</TableHead>

                {/* Development cleanup. Hidden for non-admins; the endpoint
                    enforces both ADMIN and the server-side flag regardless. */}
                {(
                  <TableHead className="text-xs font-semibold h-10 w-12 text-right">Delete</TableHead>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={9} className="h-32 text-center text-xs text-muted-foreground">
                    Loading attendance reports...
                  </TableCell>
                </TableRow>
              ) : paginatedReports.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="h-32 text-center text-xs text-muted-foreground">
                    No attendance reports logged for the selected scope & date filter.
                  </TableCell>
                </TableRow>
              ) : (
                paginatedReports.map((item) => {
                  const isSelected = selectedIds.includes(item.id)
                  return (
                    <TableRow
                      key={item.id}
                      onClick={() => {
                        setSelectedReportId(item.id)
                        setDetailOpen(true)
                      }}
                      className={`hover:bg-muted/30 transition-colors cursor-pointer ${
                        isSelected ? 'bg-amber-500/5 dark:bg-amber-500/10' : ''
                      }`}
                    >
                      <TableCell className="text-center px-3" onClick={(e) => toggleSelectRow(item.id, e)}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}}
                          className="size-4 rounded border-border text-amber-600 focus:ring-amber-500 cursor-pointer accent-amber-600"
                        />
                      </TableCell>

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

                      {(
                        <TableCell className="text-xs py-3 text-right">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7"
                            disabled={deletingId === item.id}
                            title="Delete this attendance report (development only)"
                            onClick={(e) => {
                              // The row itself opens the detail sheet.
                              e.stopPropagation()
                              handleDelete(item.id, item.occurred_date)
                            }}
                          >
                            <Trash2
                              className={`size-3.5 ${
                                deletingId === item.id
                                  ? 'text-muted-foreground animate-pulse'
                                  : 'text-muted-foreground hover:text-rose-600'
                              }`}
                            />
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination Footer (Matching ExpensesPage pagination footer styling) */}
        <div className="border-t bg-card/40 px-3 py-2 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Rows per page</span>
            <Select
              value={String(pageSize)}
              onValueChange={(val) => {
                setPageSize(Number(val))
                setCurrentPage(1)
              }}
            >
              <SelectTrigger className="h-7 w-16 text-xs font-mono">
                <SelectValue placeholder={String(pageSize)} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="5">5</SelectItem>
                <SelectItem value="10">10</SelectItem>
                <SelectItem value="25">25</SelectItem>
                <SelectItem value="50">50</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-muted-foreground font-mono">
              Page {currentPage} of {totalPages}
            </span>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="sm"
                className="h-7 size-7 p-0"
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => p - 1)}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 size-7 p-0"
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Bulk Action Bar */}
      <BulkActionBar selectedCount={selectedIds.length} onClear={() => setSelectedIds([])}>
        <Button
          variant="outline"
          size="sm"
          onClick={exportCsv}
          className="h-7 text-xs font-semibold gap-1.5"
        >
          <Download className="size-3.5 text-blue-500" />
          Export Selected CSV
        </Button>
      </BulkActionBar>

      {/* Report Detail Sheet */}
      <AttendanceDetailSheet
        reportId={selectedReportId}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />
    </div>
  )
}
