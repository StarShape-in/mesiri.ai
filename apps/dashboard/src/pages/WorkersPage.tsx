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
} from 'lucide-react'
import { KpiCard } from '@/components/ui/kpi-card'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { fetchWorkersApi, type WorkforceWorkerItem } from '@/lib/api'
import { AddWorkerDialog } from '@/components/workforce/add-worker-dialog'
import { EditWorkerSheet } from '@/components/workforce/edit-worker-sheet'

export default function WorkersPage() {
  const [workers, setWorkers] = React.useState<WorkforceWorkerItem[]>([])
  const [loading, setLoading] = React.useState(true)
  const [search, setSearch] = React.useState('')
  const [statusFilter, setStatusFilter] = React.useState<string>('active')
  const [typeFilter, setTypeFilter] = React.useState<string>('all')

  // Modals
  const [addOpen, setAddOpen] = React.useState(false)
  const [selectedWorker, setSelectedWorker] = React.useState<WorkforceWorkerItem | null>(null)
  const [editOpen, setEditOpen] = React.useState(false)

  const loadWorkers = React.useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchWorkersApi({
        status: statusFilter === 'all' ? undefined : statusFilter,
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

  // Filter client-side by worker_type if set
  const filteredWorkers = React.useMemo(() => {
    return workers.filter((w) => {
      if (typeFilter !== 'all' && w.worker_type !== typeFilter) return false
      return true
    })
  }, [workers, typeFilter])

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
            <p className="text-xs text-muted-foreground font-medium">
              Manage organization site workers, trade skills, default daily wages, and subcontractor listings.
            </p>
          </div>
        </div>

        <Button
          onClick={() => setAddOpen(true)}
          className="bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs gap-1.5 shadow-2xs self-start sm:self-auto"
        >
          <UserPlus className="size-4" />
          Register Worker
        </Button>
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

      {/* Controls Toolbar */}
      <Card className="p-3 border shadow-2xs flex flex-col sm:flex-row gap-3 items-center justify-between bg-card">
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto items-center">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search worker name, trade, contractor..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="w-full sm:w-40 h-9 rounded-md border border-input bg-background px-3 py-1 text-xs font-sans ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <option value="all">All Worker Types</option>
            <option value="permanent">Permanent Staff</option>
            <option value="temporary">Temporary Labor</option>
            <option value="contractor">Subcontractor</option>
          </select>
        </div>

        <div className="flex items-center gap-1.5 bg-muted/60 p-1 rounded-lg border w-full sm:w-auto justify-center">
          <button
            onClick={() => setStatusFilter('active')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              statusFilter === 'active'
                ? 'bg-background text-foreground shadow-2xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Active ({activeCount})
          </button>
          <button
            onClick={() => setStatusFilter('inactive')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              statusFilter === 'inactive'
                ? 'bg-background text-foreground shadow-2xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Retired
          </button>
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
              statusFilter === 'all'
                ? 'bg-background text-foreground shadow-2xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            All
          </button>
        </div>
      </Card>

      {/* Worker Roster Table */}
      <Card className="border shadow-2xs overflow-hidden bg-card">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent border-b">
              <TableHead className="text-xs font-semibold h-10">Worker Name</TableHead>
              <TableHead className="text-xs font-semibold h-10">Trade / Skill</TableHead>
              <TableHead className="text-xs font-semibold h-10">Worker Type</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-right">Default Daily Wage</TableHead>
              <TableHead className="text-xs font-semibold h-10">Contractor / Agency</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-center">Status</TableHead>
              <TableHead className="text-xs font-semibold h-10 w-12 text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                  Loading worker roster...
                </TableCell>
              </TableRow>
            ) : filteredWorkers.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-xs text-muted-foreground">
                  No workers found matching the current search & status filters.
                </TableCell>
              </TableRow>
            ) : (
              filteredWorkers.map((item) => (
                <TableRow key={item.id} className="hover:bg-muted/30 transition-colors">
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
              ))
            )}
          </TableBody>
        </Table>
      </Card>

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
