import * as React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Building2,
  AlertTriangle,
  ChevronRight,
  Loader2,
  Search,
  Settings2,
  Activity,
  History,
  CheckCircle2,
  RotateCcw,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/lib/AuthContext'
import { fetchProjectsFull, type Project } from '@/lib/projects'
import { fetchTodayFieldActivity, fetchPortfolioTimeline } from '@/lib/portfolio'
import { timeAgo, cn } from '@/lib/utils'
import { FIELD_ACTIVITY_META, describeEventType, statusBadgeClass } from '@/lib/field-activity'

function isActiveProject(p: Project) {
  return p.status !== 'archived' && p.status !== 'on_hold' && p.status !== 'neutral'
}

export function PortfolioOverview() {
  const { me } = useAuth()
  const navigate = useNavigate()

  const [search, setSearch] = React.useState('')
  const [statusFilter, setStatusFilter] = React.useState('ALL')
  const [onlyWithIssues, setOnlyWithIssues] = React.useState(false)

  const {
    data: projects = [],
    isLoading: isProjectsLoading,
    isError: isProjectsError,
    refetch: refetchProjects,
  } = useQuery<Project[]>({
    queryKey: ['projects-list'],
    queryFn: fetchProjectsFull,
    staleTime: 30_000,
  })

  const {
    data: fieldActivity,
    isLoading: isFieldActivityLoading,
    isError: isFieldActivityError,
    refetch: refetchFieldActivity,
  } = useQuery({
    queryKey: ['portfolio-field-activity-today'],
    queryFn: () => fetchTodayFieldActivity(),
    staleTime: 60_000,
  })

  const {
    data: timeline,
    isLoading: isTimelineLoading,
    isError: isTimelineError,
    refetch: refetchTimeline,
  } = useQuery({
    queryKey: ['portfolio-timeline-recent'],
    queryFn: () => fetchPortfolioTimeline(50),
    staleTime: 30_000,
  })

  const nonArchived = React.useMemo(() => projects.filter((p) => p.status !== 'archived'), [projects])

  const stats = React.useMemo(
    () => ({
      total: nonArchived.length,
      active: nonArchived.filter(isActiveProject).length,
      openIssues: nonArchived.reduce((sum, p) => sum + (p.openIssues || 0), 0),
    }),
    [nonArchived]
  )

  const attentionItems = React.useMemo(
    () =>
      nonArchived
        .filter((p) => p.openIssues > 0)
        .sort((a, b) => b.openIssues - a.openIssues)
        .slice(0, 4),
    [nonArchived]
  )

  // Last activity per project, derived client-side from a single bounded
  // org-wide timeline fetch — avoids an N+1 request-per-project pattern.
  const lastActivityByProject = React.useMemo(() => {
    const map = new Map<string, string>()
    for (const entry of timeline ?? []) {
      if (!entry.projectId) continue
      if (!map.has(entry.projectId)) map.set(entry.projectId, entry.occurredAt)
    }
    return map
  }, [timeline])

  const projectNameById = React.useMemo(() => {
    const map = new Map<string, string>()
    for (const p of projects) map.set(p.id, p.name)
    return map
  }, [projects])

  const filteredProjects = React.useMemo(() => {
    return nonArchived
      .filter((p) => {
        const matchSearch =
          !search ||
          p.name.toLowerCase().includes(search.toLowerCase()) ||
          (p.code && p.code.toLowerCase().includes(search.toLowerCase())) ||
          (p.client && p.client.toLowerCase().includes(search.toLowerCase()))
        if (!matchSearch) return false
        if (statusFilter !== 'ALL') {
          if (statusFilter === 'active' && !isActiveProject(p)) return false
          if (statusFilter === 'on_hold' && p.status !== 'on_hold' && p.status !== 'neutral') return false
        }
        if (onlyWithIssues && p.openIssues <= 0) return false
        return true
      })
      .sort((a, b) => b.openIssues - a.openIssues || a.name.localeCompare(b.name))
  }, [nonArchived, search, statusFilter, onlyWithIssues])

  const openProject = (projectId: string) => navigate(`/overview?project=${projectId}`)

  const isAdmin = me?.role === 'ADMIN'

  if (isProjectsLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (isProjectsError) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center text-sm">
        <AlertTriangle className="size-8 text-rose-500" />
        <p className="text-muted-foreground">Failed to load the portfolio. Please try again.</p>
        <Button size="sm" variant="outline" onClick={() => refetchProjects()} className="gap-1.5">
          <RotateCcw className="size-3.5" />
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Portfolio Context Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-4">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <Building2 className="size-5 text-blue-500 dark:text-blue-400" />
            <h1 className="text-lg font-bold text-foreground leading-tight">Portfolio Overview</h1>
          </div>
          <p className="text-xs text-muted-foreground font-semibold">
            All Projects · All Sites
            {me?.organization_name ? ` · ${me.organization_name}` : ''}
            {` · ${stats.total} Project${stats.total === 1 ? '' : 's'}`}
          </p>
        </div>
        {isAdmin && (
          <Button variant="outline" size="sm" asChild className="h-7 text-xs font-bold gap-1.5 w-fit">
            <Link to="/projects">
              <Settings2 className="size-3.5" />
              Manage Projects
            </Link>
          </Button>
        )}
      </div>

      {/* Attention Required */}
      <Card className="rounded-md border-border/70 shadow-xs overflow-hidden border-l-4 border-l-rose-500">
        <CardHeader className="pb-2 border-b bg-rose-500/[0.01]">
          <CardTitle className="text-xs uppercase tracking-wider text-rose-600 dark:text-rose-400 font-bold flex items-center gap-1.5">
            <AlertTriangle className="size-4" />
            Attention Required
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-3 text-xs">
          {attentionItems.length === 0 ? (
            <div className="flex items-center gap-2 py-2 text-muted-foreground">
              <CheckCircle2 className="size-4 text-emerald-500" />
              No open issues across the portfolio right now.
            </div>
          ) : (
            <div className="divide-y divide-border/40">
              {attentionItems.map((p) => (
                <div
                  key={p.id}
                  onClick={() => openProject(p.id)}
                  className="flex items-start justify-between py-2.5 first:pt-0 last:pb-0 cursor-pointer group hover:text-primary transition-all"
                >
                  <div className="space-y-0.5">
                    <h4 className="font-bold text-foreground group-hover:text-primary transition-colors">
                      {p.openIssues} Open Issue{p.openIssues === 1 ? '' : 's'} · {p.name}
                    </h4>
                    <p className="text-muted-foreground font-medium">
                      {p.code || 'NO-CODE'} · {p.client || 'No Client'}
                    </p>
                  </div>
                  <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-primary transition-colors self-center" />
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Portfolio Snapshot */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
        <SnapshotStat label="Total Projects" value={stats.total} />
        <SnapshotStat label="Active Projects" value={stats.active} />
        <SnapshotStat
          label="Open Issues"
          value={stats.openIssues}
          tone={stats.openIssues > 0 ? 'warning' : 'neutral'}
        />
        {!isFieldActivityLoading && !isFieldActivityError && (
          <SnapshotStat
            label="Field Updates Today"
            value={(fieldActivity ?? []).reduce((sum, i) => sum + i.count, 0)}
          />
        )}
      </div>

      {/* Projects (primary section) */}
      <Card className="rounded-md border-border/70 shadow-xs overflow-hidden">
        <CardHeader className="pb-3 border-b flex flex-col gap-3">
          <div className="flex flex-row items-center justify-between gap-4">
            <div>
              <CardTitle className="text-sm font-bold text-foreground">Projects</CardTitle>
              <CardDescription className="text-xs">
                {stats.active} Active Project{stats.active === 1 ? '' : 's'} · {stats.total} Total
              </CardDescription>
            </div>
          </div>
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search project, code, client..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-8 text-xs"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-[150px] h-8 text-xs">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All Statuses</SelectItem>
                <SelectItem value="active">Active Only</SelectItem>
                <SelectItem value="on_hold">On Hold</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant={onlyWithIssues ? 'default' : 'outline'}
              size="sm"
              className="h-8 text-xs font-semibold shrink-0"
              onClick={() => setOnlyWithIssues((v) => !v)}
            >
              Has Open Issues
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-4 text-xs">
          {filteredProjects.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground italic">
              No projects match the current search or filter.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="font-bold text-foreground">Project</TableHead>
                    <TableHead className="font-bold text-foreground">Status</TableHead>
                    <TableHead className="font-bold text-foreground">Open Issues</TableHead>
                    <TableHead className="font-bold text-foreground hidden md:table-cell">
                      Last Activity
                    </TableHead>
                    <TableHead className="font-bold text-foreground text-right pr-4">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredProjects.map((p) => {
                    const lastActivity = lastActivityByProject.get(p.id)
                    return (
                      <TableRow
                        key={p.id}
                        onClick={() => openProject(p.id)}
                        className="hover:bg-muted/30 transition-colors cursor-pointer"
                      >
                        <TableCell className="py-2.5">
                          <div className="flex flex-col">
                            <span className="font-semibold text-foreground text-sm">{p.name}</span>
                            <span className="text-[10px] text-muted-foreground font-mono">
                              {p.code || 'NO-CODE'} · {p.client || 'No Client'}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="py-2.5">
                          <Badge variant="outline" className={cn('text-xs rounded-sm py-0.5 font-semibold', statusBadgeClass(p.status))}>
                            {p.statusLabel || p.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="py-2.5">
                          {p.openIssues > 0 ? (
                            <Badge variant="outline" className="text-xs rounded-sm py-0.5 font-semibold bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20">
                              {p.openIssues}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">0</span>
                          )}
                        </TableCell>
                        <TableCell className="py-2.5 hidden md:table-cell text-muted-foreground">
                          {lastActivity ? (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span>{timeAgo(lastActivity)}</span>
                              </TooltipTrigger>
                              <TooltipContent>{new Date(lastActivity).toLocaleString()}</TooltipContent>
                            </Tooltip>
                          ) : (
                            <span className="italic">No recent activity</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right pr-4 py-2.5" onClick={(e) => e.stopPropagation()}>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-6 text-[11px] font-bold rounded-md px-2.5"
                            onClick={() => openProject(p.id)}
                          >
                            Open Project
                          </Button>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Today's Field Activity */}
      {!isFieldActivityError && (isFieldActivityLoading || (fieldActivity && fieldActivity.length >= 0)) && (
        <Card className="rounded-md border-border/70 shadow-xs overflow-hidden">
          <CardHeader className="pb-3 border-b border-l-3 border-l-sky-500">
            <CardTitle className="text-xs uppercase tracking-wider text-sky-600 dark:text-sky-400 font-bold">
              Today's Field Activity
            </CardTitle>
            <CardDescription className="text-xs">Cross-project activity recorded today.</CardDescription>
          </CardHeader>
          <CardContent className="pt-4 text-xs">
            {isFieldActivityLoading ? (
              <div className="flex justify-center p-6">
                <Loader2 className="size-4 animate-spin text-primary" />
              </div>
            ) : !fieldActivity || fieldActivity.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground italic">
                No field activity recorded today.
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
                {fieldActivity.map((item) => {
                  const meta = FIELD_ACTIVITY_META[item.eventType]
                  const Icon = meta?.icon ?? Activity
                  return (
                    <Link
                      key={item.eventType}
                      to={`/operations/daily-reports${meta ? `?type=${meta.slug}` : ''}`}
                      className="flex items-center justify-between p-3 border border-border/50 rounded-md hover:border-sky-500/40 hover:bg-sky-500/[0.01] transition-all group"
                    >
                      <div className="flex items-center gap-2">
                        <Icon className="size-4 text-sky-500 shrink-0" />
                        <span className="font-semibold text-foreground group-hover:text-sky-600 transition-colors">
                          {describeEventType(item.eventType)}
                        </span>
                      </div>
                      <span className="font-mono font-bold text-foreground">{item.count}</span>
                    </Link>
                  )
                })}
              </div>
            )}
            <div className="flex justify-end mt-4">
              <Button variant="outline" size="sm" asChild className="h-7 text-xs font-bold rounded-md px-3">
                <Link to="/operations/daily-reports">
                  View All Daily Reports
                  <ChevronRight className="size-3 ml-0.5" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
      {isFieldActivityError && (
        <SectionRetry label="Today's Field Activity" onRetry={() => refetchFieldActivity()} />
      )}

      {/* Recent Activity */}
      {!isTimelineError && (
        <Card className="rounded-md border-border/70 shadow-xs overflow-hidden">
          <CardHeader className="pb-3 border-b border-l-3 border-l-teal-500">
            <CardTitle className="text-xs uppercase tracking-wider text-teal-600 dark:text-teal-400 font-bold">
              Recent Activity
            </CardTitle>
            <CardDescription className="text-xs">Live cross-project event feed.</CardDescription>
          </CardHeader>
          <CardContent className="pt-4 text-xs">
            {isTimelineLoading ? (
              <div className="flex justify-center p-6">
                <Loader2 className="size-4 animate-spin text-primary" />
              </div>
            ) : !timeline || timeline.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground italic">
                No recent operational activity found.
              </div>
            ) : (
              <div className="space-y-3">
                {timeline.slice(0, 8).map((entry) => (
                  <div
                    key={entry.id}
                    onClick={() => entry.projectId && openProject(entry.projectId)}
                    className={cn(
                      'flex gap-2.5 items-start',
                      entry.projectId && 'cursor-pointer group'
                    )}
                  >
                    <div className="size-6 rounded-full border border-teal-500/20 bg-teal-500/5 flex items-center justify-center text-teal-600 shrink-0 mt-0.5">
                      <History className="size-3" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-foreground font-semibold leading-normal truncate group-hover:text-primary transition-colors">
                        {entry.summary || describeEventType(entry.eventType)}
                      </p>
                      <span className="text-[10px] text-muted-foreground font-medium">
                        {entry.projectId && projectNameById.get(entry.projectId)
                          ? `${projectNameById.get(entry.projectId)} · `
                          : ''}
                        {timeAgo(entry.occurredAt)}
                      </span>
                    </div>
                    {entry.projectId && (
                      <ChevronRight className="size-3.5 text-muted-foreground/40 group-hover:text-primary transition-colors self-center shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            )}
            <div className="border-t border-border/40 mt-3 pt-4 flex justify-end">
              <Button variant="outline" size="sm" asChild className="h-7 text-xs font-bold rounded-md px-3">
                <Link to="/timeline">
                  View Timeline
                  <ChevronRight className="size-3 ml-0.5" />
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
      {isTimelineError && <SectionRetry label="Recent Activity" onRetry={() => refetchTimeline()} />}
    </div>
  )
}

function SnapshotStat({
  label,
  value,
  tone = 'neutral',
}: {
  label: string
  value: number
  tone?: 'neutral' | 'warning'
}) {
  return (
    <Card className="rounded-md border-border/70 shadow-xs">
      <CardContent className="p-3">
        <span className="block text-[10px] font-semibold text-muted-foreground uppercase tracking-wider truncate">
          {label}
        </span>
        <span
          className={cn(
            'block text-xl font-bold font-mono mt-0.5',
            tone === 'warning' && 'text-amber-600 dark:text-amber-400'
          )}
        >
          {value}
        </span>
      </CardContent>
    </Card>
  )
}

function SectionRetry({ label, onRetry }: { label: string; onRetry: () => void }) {
  return (
    <Card className="rounded-md border-border/70 shadow-xs">
      <CardContent className="p-4 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Unable to load {label.toLowerCase()}.</span>
        <Button size="sm" variant="outline" onClick={onRetry} className="h-7 gap-1.5 text-xs">
          <RotateCcw className="size-3.5" />
          Retry
        </Button>
      </CardContent>
    </Card>
  )
}
