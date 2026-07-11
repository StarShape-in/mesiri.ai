import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, AlertTriangle } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { fetchLedger, type LedgerEntry, type StockState } from '@/lib/materials'

const PAGE_SIZE = 25

interface MaterialLedgerSheetProps {
  siteId: string
  materialId: string
  materialName: string
  open: boolean
  onOpenChange: (open: boolean) => void
  stockState?: StockState
}

export function MaterialLedgerSheet({
  siteId,
  materialId,
  materialName,
  open,
  onOpenChange,
  stockState,
}: MaterialLedgerSheetProps) {
  const [entries, setEntries] = React.useState<LedgerEntry[]>([])
  const [offset, setOffset] = React.useState(0)

  React.useEffect(() => {
    if (open) {
      setEntries([])
      setOffset(0)
    }
  }, [open, siteId, materialId])

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['materials', 'ledger', siteId, materialId, offset],
    queryFn: () => fetchLedger(siteId, materialId, { limit: PAGE_SIZE, offset }),
    enabled: open && !!siteId && !!materialId,
  })

  React.useEffect(() => {
    if (!data) return
    setEntries((prev) => (offset === 0 ? data.items : [...prev, ...data.items]))
  }, [data, offset])

  const hasMore = data ? entries.length < data.total : false

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{materialName}</SheetTitle>
          <SheetDescription>Chronological movement ledger for this Site.</SheetDescription>
        </SheetHeader>

        <div className="px-4 pb-4 flex-1 text-xs space-y-4">
          {data && (
            <div className="grid grid-cols-3 gap-2">
              <div className="border border-border/60 rounded p-2.5">
                <span className="block text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                  Balance
                </span>
                <span className="block text-sm font-mono font-bold tabular-nums text-foreground">
                  {data.current_balance}
                </span>
              </div>
              <div className="border border-border/60 rounded p-2.5">
                <span className="block text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                  Unit
                </span>
                <span className="block text-sm font-semibold text-foreground">{data.unit}</span>
              </div>
              {stockState && (
                <div className="border border-border/60 rounded p-2.5">
                  <span className="block text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                    State
                  </span>
                  <Badge variant={stockStateVariant(stockState)} className="text-[10px] mt-0.5">
                    {stockState}
                  </Badge>
                </div>
              )}
            </div>
          )}

          {isLoading && entries.length === 0 && (
            <div className="flex items-center justify-center py-10 gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin text-primary" />
              Loading ledger...
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <AlertTriangle className="size-6 text-rose-500" />
              <p className="text-muted-foreground">Failed to load the ledger.</p>
              <Button size="sm" variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          )}

          {entries.length > 0 && (
            <div className="border border-border/60 rounded overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/10">
                    <TableHead>Date/Time</TableHead>
                    <TableHead>Movement</TableHead>
                    <TableHead className="text-right">In</TableHead>
                    <TableHead className="text-right">Out</TableHead>
                    <TableHead className="text-right">Balance</TableHead>
                    <TableHead>Recorded By</TableHead>
                    <TableHead>Source</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entries.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className="text-muted-foreground">
                        {entry.occurred_date}
                        {entry.occurred_time ? ` ${entry.occurred_time}` : ''}
                      </TableCell>
                      <TableCell>
                        <Badge variant={entry.direction === 'IN' ? 'default' : 'secondary'} className="text-[9px]">
                          {entry.movement_reason}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {entry.direction === 'IN' ? entry.quantity : ''}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums">
                        {entry.direction === 'OUT' ? entry.quantity : ''}
                      </TableCell>
                      <TableCell className="text-right font-mono tabular-nums font-semibold">
                        {entry.running_balance}
                      </TableCell>
                      <TableCell className="font-mono text-[10px] text-muted-foreground">
                        {entry.created_by ?? '—'}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[9px]">
                          {entry.source}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {!isLoading && !isError && entries.length === 0 && (
            <div className="text-center py-8 text-muted-foreground italic">
              No ledger entries recorded for this material at this Site.
            </div>
          )}

          {hasMore && (
            <div className="flex justify-center">
              <Button
                size="sm"
                variant="outline"
                className="h-8 text-xs"
                disabled={isFetching}
                onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
              >
                {isFetching ? 'Loading...' : 'Load More'}
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function stockStateVariant(state: StockState): 'default' | 'secondary' | 'outline' | 'destructive' {
  if (state === 'AVAILABLE') return 'default'
  if (state === 'OUT_OF_STOCK') return 'outline'
  return 'destructive'
}
