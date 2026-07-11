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
import { api } from '@/lib/api'

interface ActivityRow {
  id: string
  label: string
  status: 'active' | 'pending'
  updatedAt: string
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

  // Placeholder query against the backend to prove the data layer end-to-end.
  // Falls back to static demo data if the endpoint isn't available yet.
  const { data: rows, isLoading } = useQuery({
    queryKey: ['overview-activity'],
    queryFn: async () => {
      try {
        const res = await api.get<ActivityRow[]>('/dashboard/activity')
        return res.data
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
        <h2 className="text-lg font-semibold">Welcome back{me?.name ? `, ${me.name}` : ''}</h2>
        <p className="text-sm text-muted-foreground">Here's what's happening with your account.</p>
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
            <div className="text-2xl font-bold">{me?.org_name ? 1 : 0}</div>
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
