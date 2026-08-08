import * as React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Search, RotateCcw } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { fetchOutflows, OUTFLOW_REASONS, type MaterialUsage, reverseOutflow } from '@/lib/materials'
import { fetchProjects, fetchSites } from '@/lib/projects'
import { MovementDetailsSheet } from './movement-details-sheet'
import { BulkActionBar } from '@/components/ui/bulk-action-bar'

interface OutflowsViewProps {
  projectId: string | null
  siteId: string | null
}

function reasonBadgeVariant(reason: string): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (reason === 'WASTAGE') return 'destructive'
  return 'outline'
}

export function OutflowsView({ projectId, siteId }: OutflowsViewProps) {
  const queryClient = useQueryClient()
  const [search, setSearch] = React.useState('')
  const [reason, setReason] = React.useState('ALL')
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = React.useState(false)
  const [selectedIds, setSelectedIds] = React.useState<string[]>([])

  const filters = {
    project_id: projectId ?? undefined,
    site_id: siteId ?? undefined,
    material_name: search || undefined,
    movement_reason: reason === 'ALL' ? undefined : reason,
    limit: 100,
  }

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['materials', 'outflows', filters],
    queryFn: () => fetchOutflows(filters),
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

  const reverseMutation = useMutation({
    mutationFn: (id: string) => reverseOutflow(id, { reason_note: 'Bulk reversal correction' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] })
    },
  })

  React.useEffect(() => {
    setSelectedIds([])
  }, [projectId, siteId, search, reason])

  const projectNameById = React.useMemo(() => new Map(projects.map((p) => [p.id, p.name])), [projects])
  const siteNameById = React.useMemo(() => new Map(sites.map((s) => [s.id, s.name])), [sites])

  const showSiteColumn = !siteId
  const showProjectColumn = !projectId

  const openRow = (id: string) => {
    setSelectedId(id)
    setSheetOpen(true)
  }

  const items = data?.items ?? []

  // Row selection helpers
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(items.map((i) => i.id))
    } else {
      setSelectedIds([])
    }
  }

  const handleSelectRow = (id: string, checked: boolean) => {
    if (checked) {
      setSelectedIds((prev) => [...prev, id])
    } else {
      setSelectedIds((prev) => prev.filter((item) => item !== id))
    }
  }

  const handleBulkReverse = async () => {
    if (confirm(`Are you sure you want to reverse the ${selectedIds.length} selected outflows?`)) {
      try {
        for (const id of selectedIds) {
          await reverseMutation.mutateAsync(id)
        }
        setSelectedIds([])
      } catch (err: any) {
        alert(err.response?.data?.detail || 'Failed to bulk reverse outflows.')
      }
    }
  }

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
              {OUTFLOW_REASONS.map((r) => (
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
              <p className="text-muted-foreground">Failed to load material outflows.</p>
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
              <p className="text-muted-foreground">No material outflows recorded in this scope.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12 px-4">
                      <input
                        type="checkbox"
                        checked={items.length > 0 && selectedIds.length === items.length}
                        onChange={(e) => handleSelectAll(e.target.checked)}
                        className="rounded border-border/80 text-primary focus:ring-primary size-4"
                      />
                    </TableHead>
                    <TableHead>Material</TableHead>
                    <TableHead className="text-right">Quantity</TableHead>
                    <TableHead>Reason</TableHead>
                    {showSiteColumn && <TableHead>Site</TableHead>}
                    {showProjectColumn && <TableHead>Project</TableHead>}
                    <TableHead>Work Item</TableHead>
                    <TableHead>Occurred At</TableHead>
                    <TableHead>Source</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((row: MaterialUsage) => {
                    const isSelected = selectedIds.includes(row.id)
                    return (
                      <TableRow
                        key={row.id}
                        data-state={isSelected ? 'selected' : undefined}
                        className="cursor-pointer hover:bg-muted/30 transition-colors text-xs"
                      >
                        <TableCell className="px-4" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={(e) => handleSelectRow(row.id, e.target.checked)}
                            className="rounded border-border/80 text-primary focus:ring-primary size-4"
                          />
                        </TableCell>
                        <TableCell className="font-semibold text-foreground" onClick={() => openRow(row.id)}>{row.material_name}</TableCell>
                        <TableCell className="text-right font-mono tabular-nums" onClick={() => openRow(row.id)}>
                          {row.quantity} {row.unit}
                        </TableCell>
                        <TableCell onClick={() => openRow(row.id)}>
                          <Badge variant={reasonBadgeVariant(row.movement_reason)} className="text-[10px]">
                            {row.movement_reason}
                          </Badge>
                        </TableCell>
                        {showSiteColumn && (
                          <TableCell className="text-muted-foreground" onClick={() => openRow(row.id)}>
                            {row.site_id ? (siteNameById.get(row.site_id) ?? row.site_id.slice(0, 8)) : '—'}
                          </TableCell>
                        )}
                        {showProjectColumn && (
                          <TableCell className="text-muted-foreground" onClick={() => openRow(row.id)}>
                            {projectNameById.get(row.project_id) ?? row.project_id.slice(0, 8)}
                          </TableCell>
                        )}
                        <TableCell className="text-muted-foreground" onClick={() => openRow(row.id)}>{row.work_item ?? '—'}</TableCell>
                        <TableCell className="text-muted-foreground" onClick={() => openRow(row.id)}>
                          {row.occurred_date}
                          {row.occurred_time ? ` ${row.occurred_time}` : ''}
                        </TableCell>
                        <TableCell onClick={() => openRow(row.id)}>
                          <Badge variant="outline" className="text-[10px]">
                            {row.source}
                          </Badge>
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

      <MovementDetailsSheet direction="OUT" id={selectedId} open={sheetOpen} onOpenChange={setSheetOpen} />

      <BulkActionBar selectedCount={selectedIds.length} onClear={() => setSelectedIds([])}>
        <Button
          variant="outline"
          size="sm"
          onClick={handleBulkReverse}
          className="h-8 text-xs text-rose-600 dark:text-rose-400 gap-1 font-bold"
        >
          Reverse Selected
        </Button>
      </BulkActionBar>
    </div>
  )
}
