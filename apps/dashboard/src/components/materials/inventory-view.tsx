import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, RotateCcw, Boxes, AlertOctagon, PackageX } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { KpiCard } from '@/components/ui/kpi-card'
import { fetchInventory, type MaterialStock, type StockState } from '@/lib/materials'
import { fetchProjects, fetchSites } from '@/lib/projects'
import { MaterialLedgerSheet } from './material-ledger-sheet'

interface InventoryViewProps {
  projectId: string | null
  siteId: string | null
}

function stockStateBadgeVariant(state: StockState): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (state === 'AVAILABLE') return 'secondary'
  if (state === 'OUT_OF_STOCK') return 'outline'
  return 'destructive'
}

export function InventoryView({ projectId, siteId }: InventoryViewProps) {
  const [selectedRow, setSelectedRow] = React.useState<MaterialStock | null>(null)
  const [ledgerOpen, setLedgerOpen] = React.useState(false)

  const filters = {
    project_id: projectId ?? undefined,
    site_id: siteId ?? undefined,
  }

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['materials', 'inventory', filters],
    queryFn: () => fetchInventory(filters),
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

  const showProjectColumn = !projectId

  const rows = React.useMemo(() => data ?? [], [data])

  const summary = React.useMemo(
    () => ({
      total: rows.length,
      negative: rows.filter((r) => r.stock_state === 'NEGATIVE_STOCK').length,
      outOfStock: rows.filter((r) => r.stock_state === 'OUT_OF_STOCK').length,
      available: rows.filter((r) => r.stock_state === 'AVAILABLE').length,
    }),
    [rows]
  )

  const openLedger = (row: MaterialStock) => {
    setSelectedRow(row)
    setLedgerOpen(true)
  }

  return (
    <div className="space-y-3">
      {!isLoading && !isError && rows.length > 0 && (
        <div className="grid gap-3 grid-cols-2 sm:grid-cols-4">
          <KpiCard title="Materials Tracked" value={summary.total} icon={<Boxes />} />
          <KpiCard title="Available" value={summary.available} icon={<Boxes />} trend="up" />
          <KpiCard
            title="Out Of Stock"
            value={summary.outOfStock}
            icon={<PackageX />}
            trend={summary.outOfStock > 0 ? 'down' : 'neutral'}
          />
          <KpiCard
            title="Negative Stock"
            value={summary.negative}
            icon={<AlertOctagon />}
            trend={summary.negative > 0 ? 'down' : 'neutral'}
          />
        </div>
      )}

      <Card className="rounded-md border-border/70 shadow-xs overflow-hidden">
        <CardContent className="p-0">
          {isError ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center text-xs">
              <AlertTriangle className="size-6 text-rose-500" />
              <p className="text-muted-foreground">Failed to load material inventory.</p>
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
          ) : rows.length === 0 ? (
            <div className="flex flex-col items-center gap-1.5 py-12 text-center text-xs">
              <p className="text-muted-foreground">No material inventory exists yet.</p>
              <p className="text-muted-foreground">Record a material inflow to begin tracking Site inventory.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Material</TableHead>
                    <TableHead className="text-right">Available</TableHead>
                    <TableHead>Site</TableHead>
                    {showProjectColumn && <TableHead>Project</TableHead>}
                    <TableHead className="text-right">Total In</TableHead>
                    <TableHead className="text-right">Total Out</TableHead>
                    <TableHead>Last Movement</TableHead>
                    <TableHead>Stock State</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow
                      key={`${row.site_id}-${row.material_id}`}
                      onClick={() => openLedger(row)}
                      className="cursor-pointer hover:bg-muted/30 transition-colors text-xs"
                    >
                      <TableCell className="font-semibold text-foreground">{row.material_name}</TableCell>
                      <TableCell className="text-right font-mono tabular-nums font-semibold">
                        {row.current_stock} {row.unit}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {row.site_id ? (siteNameById.get(row.site_id) ?? row.site_id.slice(0, 8)) : '—'}
                      </TableCell>
                      {showProjectColumn && (
                        <TableCell className="text-muted-foreground">
                          {row.project_id ? (projectNameById.get(row.project_id) ?? row.project_id.slice(0, 8)) : '—'}
                        </TableCell>
                      )}
                      <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                        {row.total_received}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                        {row.total_used}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {row.last_movement_at ? new Date(row.last_movement_at).toLocaleString() : '—'}
                      </TableCell>
                      <TableCell>
                        <Badge variant={stockStateBadgeVariant(row.stock_state)} className="text-[10px]">
                          {row.stock_state}
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

      {selectedRow && (
        <MaterialLedgerSheet
          siteId={selectedRow.site_id}
          materialId={selectedRow.material_id}
          materialName={selectedRow.material_name}
          stockState={selectedRow.stock_state}
          open={ledgerOpen}
          onOpenChange={setLedgerOpen}
        />
      )}
    </div>
  )
}
