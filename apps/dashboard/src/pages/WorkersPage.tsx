import * as React from 'react'
import {
  Users,
  Search,
  UserPlus,
  HardHat,
  DollarSign,
  UserCheck,
  Building,
  MoreVertical,
  Edit,
  UserX,
  Download,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { fetchWorkersApi, updateWorkerApi, type WorkforceWorkerItem } from '@/lib/api'
import { AddWorkerDialog } from '@/components/workforce/add-worker-dialog'
import { EditWorkerSheet } from '@/components/workforce/edit-worker-sheet'

type SortField = 'name' | 'trade' | 'type' | 'wage' | 'status'
type SortOrder = 'asc' | 'desc'

export default function WorkersPage() {
  const { scope } = useScope()
  const [workers, setWorkers] = React.useState<WorkforceWorkerItem[]>([])
  const [loading, setLoading] = React.useState(true)
  const [search, setSearch] = React.useState('')
  const [statusFilter, setStatusFilter] = React.useState<string>('ALL')
  const [typeFilter, setTypeFilter] = React.useState<string>('ALL')

  // Selection & Bulk Action state
  const [selectedIds, setSelectedIds] = React.useState<string[]>([])

  // Sorting state
  const [sortField, setSortField] = React.useState<SortField>('name')
  const [sortOrder, setSortOrder] = React.useState<SortOrder>('asc')

  // Pagination state
  const [currentPage, setCurrentPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState(10)

  // Modals
  const [addOpen, setAddOpen] = React.useState(false)
  const [selectedWorker, setSelectedWorker] = React.useState<WorkforceWorkerItem | null>(null)
  const [editOpen, setEditOpen] = React.useState(false)

  const loadWorkers = React.useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchWorkersApi({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        search: search.trim() || undefined,
      })
      setWorkers(data.items || [])
    } catch (err) {
      console.warn('Failed to load worker roster:', err)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, search])

  React.useEffect(() => {
    loadWorkers()
  }, [loadWorkers])

  // Handle Sort Toggle
  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortOrder('asc')
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

  // Filtered & Sorted workers
  const filteredWorkers = React.useMemo(() => {
    return workers
      .filter((w) => {
        if (typeFilter !== 'ALL' && w.worker_type !== typeFilter) return false
        return true
      })
      .sort((a, b) => {
        const modifier = sortOrder === 'asc' ? 1 : -1
        if (sortField === 'name') return a.name.localeCompare(b.name) * modifier
        if (sortField === 'trade') return (a.trade || '').localeCompare(b.trade || '') * modifier
        if (sortField === 'type') return a.worker_type.localeCompare(b.worker_type) * modifier
        if (sortField === 'wage') return ((a.default_daily_wage || 0) - (b.default_daily_wage || 0)) * modifier
        if (sortField === 'status') return a.status.localeCompare(b.status) * modifier
        return 0
      })
  }, [workers, typeFilter, sortField, sortOrder])

  // Pagination calculation
  const totalPages = Math.ceil(filteredWorkers.length / pageSize) || 1
  const paginatedWorkers = React.useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredWorkers.slice(start, start + pageSize)
  }, [filteredWorkers, currentPage, pageSize])

  // Bulk Selection Handlers
  const isAllSelected = paginatedWorkers.length > 0 && paginatedWorkers.every((w) => selectedIds.includes(w.id))

  const toggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds([])
    } else {
      setSelectedIds(paginatedWorkers.map((w) => w.id))
    }
  }

  const toggleSelectRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  const handleBulkStatusChange = async (nextStatus: 'active' | 'inactive') => {
    if (!confirm(`Update ${selectedIds.length} selected workers to ${nextStatus.toUpperCase()}?`)) return
    const idsToUpdate = [...selectedIds]
    setSelectedIds([])
    for (const id of idsToUpdate) {
      try {
        await updateWorkerApi(id, { status: nextStatus })
      } catch (err) {
        console.warn(`Failed to update worker ${id}:`, err)
      }
    }
    loadWorkers()
  }

  // Export CSV
  const exportCsv = () => {
    const headers = ['ID', 'Name', 'Trade', 'Worker Type', 'Daily Wage', 'Contractor', 'Status']
    const rows = filteredWorkers.map((w) => [
      w.id,
      `"${w.name}"`,
      `"${w.trade || ''}"`,
      w.worker_type,
      w.default_daily_wage || 0,
      `"${w.contractor || ''}"`,
      w.status,
    ])
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `Worker_Roster_${new Date().toISOString().split('T')[0]}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Derived KPI Metrics
  const activeCount = workers.filter((w) => w.status === 'active').length
  const permanentCount = workers.filter((w) => w.worker_type === 'permanent').length
  const contractorCount = workers.filter((w) => w.worker_type === 'contractor').length
  const avgWage =
    workers.length > 0
      ? Math.round(
          workers.reduce((acc, w) => acc + (w.default_daily_wage || 0), 0) / (workers.length || 1)
        )
      : 0

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Site Labor Roster)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

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
              Worker Roster & Master Registry
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
            onClick={exportCsv}
            className="h-8 gap-1.5 text-xs font-medium"
          >
            <Download className="size-3.5" />
            Export CSV
          </Button>

          <Button
            size="sm"
            onClick={() => setAddOpen(true)}
            className="h-8 gap-1.5 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white shadow-2xs"
          >
            <UserPlus className="size-4" />
            Register Worker
          </Button>
        </div>
      </div>

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Active Workers"
          value={<span className="text-emerald-600 dark:text-emerald-400">{activeCount} Registered</span>}
          trend="up"
          trendValue="Master Roster"
          description="Active site labor"
          icon={<UserCheck className="text-emerald-500" />}
          chartData={[10, 20, 30, 45, 60, 80]}
        />
        <KpiCard
          title="Permanent Staff"
          value={<span className="text-blue-600 dark:text-blue-400">{permanentCount} Workers</span>}
          trend="neutral"
          trendValue="Company Direct"
          description="Direct payroll labor"
          icon={<Users className="text-blue-500" />}
        />
        <KpiCard
          title="Contractor Labor"
          value={<span className="text-purple-600 dark:text-purple-400">{contractorCount} Subcontracted</span>}
          trend="neutral"
          trendValue="Agency Labor"
          description="Subcontractor workers"
          icon={<Building className="text-purple-500" />}
        />
        <KpiCard
          title="Average Daily Wage"
          value={<span className="text-amber-600 dark:text-amber-400">₹{avgWage.toLocaleString('en-IN')}/day</span>}
          trend="up"
          trendValue="Daily Rate"
          description="Average baseline wage"
          icon={<DollarSign className="text-amber-500" />}
        />
      </div>

      {/* Filter & Toolbar (Matching ExpensesPage container styling) */}
      <div className="flex flex-col sm:flex-row gap-2.5 items-center justify-between border border-border/80 p-2.5 rounded-lg bg-card/40">
        <div className="flex flex-wrap gap-2 w-full sm:w-auto flex-1 items-center">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search worker name, trade, contractor..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>

          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-40">
              <SelectValue placeholder="All Worker Types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Worker Types</SelectItem>
              <SelectItem value="permanent">Permanent Staff</SelectItem>
              <SelectItem value="temporary">Temporary Labor</SelectItem>
              <SelectItem value="contractor">Subcontractor</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Status Tab Filter (Matching ExpensesPage status tabs) */}
        <Tabs value={statusFilter} onValueChange={setStatusFilter} className="w-full sm:w-auto">
          <TabsList className="h-9 text-xs grid grid-cols-3 w-full sm:w-auto">
            <TabsTrigger value="ALL" className="text-xs">All</TabsTrigger>
            <TabsTrigger value="active" className="text-xs">Active ({activeCount})</TabsTrigger>
            <TabsTrigger value="inactive" className="text-xs">Retired</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Filter Summary Banner */}
      <div className="flex items-center justify-between text-xs px-1 text-muted-foreground font-medium">
        <div>
          Showing <span className="text-foreground font-semibold">{filteredWorkers.length}</span> of {workers.length} records
        </div>
        {selectedIds.length > 0 && (
          <span className="text-amber-600 font-semibold text-xs">
            {selectedIds.length} items checked
          </span>
        )}
      </div>

      {/* Main Worker Table Container (Matching ExpensesPage table styling) */}
      <div className="border rounded-lg overflow-hidden bg-card shadow-2xs">
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
                onClick={() => toggleSort('name')}
              >
                Worker Name {renderSortIcon('name')}
              </TableHead>

              <TableHead
                className="text-xs font-semibold h-10 cursor-pointer select-none"
                onClick={() => toggleSort('trade')}
              >
                Trade / Skill {renderSortIcon('trade')}
              </TableHead>

              <TableHead
                className="text-xs font-semibold h-10 cursor-pointer select-none"
                onClick={() => toggleSort('type')}
              >
                Worker Type {renderSortIcon('type')}
              </TableHead>

              <TableHead
                className="text-xs font-semibold h-10 text-right cursor-pointer select-none"
                onClick={() => toggleSort('wage')}
              >
                Default Daily Wage {renderSortIcon('wage')}
              </TableHead>

              <TableHead className="text-xs font-semibold h-10">Contractor / Agency</TableHead>

              <TableHead
                className="text-xs font-semibold h-10 text-center cursor-pointer select-none"
                onClick={() => toggleSort('status')}
              >
                Status {renderSortIcon('status')}
              </TableHead>

              <TableHead className="text-xs font-semibold h-10 w-12 text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="h-32 text-center text-xs text-muted-foreground">
                  Loading worker roster...
                </TableCell>
              </TableRow>
            ) : paginatedWorkers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-32 text-center text-xs text-muted-foreground">
                  No workers found matching the current search & status filters.
                </TableCell>
              </TableRow>
            ) : (
              paginatedWorkers.map((item) => {
                const isSelected = selectedIds.includes(item.id)
                return (
                  <TableRow
                    key={item.id}
                    className={`hover:bg-muted/30 transition-colors ${
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
                      <div className="flex items-center gap-2.5">
                        <div className="size-7 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 flex items-center justify-center font-bold text-xs shrink-0">
                          {item.name.charAt(0)}
                        </div>
                        <span className="truncate">{item.name}</span>
                      </div>
                    </TableCell>

                    <TableCell className="text-xs py-3">
                      <Badge variant="outline" className="font-sans text-[11px] bg-card">
                        {item.trade || 'General Labor'}
                      </Badge>
                    </TableCell>

                    <TableCell className="text-xs py-3">
                      <Badge
                        variant="outline"
                        className={
                          item.worker_type === 'permanent'
                            ? 'border-blue-500/30 text-blue-600 bg-blue-500/10 text-[10px]'
                            : item.worker_type === 'contractor'
                            ? 'border-purple-500/30 text-purple-600 bg-purple-500/10 text-[10px]'
                            : 'border-amber-500/30 text-amber-600 bg-amber-500/10 text-[10px]'
                        }
                      >
                        {item.worker_type.toUpperCase()}
                      </Badge>
                    </TableCell>

                    <TableCell className="text-xs py-3 text-right font-mono font-bold text-foreground">
                      {item.default_daily_wage ? `₹${item.default_daily_wage.toLocaleString('en-IN')}` : '—'}
                    </TableCell>

                    <TableCell className="text-xs py-3 text-muted-foreground">
                      {item.contractor || 'Direct Payroll'}
                    </TableCell>

                    <TableCell className="text-xs py-3 text-center">
                      <Badge
                        variant="outline"
                        className={
                          item.status === 'active'
                            ? 'border-emerald-500/30 text-emerald-600 bg-emerald-500/10 text-[10px]'
                            : 'border-slate-500/30 text-slate-500 bg-slate-500/10 text-[10px]'
                        }
                      >
                        {item.status.toUpperCase()}
                      </Badge>
                    </TableCell>

                    <TableCell className="text-xs py-3 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="size-7">
                            <MoreVertical className="size-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="text-xs">
                          <DropdownMenuItem
                            onClick={() => {
                              setSelectedWorker(item)
                              setEditOpen(true)
                            }}
                          >
                            <Edit className="size-3.5 mr-2 text-amber-500" />
                            Edit Profile
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => {
                              setSelectedWorker(item)
                              setEditOpen(true)
                            }}
                            className={item.status === 'active' ? 'text-red-600' : 'text-emerald-600'}
                          >
                            {item.status === 'active' ? (
                              <>
                                <UserX className="size-3.5 mr-2" /> Retire Worker
                              </>
                            ) : (
                              <>
                                <UserCheck className="size-3.5 mr-2" /> Reactivate Worker
                              </>
                            )}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>

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
          onClick={() => handleBulkStatusChange('inactive')}
          className="h-7 text-xs font-semibold gap-1.5 text-red-600 border-red-500/40 hover:bg-red-500/10"
        >
          <UserX className="size-3.5" />
          Retire Selected
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => handleBulkStatusChange('active')}
          className="h-7 text-xs font-semibold gap-1.5 text-emerald-600 border-emerald-500/40 hover:bg-emerald-500/10"
        >
          <UserCheck className="size-3.5" />
          Reactivate Selected
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={exportCsv}
          className="h-7 text-xs font-semibold gap-1.5"
        >
          <Download className="size-3.5" />
          Export Selected CSV
        </Button>
      </BulkActionBar>

      {/* Modals */}
      <AddWorkerDialog open={addOpen} onOpenChange={setAddOpen} onSuccess={loadWorkers} />
      <EditWorkerSheet
        worker={selectedWorker}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSuccess={loadWorkers}
      />
    </div>
  )
}
