import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Search, RotateCcw } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchInflows, INFLOW_REASONS, type MaterialReceipt } from '@/lib/materials'
import { fetchProjects, fetchSites } from '@/lib/projects'
import { MovementDetailsSheet } from './movement-details-sheet'

interface InflowsViewProps {
  projectId: string | null
  siteId: string | null
}

export function InflowsView({ projectId, siteId }: InflowsViewProps) {
  const [search, setSearch] = React.useState('')
  const [reason, setReason] = React.useState('ALL')
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = React.useState(false)

  const filters = {
    project_id: projectId ?? undefined,
    site_id: siteId ?? undefined,
    material_name: search || undefined,
    movement_reason: reason === 'ALL' ? undefined : reason,
    limit: 100,
  }

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['materials', 'inflows', filters],
    queryFn: () => fetchInflows(filters),
  })

  const { data: projects = [] } = useQuery({
    queryKey: ['scope-projects'],
    queryFn: fetchProjects,
    staleTime: 60_000,
  })

  const { data: sites = [] } = useQuery({
    queryKey: ['scope-sites', projectId],
    queryFn: () => fetchSites(projectId!),
    enabled: !!projectId,
    staleTime: 60_000,
  })

  const projectNameById = React.useMemo(() => new Map(projects.map((p) => [p.id, p.name])), [projects])
  const siteNameById = React.useMemo(() => new Map(sites.map((s) => [s.id, s.name])), [sites])

  const showSiteColumn = !siteId
  const showProjectColumn = !projectId

  const openRow = (id: string) => {
    setSelectedId(id)
    setSheetOpen(true)
  }

  const items = data?.items ?? []

  return (
    <div className="space-y-3">
      <Card className="rounded-md border-border/70 shadow-xs">
        <CardContent className="p-3 flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search material name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-8 text-xs"
            />
          </div>
          <Select value={reason} onValueChange={setReason}>
            <SelectTrigger className="w-full sm:w-[180px] h-8 text-xs">
              <SelectValue placeholder="Reason" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Reasons</SelectItem>
              {INFLOW_REASONS.map((r) => (
                <SelectItem key={r.value} value={r.value}>
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card className="rounded-md border-border/70 shadow-xs overflow-hidden">
        <CardContent className="p-0">
          {isError ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center text-xs">
              <AlertTriangle className="size-6 text-rose-500" />
              <p className="text-muted-foreground">Failed to load material inflows.</p>
              <Button size="sm" variant="outline" onClick={() => refetch()} className="gap-1.5">
                <RotateCcw className="size-3.5" />
                Retry
              </Button>
            </div>
          ) : isLoading ? (
            <div className="p-3 space-y-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-1.5 py-12 text-center text-xs">
              <p className="text-muted-foreground">No material inflows recorded in this scope.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Material</TableHead>
                    <TableHead className="text-right">Quantity</TableHead>
                    <TableHead>Reason</TableHead>
                    {showSiteColumn && <TableHead>Site</TableHead>}
                    {showProjectColumn && <TableHead>Project</TableHead>}
                    <TableHead>Vendor</TableHead>
                    <TableHead>Occurred At</TableHead>
                    <TableHead>Source</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((row: MaterialReceipt) => (
                    <TableRow
                      key={row.id}
                      onClick={() => openRow(row.id)}
                      className="cursor-pointer hover:bg-muted/30 transition-colors text-xs"
                    >
                      <TableCell className="font-semibold text-foreground">{row.material_name}</TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {row.quantity} {row.unit}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px]">
                          {row.movement_reason}
                        </Badge>
                      </TableCell>
                      {showSiteColumn && (
                        <TableCell className="text-muted-foreground">
                          {row.site_id ? (siteNameById.get(row.site_id) ?? row.site_id.slice(0, 8)) : '—'}
                        </TableCell>
                      )}
                      {showProjectColumn && (
                        <TableCell className="text-muted-foreground">
                          {projectNameById.get(row.project_id) ?? row.project_id.slice(0, 8)}
                        </TableCell>
                      )}
                      <TableCell className="text-muted-foreground">{row.supplier ?? '—'}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {row.occurred_date}
                        {row.occurred_time ? ` ${row.occurred_time}` : ''}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px]">
                          {row.source}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <MovementDetailsSheet direction="IN" id={selectedId} open={sheetOpen} onOpenChange={setSheetOpen} />
    </div>
  )
}
