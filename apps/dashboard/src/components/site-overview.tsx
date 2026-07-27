import * as React from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  MapPin,
  AlertTriangle,
  ChevronRight,
  Settings2,
  Activity,
  History,
  CheckCircle2,
  RotateCcw,
  Radio,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/lib/AuthContext'
import { fetchSiteOverview, type SiteOverviewData } from '@/lib/projects'
import { timeAgo, cn } from '@/lib/utils'
import { FIELD_ACTIVITY_META, describeEventType, statusBadgeClass } from '@/lib/field-activity'

const SITE_STATUS_COLORS = {
  active: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20',
  inactive: 'bg-muted text-muted-foreground border-border',
  pending: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20',
} as const

function siteStatusClass(status: string) {
  return SITE_STATUS_COLORS[status as keyof typeof SITE_STATUS_COLORS] || SITE_STATUS_COLORS.inactive
}

// The only two Field Report categories with real, trackable submissions
// today (see backend/src/mesiri/events/consumers/timeline_projector.py).
// Their vocabulary here ("Material In" / "Material Out") matches the
// `requiredReportTypes` labels configured on the Project (see
// components/project-reporting-tab.tsx::REPORT_TYPES).
const TRACKABLE_REPORT_ROWS: Array<{ eventType: string; requiredLabel: string }> = [
  { eventType: 'MaterialReceived', requiredLabel: 'Material In' },
  { eventType: 'MaterialUsed', requiredLabel: 'Material Out' },
]

interface SiteOverviewProps {
  projectId: string
  siteId: string
}

export function SiteOverview({ projectId, siteId }: SiteOverviewProps) {
  const { me } = useAuth()

  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useQuery<SiteOverviewData>({
    queryKey: ['site-overview', projectId, siteId],
    queryFn: () => fetchSiteOverview(projectId, siteId),
    staleTime: 30_000,
  })

  const todayCounts = React.useMemo(() => {
    const map = new Map<string, number>()
    for (const item of data?.fieldActivityToday ?? []) map.set(item.eventType, item.count)
    return map
  }, [data])

  const totalToday = React.useMemo(
    () => Array.from(todayCounts.values()).reduce((sum, n) => sum + n, 0),
    [todayCounts]
  )

  const reportingRows = React.useMemo(() => {
    if (!data) return []
    return TRACKABLE_REPORT_ROWS.map(({ eventType, requiredLabel }) => {
      const count = todayCounts.get(eventType) ?? 0
      const meta = FIELD_ACTIVITY_META[eventType]
      const required = data.project.requiredReportTypes
        ? data.project.requiredReportTypes.includes(requiredLabel)
        : true
      const status: 'submitted' | 'missing' | 'not_required' = !required
        ? 'not_required'
        : count > 0
          ? 'submitted'
          : 'missing'
      return { eventType, meta, count, status }
    })
  }, [data, todayCounts])

  const attentionItems = React.useMemo(() => {
    if (!data) return []
    const items: Array<{ id: string; title: string; context: string; slug?: string }> = []
    if (totalToday === 0) {
      items.push({
        id: 'no-activity',
        title: 'No Site Activity Today',
        context: 'No Field Reports have been recorded at this site today.',
      })
    }
    for (const row of reportingRows) {
      if (row.status === 'missing') {
        items.push({
          id: `missing-${row.eventType}`,
          title: `Missing ${row.meta?.label ?? row.eventType} Report`,
          context: 'Required for this project, not yet submitted today.',
          slug: row.meta?.slug,
        })
      }
    }
    return items.slice(0, 4)
  }, [data, totalToday, reportingRows])

  const isAdmin = me?.role === 'ADMIN'

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center text-sm">
        <AlertTriangle className="size-8 text-rose-500" />
        <p className="text-muted-foreground">
          Failed to load this site. It may not exist under the current project, or you may not have access.
        </p>
        <Button size="sm" variant="outline" onClick={() => refetch()} className="gap-1.5">
          <RotateCcw className="size-3.5" />
          Retry
        </Button>
      </div>
    )
  }

  const { site, project, reportingToday, lastActivityAt, recentActivity } = data

  return (
    <div className="space-y-4">
      {/* Site Context Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-4">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2 flex-wrap">
            <MapPin className="size-5 text-sky-500 dark:text-sky-400" />
            <h1 className="text-lg font-bold text-foreground leading-tight">{site.name}</h1>
            <Badge variant="outline" className={cn('text-xs rounded-sm py-0.5 font-semibold', siteStatusClass(site.status))}>
              {site.status}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground font-semibold">
            <Link to={`/overview?project=${projectId}`} className="hover:underline hover:text-foreground transition-colors">
              {project.name} Project
            </Link>
            {project.location ? ` · ${project.location}` : ''}
          </p>
          <div className="flex items-center gap-2 pt-1 flex-wrap">
            <Badge
              variant="outline"
              className={cn(
                'text-[10px] rounded-sm py-0.5 font-semibold gap-1',
                reportingToday ? statusBadgeClass('success') : statusBadgeClass('neutral')
              )}
            >
              <Radio className="size-3" />
              {reportingToday ? 'Reporting Today' : 'No Reports Today'}
            </Badge>
            {lastActivityAt && (
              <span className="text-[10px] text-muted-foreground font-medium">
                Last activity {timeAgo(lastActivityAt)}
              </span>
            )}
          </div>
        </div>
        {isAdmin && (
          <Button variant="outline" size="sm" asChild className="h-7 text-xs font-bold gap-1.5 w-fit shrink-0">
            <Link to={`/projects/${projectId}`}>
              <Settings2 className="size-3.5" />
              View Site Details
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
              Nothing needs attention at this site right now.
            </div>
          ) : (
            <div className="divide-y divide-border/40">
              {attentionItems.map((item) => (
                <Link
                  key={item.id}
                  to={
                    item.slug
                      ? `/operations/daily-reports?project=${projectId}&site=${siteId}&type=${item.slug}`
                      : `/operations/daily-reports?project=${projectId}&site=${siteId}`
                  }
                  className="flex items-start justify-between py-2.5 first:pt-0 last:pb-0 group hover:text-primary transition-all"
                >
                  <div className="space-y-0.5">
                    <h4 className="font-bold text-foreground group-hover:text-primary transition-colors">
                      {item.title}
                    </h4>
                    <p className="text-muted-foreground font-medium">{item.context}</p>
                  </div>
                  <ChevronRight className="size-4 text-muted-foreground/40 group-hover:text-primary transition-colors self-center shrink-0" />
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Today at Site */}
      <div className="grid gap-3 grid-cols-2 sm:grid-cols-3">
        <SnapshotStat label="Material In Today" value={todayCounts.get('MaterialReceived') ?? 0} />
        <SnapshotStat label="Material Out Today" value={todayCounts.get('MaterialUsed') ?? 0} />
        <SnapshotStat label="Field Updates Today" value={totalToday} />
      </div>

      {/* Field Reporting Status */}
      <Card className="rounded-md border-border/70 shadow-xs overflow-hidden">
        <CardHeader className="pb-3 border-b border-l-3 border-l-violet-500">
          <CardTitle className="text-xs uppercase tracking-wider text-violet-600 dark:text-violet-400 font-bold">
            Field Reporting Status
          </CardTitle>
          <CardDescription className="text-xs">
            Has this site submitted today's required Field Reports?
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-2 text-xs">
          <div className="divide-y divide-border/40">
            {reportingRows.map((row) => {
              const Icon = row.meta?.icon ?? Activity
              const label = row.meta?.label ?? row.eventType
              return (
                <Link
                  key={row.eventType}
                  to={
                    row.meta
                      ? `/operations/daily-reports?project=${projectId}&site=${siteId}&type=${row.meta.slug}`
                      : `/operations/daily-reports?project=${projectId}&site=${siteId}`
                  }
                  className="flex items-center justify-between py-2.5 first:pt-0 last:pb-0 group hover:text-primary transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <div className="size-6 rounded-full border border-violet-500/20 bg-violet-500/5 flex items-center justify-center text-violet-600 shrink-0">
                      <Icon className="size-3.5" />
                    </div>
                    <span className="font-semibold text-foreground">{label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {row.status === 'submitted' && (
                      <Badge variant="outline" className={cn('text-[10px] rounded-sm py-0.5 font-semibold', statusBadgeClass('success'))}>
                        Submitted · {row.count}
                      </Badge>
                    )}
                    {row.status === 'missing' && (
                      <Badge variant="outline" className={cn('text-[10px] rounded-sm py-0.5 font-semibold', statusBadgeClass('warning'))}>
                        Missing
                      </Badge>
                    )}
                    {row.status === 'not_required' && (
                      <Badge variant="outline" className={cn('text-[10px] rounded-sm py-0.5 font-semibold', statusBadgeClass('neutral'))}>
                        Not Required
                      </Badge>
                    )}
                    <ChevronRight className="size-3.5 text-muted-foreground/40 group-hover:text-primary transition-colors" />
                  </div>
                </Link>
              )
            })}
          </div>
          <div className="flex justify-end mt-3 pt-3 border-t border-border/40">
            <Button variant="outline" size="sm" asChild className="h-7 text-xs font-bold rounded-md px-3">
              <Link to={`/operations/daily-reports?project=${projectId}&site=${siteId}`}>
                View All Daily Reports
                <ChevronRight className="size-3 ml-0.5" />
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Recent Field Activity (Latest Field Reports + Material Movement + Recent Activity combined — currently the same underlying timeline records) */}
      <Card className="rounded-md border-border/70 shadow-xs overflow-hidden">
        <CardHeader className="pb-3 border-b border-l-3 border-l-teal-500">
          <CardTitle className="text-xs uppercase tracking-wider text-teal-600 dark:text-teal-400 font-bold">
            Recent Field Activity
          </CardTitle>
          <CardDescription className="text-xs">Latest submitted reports and site activity.</CardDescription>
        </CardHeader>
        <CardContent className="pt-4 text-xs">
          {recentActivity.length === 0 ? (
            <div className="text-center py-6 text-muted-foreground italic">
              No recent activity recorded at this site.
            </div>
          ) : (
            <div className="space-y-3">
              {recentActivity.slice(0, 8).map((entry) => {
                const meta = FIELD_ACTIVITY_META[entry.eventType]
                const Icon = meta?.icon ?? History
                return (
                  <div key={entry.id} className="flex gap-2.5 items-start">
                    <div className="size-6 rounded-full border border-teal-500/20 bg-teal-500/5 flex items-center justify-center text-teal-600 shrink-0 mt-0.5">
                      <Icon className="size-3" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-foreground font-semibold leading-normal truncate">
                        {entry.summary || describeEventType(entry.eventType)}
                      </p>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="text-[10px] text-muted-foreground font-medium cursor-default">
                            {timeAgo(entry.occurredAt)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>{new Date(entry.occurredAt).toLocaleString()}</TooltipContent>
                      </Tooltip>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
          <div className="flex flex-wrap justify-end gap-2 border-t border-border/40 mt-3 pt-4">
            <Button variant="outline" size="sm" asChild className="h-7 text-xs font-bold rounded-md px-3">
              <Link to={`/operations/daily-reports?project=${projectId}&site=${siteId}&type=material-in`}>
                View Material In
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild className="h-7 text-xs font-bold rounded-md px-3">
              <Link to={`/operations/daily-reports?project=${projectId}&site=${siteId}&type=material-out`}>
                View Material Out
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild className="h-7 text-xs font-bold rounded-md px-3">
              <Link to={`/timeline?project=${projectId}&site=${siteId}`}>
                View Timeline
                <ChevronRight className="size-3 ml-0.5" />
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function SnapshotStat({ label, value }: { label: string; value: number }) {
  return (
    <Card className="rounded-md border-border/70 shadow-xs">
      <CardContent className="p-3">
        <span className="block text-[10px] font-semibold text-muted-foreground uppercase tracking-wider truncate">
          {label}
        </span>
        <span className="block text-xl font-bold font-mono mt-0.5">{value}</span>
      </CardContent>
    </Card>
  )
}
