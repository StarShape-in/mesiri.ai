import { useQuery } from '@tanstack/react-query'
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from '@tanstack/react-table'
import { Bar, BarChart, CartesianGrid, XAxis } from 'recharts'
import { Activity, TrendingUp, Users } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart'
import { useAuth } from '@/lib/AuthContext'
import { useScope } from '@/lib/ScopeContext'
import { api } from '@/lib/api'

interface ActivityRow {
  id: string
  label: string
  status: 'active' | 'pending'
  updatedAt: string
}

interface TimelineEntry {
  id: string
  event_type: string
  summary: string
  occurred_at: string
}

const chartConfig = {
  value: { label: 'Activity', color: 'var(--chart-1)' },
} satisfies ChartConfig

const FALLBACK_CHART_DATA = [
  { day: 'Mon', value: 12 },
  { day: 'Tue', value: 19 },
  { day: 'Wed', value: 14 },
  { day: 'Thu', value: 22 },
  { day: 'Fri', value: 18 },
  { day: 'Sat', value: 9 },
  { day: 'Sun', value: 15 },
]

const columns: ColumnDef<ActivityRow>[] = [
  { accessorKey: 'label', header: 'Item' },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => (
      <Badge variant={row.original.status === 'active' ? 'default' : 'secondary'}>
        {row.original.status}
      </Badge>
    ),
  },
  { accessorKey: 'updatedAt', header: 'Updated' },
]

const FALLBACK_ROWS: ActivityRow[] = [
  { id: '1', label: 'Welcome to your dashboard', status: 'active', updatedAt: 'just now' },
]

export default function Overview() {
  const { me } = useAuth()
  const { scope } = useScope()

  // Reads the current Scope and filters the shared Overview page's data
  // accordingly — Portfolio has no project_id/site_id (org-wide), Project
  // scope passes project_id only, Site scope passes both. This is the same
  // pattern every future shared page should follow: Scope -> Filtered Data.
  const projectId = scope.mode !== 'portfolio' ? scope.projectId : undefined
  const siteId = scope.mode === 'site' ? scope.siteId : undefined

  const { data: rows, isLoading } = useQuery({
    queryKey: ['overview-activity', projectId, siteId],
    queryFn: async () => {
      try {
        const res = await api.get<{ items: TimelineEntry[] }>('/timeline', {
          params: { project_id: projectId, site_id: siteId, limit: 10 },
        })
        if (res.data.items.length === 0) return FALLBACK_ROWS
        return res.data.items.map(
          (entry): ActivityRow => ({
            id: entry.id,
            label: entry.summary || entry.event_type,
            status: 'active',
            updatedAt: new Date(entry.occurred_at).toLocaleString(),
          })
        )
      } catch {
        return FALLBACK_ROWS
      }
    },
  })

  const table = useReactTable({
    data: rows ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">Welcome back{me?.full_name ? `, ${me.full_name}` : ''}</h2>
        <p className="text-sm text-muted-foreground">
          {scope.mode === 'portfolio'
            ? 'Organization-wide view across all projects.'
            : scope.mode === 'project'
              ? `Viewing ${scope.projectName}.`
              : `Viewing ${scope.siteName} (${scope.projectName}).`}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Activity</CardTitle>
            <Activity className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">109</div>
            <p className="text-xs text-muted-foreground">this week</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Growth</CardTitle>
            <TrendingUp className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">+12%</div>
            <p className="text-xs text-muted-foreground">vs last week</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Team</CardTitle>
            <Users className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{me?.organization_name ? 1 : 0}</div>
            <p className="text-xs text-muted-foreground">organization</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Weekly activity</CardTitle>
          <CardDescription>Overview of activity over the last 7 days.</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={chartConfig} className="h-[240px] w-full">
            <BarChart data={FALLBACK_CHART_DATA}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="day" tickLine={false} axisLine={false} tickMargin={8} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Bar dataKey="value" fill="var(--color-value)" radius={4} />
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent items</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="grid gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((headerGroup) => (
                  <TableRow key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <TableHead key={header.id}>
                        {header.isPlaceholder
                          ? null
                          : flexRender(header.column.columnDef.header, header.getContext())}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {table.getRowModel().rows.map((row) => (
                  <TableRow key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
