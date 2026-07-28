import * as React from 'react'
import {
  ShieldAlert,
  Search,
  Filter,
  Plus,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Check,
  List,
  LayoutGrid,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import {
  fetchSiteIssuesApi,
  createSiteIssueApi,
  resolveSiteIssueApi,
  type SiteIssueItem,
} from '@/lib/api'
import { KpiCard } from '@/components/ui/kpi-card'
import { useToast } from '@/components/ui/toast-notification'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { cn } from '@/lib/utils'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getSeverityBadge(severity: string) {
  switch (severity.toUpperCase()) {
    case 'CRITICAL':
      return <Badge variant="destructive" className="font-bold text-[10px] uppercase">CRITICAL</Badge>
    case 'HIGH':
      return <Badge variant="outline" className="border-rose-500/40 text-rose-600 dark:text-rose-400 font-bold text-[10px] uppercase">HIGH</Badge>
    case 'MEDIUM':
      return <Badge variant="outline" className="border-amber-500/40 text-amber-600 dark:text-amber-400 font-bold text-[10px] uppercase">MEDIUM</Badge>
    default:
      return <Badge variant="secondary" className="font-bold text-[10px] uppercase">LOW</Badge>
  }
}

function getStatusBadge(status: string) {
  switch (status.toUpperCase()) {
    case 'RESOLVED':
      return <Badge variant="outline" className="border-emerald-500/40 text-emerald-600 dark:text-emerald-400 font-bold text-[10px] uppercase gap-1"><Check className="size-3" /> RESOLVED</Badge>
    case 'INVESTIGATING':
      return <Badge variant="outline" className="border-sky-500/40 text-sky-600 dark:text-sky-400 font-bold text-[10px] uppercase">INVESTIGATING</Badge>
    case 'BLOCKED':
      return <Badge variant="destructive" className="font-bold text-[10px] uppercase">BLOCKED</Badge>
    default:
      return <Badge variant="outline" className="border-amber-500/40 text-amber-600 dark:text-amber-400 font-bold text-[10px] uppercase">OPEN</Badge>
  }
}

// ─── Main Operations Issues Page ───────────────────────────────────────────────

export default function OperationsIssuesPage() {
  const { scope } = useScope()
  const toast = useToast()

  const [issues, setIssues] = React.useState<SiteIssueItem[]>([])
  const [loading, setLoading] = React.useState<boolean>(true)

  // Filters
  const [searchQuery, setSearchQuery] = React.useState<string>('')
  const [statusFilter, setStatusFilter] = React.useState<string>('ALL')
  const [severityFilter, setSeverityFilter] = React.useState<string>('ALL')
  const [viewMode, setViewMode] = React.useState<'table' | 'grid'>('table')

  // Modals
  const [createDialogOpen, setCreateDialogOpen] = React.useState<boolean>(false)
  const [resolveDialogOpen, setResolveDialogOpen] = React.useState<boolean>(false)
  const [selectedIssue, setSelectedIssue] = React.useState<SiteIssueItem | null>(null)
  const [inspectSheetOpen, setInspectSheetOpen] = React.useState<boolean>(false)

  // Form states
  const [newIssueType, setNewIssueType] = React.useState<string>('SITE_BLOCKER')
  const [newSeverity, setNewSeverity] = React.useState<string>('MEDIUM')
  const [newNarrative, setNewNarrative] = React.useState<string>('')
  const [newDelayMins, setNewDelayMins] = React.useState<string>('30')
  const [submitting, setSubmitting] = React.useState<boolean>(false)
  const [resolutionNotes, setResolutionNotes] = React.useState<string>('')

  const activeProjectId = React.useMemo(() => {
    return scope.mode !== 'portfolio' ? scope.projectId : undefined
  }, [scope])

  const activeSiteId = React.useMemo(() => {
    return scope.mode === 'site' ? scope.siteId : undefined
  }, [scope])

  const scopeFilter = React.useMemo(() => ({
    projectId: activeProjectId,
    siteId: activeSiteId,
  }), [activeProjectId, activeSiteId])

  const loadIssues = React.useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchSiteIssuesApi({
        projectId: scopeFilter.projectId,
        siteId: scopeFilter.siteId,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        severity: severityFilter !== 'ALL' ? severityFilter : undefined,
        limit: 100,
      })
      setIssues(res.items || [])
    } catch {
      setIssues([])
    } finally {
      setLoading(false)
    }
  }, [scopeFilter, statusFilter, severityFilter])

  React.useEffect(() => {
    loadIssues()
  }, [loadIssues])

  // Filtered client side search
  const filteredIssues = React.useMemo(() => {
    return issues.filter((item) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const match =
          item.issue_type.toLowerCase().includes(q) ||
          (item.narrative || '').toLowerCase().includes(q) ||
          (item.resolution_notes || '').toLowerCase().includes(q)
        if (!match) return false
      }
      return true
    })
  }, [issues, searchQuery])

  // KPI Metrics
  const stats = React.useMemo(() => {
    const total = issues.length
    const openCount = issues.filter((i) => i.status.toUpperCase() !== 'RESOLVED').length
    const criticalCount = issues.filter((i) => i.severity.toUpperCase() === 'CRITICAL' || i.severity.toUpperCase() === 'HIGH').length
    const totalMinsLost = issues.reduce((acc, i) => acc + (i.delay_duration_minutes || 0), 0)

    return { total, openCount, criticalCount, totalMinsLost }
  }, [issues])

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Projects)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  const handleCreateIssue = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeProjectId || !activeSiteId) {
      toast.error('Project & Site Scope Required', 'Please select a specific Site scope in the header scope switcher before creating an issue.')
      return
    }

    setSubmitting(true)
    try {
      await createSiteIssueApi({
        project_id: activeProjectId,
        site_id: activeSiteId,
        issue_type: newIssueType,
        severity: newSeverity,
        narrative: newNarrative,
        delay_duration_minutes: parseInt(newDelayMins, 10) || 0,
      })
      toast.success('Site Blocker Reported', 'Issue successfully recorded in database and assigned to site team.')
      setCreateDialogOpen(false)
      setNewNarrative('')
      loadIssues()
    } catch {
      toast.error('Failed to Create Issue', 'Could not record site issue. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleResolveIssue = async () => {
    if (!selectedIssue) return
    setSubmitting(true)
    try {
      await resolveSiteIssueApi(selectedIssue.id, resolutionNotes)
      toast.success('Blocker Resolved', `Issue ${selectedIssue.id.slice(0, 8)} marked as RESOLVED.`)
      setResolveDialogOpen(false)
      setSelectedIssue(null)
      setResolutionNotes('')
      loadIssues()
    } catch {
      toast.error('Resolution Failed', 'Could not resolve issue. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-12">

      {/* ── Page Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg border border-rose-500/30 bg-rose-500/10 flex items-center justify-center text-rose-600 dark:text-rose-400 shrink-0 shadow-2xs">
            <ShieldAlert className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Site Issues & Blockers
              <Badge variant="outline" className="text-[10px] font-mono border-rose-500/30 text-rose-600 dark:text-rose-400">
                Live Backend Ledger
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            className="h-8 gap-1.5 text-xs font-bold bg-rose-600 text-white hover:bg-rose-700 shadow-2xs"
            onClick={() => setCreateDialogOpen(true)}
          >
            <Plus className="size-3.5" />
            Report New Blocker
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={loadIssues}
            disabled={loading}
            className="h-8 gap-1.5 text-xs"
          >
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {/* ── Executive KPI Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Active Site Blockers"
          value={<span className="text-rose-600 dark:text-rose-400">{stats.openCount}</span>}
          trend={stats.openCount > 0 ? 'down' : 'up'}
          trendValue={`${stats.openCount} Open`}
          description="Unresolved site interruptions"
          icon={<ShieldAlert className="text-rose-500" />}
          chartData={[3, 5, 4, 6, 8, 5, 4, stats.openCount]}
        />
        <KpiCard
          title="High & Critical Incidents"
          value={<span className="text-amber-600 dark:text-amber-400">{stats.criticalCount}</span>}
          trend="neutral"
          trendValue="Requires Priority"
          description="High severity bottlenecks"
          icon={<AlertTriangle className="text-amber-500" />}
          chartData={[1, 2, 1, 3, 2, 4, 3, stats.criticalCount]}
        />
        <KpiCard
          title="Total Delay Duration"
          value={<span className="text-sky-600 dark:text-sky-400">{stats.totalMinsLost}m</span>}
          trend="down"
          trendValue="Minutes Lost"
          description="Work hours lost to blockers"
          icon={<Clock className="text-sky-500" />}
          chartData={[45, 90, 120, 150, 180, 210, stats.totalMinsLost]}
        />
        <KpiCard
          title="Total Recorded Issues"
          value={<span className="text-indigo-600 dark:text-indigo-400">{stats.total}</span>}
          trend="up"
          trendValue="Historical Total"
          description="Tracked site issue entries"
          icon={<CheckCircle2 className="text-indigo-500" />}
          chartData={[2, 4, 6, 8, 10, 12, stats.total]}
        />
      </div>

      {/* ── Toolbar: Search & Filters ── */}
      <div className="flex flex-col sm:flex-row gap-2.5 items-center justify-between border border-border/80 p-2.5 rounded-lg bg-card/40">
        <div className="flex flex-wrap gap-2 w-full sm:w-auto flex-1 items-center">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search narrative, issue type..."
              value={searchQuery}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>

          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-36">
              <Filter className="size-3.5 mr-1.5 text-muted-foreground shrink-0" />
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Statuses</SelectItem>
              <SelectItem value="OPEN">OPEN</SelectItem>
              <SelectItem value="INVESTIGATING">INVESTIGATING</SelectItem>
              <SelectItem value="RESOLVED">RESOLVED</SelectItem>
            </SelectContent>
          </Select>

          <Select value={severityFilter} onValueChange={setSeverityFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-36">
              <SelectValue placeholder="All Severities" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Severities</SelectItem>
              <SelectItem value="CRITICAL">CRITICAL</SelectItem>
              <SelectItem value="HIGH">HIGH</SelectItem>
              <SelectItem value="MEDIUM">MEDIUM</SelectItem>
              <SelectItem value="LOW">LOW</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-1 border border-border/80 rounded-md p-0.5 bg-background shrink-0">
          <Button
            variant={viewMode === 'table' ? 'secondary' : 'ghost'}
            size="sm"
            className="h-7 px-2.5 text-xs font-semibold gap-1"
            onClick={() => setViewMode('table')}
          >
            <List className="size-3.5" />
            Table
          </Button>
          <Button
            variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
            size="sm"
            className="h-7 px-2.5 text-xs font-semibold gap-1"
            onClick={() => setViewMode('grid')}
          >
            <LayoutGrid className="size-3.5" />
            Grid
          </Button>
        </div>
      </div>

      {/* ── Table or Grid View ── */}
      {filteredIssues.length === 0 ? (
        <Card className="p-12 text-center flex flex-col items-center justify-center gap-3">
          <div className="size-12 rounded-full bg-muted border flex items-center justify-center">
            <ShieldAlert className="size-5 text-muted-foreground/50" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">No site issues recorded in database</p>
            <p className="text-xs text-muted-foreground mt-1">Issues will appear live when reported via WhatsApp or web dashboard.</p>
          </div>
          <Button
            size="sm"
            className="h-8 gap-1.5 text-xs font-bold bg-rose-600 text-white hover:bg-rose-700 mt-1"
            onClick={() => setCreateDialogOpen(true)}
          >
            <Plus className="size-3.5" />
            Report First Issue
          </Button>
        </Card>
      ) : viewMode === 'table' ? (
        <Card className="rounded-lg border-border/80 overflow-hidden shadow-2xs">
          <Table>
            <TableHeader className="bg-muted/30">
              <TableRow>
                <TableHead className="w-24 text-xs font-bold">Issue Type</TableHead>
                <TableHead className="text-xs font-bold">Severity</TableHead>
                <TableHead className="text-xs font-bold">Narrative Description</TableHead>
                <TableHead className="text-xs font-bold">Delay Duration</TableHead>
                <TableHead className="text-xs font-bold">Occurred At</TableHead>
                <TableHead className="text-xs font-bold">Status</TableHead>
                <TableHead className="text-right text-xs font-bold">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="text-xs">
              {filteredIssues.map((item) => (
                <TableRow key={item.id} className="hover:bg-muted/20">
                  <TableCell className="font-mono font-bold">{item.issue_type}</TableCell>
                  <TableCell>{getSeverityBadge(item.severity)}</TableCell>
                  <TableCell className="max-w-md truncate font-medium text-foreground">
                    {item.narrative || 'No description provided'}
                  </TableCell>
                  <TableCell className="font-mono font-semibold text-sky-600">
                    {item.delay_duration_minutes ? `${item.delay_duration_minutes} mins` : '—'}
                  </TableCell>
                  <TableCell className="font-mono text-muted-foreground">
                    {new Date(item.occurred_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>{getStatusBadge(item.status)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs px-2 gap-1 text-indigo-600 hover:text-indigo-700"
                        onClick={() => {
                          setSelectedIssue(item)
                          setInspectSheetOpen(true)
                        }}
                      >
                        Inspect
                      </Button>
                      {item.status.toUpperCase() !== 'RESOLVED' && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs px-2 gap-1 border-emerald-500/40 text-emerald-600 hover:bg-emerald-500/10"
                          onClick={() => {
                            setSelectedIssue(item)
                            setResolveDialogOpen(true)
                          }}
                        >
                          <Check className="size-3" />
                          Resolve
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredIssues.map((item) => (
            <Card key={item.id} className="rounded-lg border-border/80 p-4 space-y-3 shadow-2xs hover:border-rose-500/40 transition-all">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="font-mono font-bold text-xs text-foreground block">{item.issue_type}</span>
                  <span className="text-[11px] text-muted-foreground font-mono">ID: {item.id.slice(0, 8)}</span>
                </div>
                {getSeverityBadge(item.severity)}
              </div>

              <p className="text-xs text-foreground font-medium leading-relaxed">
                {item.narrative || 'No narrative recorded'}
              </p>

              <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-2 border-t font-mono">
                <span>{getStatusBadge(item.status)}</span>
                {item.status.toUpperCase() !== 'RESOLVED' && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-6 text-[10px] px-2 border-emerald-500/40 text-emerald-600 hover:bg-emerald-500/10"
                    onClick={() => {
                      setSelectedIssue(item)
                      setResolveDialogOpen(true)
                    }}
                  >
                    Resolve
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* ── Report Issue Dialog ── */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={handleCreateIssue}>
            <DialogHeader>
              <DialogTitle className="text-base font-bold flex items-center gap-2">
                <ShieldAlert className="size-5 text-rose-600" />
                Report Site Blocker / Issue
              </DialogTitle>
              <DialogDescription className="text-xs">
                Record an operational issue or site delay for audit & resolution.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3.5 py-4 text-xs">
              <div className="space-y-1">
                <label className="font-bold text-foreground">Issue Type</label>
                <Select value={newIssueType} onValueChange={setNewIssueType}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="SITE_BLOCKER">SITE_BLOCKER</SelectItem>
                    <SelectItem value="WEATHER_INTERRUPTION">WEATHER_INTERRUPTION</SelectItem>
                    <SelectItem value="EQUIPMENT_BREAKDOWN">EQUIPMENT_BREAKDOWN</SelectItem>
                    <SelectItem value="MATERIAL_SHORTAGE">MATERIAL_SHORTAGE</SelectItem>
                    <SelectItem value="LABOUR_SHORTAGE">LABOUR_SHORTAGE</SelectItem>
                    <SelectItem value="SAFETY_HAZARD">SAFETY_HAZARD</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="font-bold text-foreground">Severity</label>
                  <Select value={newSeverity} onValueChange={setNewSeverity}>
                    <SelectTrigger className="h-9 text-xs">
                      <SelectValue placeholder="Severity" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="LOW">LOW</SelectItem>
                      <SelectItem value="MEDIUM">MEDIUM</SelectItem>
                      <SelectItem value="HIGH">HIGH</SelectItem>
                      <SelectItem value="CRITICAL">CRITICAL</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1">
                  <label className="font-bold text-foreground">Delay (Minutes)</label>
                  <Input
                    type="number"
                    value={newDelayMins}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewDelayMins(e.target.value)}
                    className="h-9 text-xs font-mono"
                    placeholder="30"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-bold text-foreground">Narrative Description</label>
                <textarea
                  value={newNarrative}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setNewNarrative(e.target.value)}
                  placeholder="Describe the cause of delay, affected location, and equipment involved..."
                  className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-24"
                />
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateDialogOpen(false)} className="h-8 text-xs">
                Cancel
              </Button>
              <Button type="submit" disabled={submitting} className="h-8 text-xs font-bold bg-rose-600 text-white hover:bg-rose-700">
                {submitting ? 'Reporting...' : 'Submit Blocker Report'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ── Resolve Issue Dialog ── */}
      <Dialog open={resolveDialogOpen} onOpenChange={setResolveDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-bold flex items-center gap-2">
              <CheckCircle2 className="size-5 text-emerald-600" />
              Resolve Site Blocker
            </DialogTitle>
            <DialogDescription className="text-xs">
              Mark issue {selectedIssue?.id.slice(0, 8)} as RESOLVED.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-3 text-xs">
            <div className="p-3 rounded-lg bg-muted/20 border text-muted-foreground">
              <strong>Narrative:</strong> {selectedIssue?.narrative || 'No narrative provided'}
            </div>

            <div className="space-y-1">
              <label className="font-bold text-foreground">Resolution Notes</label>
              <textarea
                value={resolutionNotes}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setResolutionNotes(e.target.value)}
                placeholder="Explain how the blocker was cleared (e.g. Pump replaced, weather cleared)..."
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-xs shadow-2xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring min-h-20"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setResolveDialogOpen(false)} className="h-8 text-xs">
              Cancel
            </Button>
            <Button disabled={submitting} onClick={handleResolveIssue} className="h-8 text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700">
              {submitting ? 'Resolving...' : 'Confirm Resolution'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Inspection Sheet ── */}
      <Sheet open={inspectSheetOpen} onOpenChange={setInspectSheetOpen}>
        <SheetContent className="sm:max-w-md overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="text-sm font-bold flex items-center gap-2">
              <ShieldAlert className="size-4 text-rose-600" />
              {selectedIssue?.issue_type}
            </SheetTitle>
            <SheetDescription className="text-[11px]">
              ID: {selectedIssue?.id}
            </SheetDescription>
          </SheetHeader>

          <div className="space-y-4 pt-4 text-xs">
            <div className="p-3 rounded-lg border bg-muted/10 space-y-1">
              <span className="font-bold block">Description</span>
              <p className="text-muted-foreground leading-relaxed">{selectedIssue?.narrative || 'No description'}</p>
            </div>

            {selectedIssue?.resolution_notes && (
              <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 space-y-1">
                <span className="font-bold text-emerald-700 dark:text-emerald-300 block">Resolution Notes</span>
                <p className="text-emerald-900 dark:text-emerald-200">{selectedIssue.resolution_notes}</p>
              </div>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}
