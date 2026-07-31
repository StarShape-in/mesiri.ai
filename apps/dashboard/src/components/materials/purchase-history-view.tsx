import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Search,
  AlertTriangle,
  RotateCcw,
  ShoppingBag,
  DollarSign,
  ArrowUpDown,
  Truck,
  CalendarDays,
  FileText,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { KpiCard } from '@/components/ui/kpi-card'
import { fetchInflows, formatMoney, INFLOW_REASONS, type MaterialReceipt } from '@/lib/materials'
import { fetchProjects, fetchSites } from '@/lib/projects'
import { toLocalISODate } from '@/lib/utils'
import { PurchaseDetailsSheet } from './purchase-details-sheet'
import { InvoiceDetailsSheet } from './invoice-details-sheet'

interface PurchaseHistoryViewProps {
  projectId: string | null
  siteId: string | null
}

type SortOption = 'newest' | 'oldest' | 'material_asc' | 'supplier_asc'

export function PurchaseHistoryView({ projectId, siteId }: PurchaseHistoryViewProps) {
  const [search, setSearch] = React.useState('')
  const [supplierSearch, setSupplierSearch] = React.useState('')
  const [reason, setReason] = React.useState('ALL')
  const [sortOrder, setSortOrder] = React.useState<SortOption>('newest')
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [selectedInvoiceId, setSelectedInvoiceId] = React.useState<string | null>(null)
  const [invoiceSheetOpen, setInvoiceSheetOpen] = React.useState(false)
  const [sheetOpen, setSheetOpen] = React.useState(false)

  const filters = {
    project_id: projectId ?? undefined,
    site_id: siteId ?? undefined,
    material_name: search || undefined,
    movement_reason: reason === 'ALL' ? undefined : reason,
    limit: 100,
  }

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['materials', 'purchase-history', filters],
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

  const openPurchase = (id: string) => {
    setSelectedId(id)
    setSheetOpen(true)
  }

  const openInvoice = (id: string) => {
    setSelectedInvoiceId(id)
    setInvoiceSheetOpen(true)
  }

  // Memoized so the `?? []` fallback doesn't mint a new array identity on
  // every render, which would defeat the filter/sort useMemo below and re-run
  // the whole sort on every unrelated state change (search box keystrokes).
  const rawItems = React.useMemo(() => data?.items ?? [], [data])

  // Client-side supplier search and sorting filtering on top of server query
  const items = React.useMemo(() => {
    let result = [...rawItems]

    if (supplierSearch.trim()) {
      const q = supplierSearch.toLowerCase().trim()
      result = result.filter(
        (item) => item.supplier && item.supplier.toLowerCase().includes(q)
      )
    }

    result.sort((a, b) => {
      if (sortOrder === 'newest') {
        return new Date(b.occurred_date).getTime() - new Date(a.occurred_date).getTime()
      }
      if (sortOrder === 'oldest') {
        return new Date(a.occurred_date).getTime() - new Date(b.occurred_date).getTime()
      }
      if (sortOrder === 'material_asc') {
        return a.material_name.localeCompare(b.material_name)
      }
      if (sortOrder === 'supplier_asc') {
        return (a.supplier || '').localeCompare(b.supplier || '')
      }
      return 0
    })

    return result
  }, [rawItems, supplierSearch, sortOrder])

  // Refined storekeeper KPIs: Today, This Month, Total Purchase Value, Suppliers Used
  const summary = React.useMemo(() => {
    const todayStr = toLocalISODate()
    const currentMonthStr = todayStr.slice(0, 7) // YYYY-MM

    let purchasesToday = 0
    let purchasesThisMonth = 0
    let totalCostSum = 0
    let pricedCount = 0
    let costableCount = 0
    const supplierSet = new Set<string>()

    for (const item of items) {
      if (item.occurred_date === todayStr) {
        purchasesToday += 1
      }
      if (item.occurred_date && item.occurred_date.startsWith(currentMonthStr)) {
        purchasesThisMonth += 1
      }
      if (item.supplier?.trim()) {
        supplierSet.add(item.supplier.trim())
      }
      // A corrected purchase was not money spent -- counting it would overstate
      // what the company actually paid.
      if (item.is_reversed) continue
      costableCount += 1
      const cost = item.total_cost === null ? NaN : parseFloat(item.total_cost ?? '')
      if (!isNaN(cost)) {
        totalCostSum += cost
        pricedCount += 1
      }
    }

    return {
      purchasesToday,
      purchasesThisMonth,
      suppliersUsed: supplierSet.size,
      totalCostSum,
      // How much of the total is actually backed by recorded prices. Shown so
      // a figure covering 12 of 60 purchases can never read as the full spend
      // -- the same reason the DPR refuses to report material cost at all.
      pricedCount,
      costableCount,
    }
  }, [items])

  return (
    <div className="space-y-3">
      {/* KPI Cards (4-column responsive grid) */}
      {!isLoading && !isError && (
        <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
          <KpiCard
            title="Purchases Today"
            value={summary.purchasesToday}
            icon={<ShoppingBag />}
            trend={summary.purchasesToday > 0 ? 'up' : 'neutral'}
          />
          <KpiCard
            title="Purchases This Month"
            value={summary.purchasesThisMonth}
            icon={<CalendarDays />}
          />
          <KpiCard
            title="Suppliers Used"
            value={summary.suppliersUsed}
            icon={<Truck />}
          />
          <KpiCard
            title="Total Purchase Value"
            value={
              summary.pricedCount > 0
                ? `₹${summary.totalCostSum.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
                : 'Not recorded'
            }
            // Never present a partial figure as the whole spend. If only some
            // purchases carry a price, say so outright. Uses KpiCard's existing
            // `description` prop -- that component is shared with the Labour
            // pages and must not be modified from here.
            description={
              summary.pricedCount > 0 && summary.pricedCount < summary.costableCount
                ? `from ${summary.pricedCount} of ${summary.costableCount} purchases`
                : undefined
            }
            icon={<DollarSign />}
            trend="neutral"
          />
        </div>
      )}

      {/* Filter Toolbar */}
      <Card className="rounded-md border-border/70 shadow-xs">
        <CardContent className="p-3 flex flex-col md:flex-row gap-2 items-center">
          <div className="relative flex-1 w-full max-w-xs">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search material..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-8 text-xs"
            />
          </div>
          <div className="relative flex-1 w-full max-w-xs">
            <Truck className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search supplier..."
              value={supplierSearch}
              onChange={(e) => setSupplierSearch(e.target.value)}
              className="pl-8 h-8 text-xs"
            />
          </div>
          <div className="flex gap-2 w-full md:w-auto flex-wrap sm:flex-nowrap">
            <Select value={reason} onValueChange={setReason}>
              <SelectTrigger className="w-full sm:w-[150px] h-8 text-xs">
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

            <Select value={sortOrder} onValueChange={(v) => setSortOrder(v as SortOption)}>
              <SelectTrigger className="w-full sm:w-[150px] h-8 text-xs">
                <ArrowUpDown className="size-3 mr-1 text-muted-foreground" />
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="newest">Newest First</SelectItem>
                <SelectItem value="oldest">Oldest First</SelectItem>
                <SelectItem value="material_asc">Material (A-Z)</SelectItem>
                <SelectItem value="supplier_asc">Supplier (A-Z)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Main Purchase Table */}
      <Card className="rounded-md border-border/70 shadow-xs overflow-hidden">
        <CardContent className="p-0">
          {isError ? (
            <div className="flex flex-col items-center gap-3 py-12 text-center text-xs">
              <AlertTriangle className="size-6 text-rose-500" />
              <p className="text-muted-foreground">Failed to load purchase records.</p>
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
              <ShoppingBag className="size-8 text-muted-foreground/50 mb-1" />
              <p className="font-semibold text-foreground">No purchases recorded yet.</p>
              <p className="text-muted-foreground">
                Record your first material receipt to see it here.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Material</TableHead>
                    <TableHead className="text-right">Quantity</TableHead>
                    <TableHead>Supplier / Vendor</TableHead>
                    <TableHead>Purchase Date</TableHead>
                    {showSiteColumn && <TableHead>Site</TableHead>}
                    {showProjectColumn && <TableHead>Project</TableHead>}
                    <TableHead className="text-right">Total Cost</TableHead>
                    <TableHead>Invoice</TableHead>
                    <TableHead>Reason</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((row: MaterialReceipt) => (
                    <TableRow
                      key={row.id}
                      onClick={() => openPurchase(row.id)}
                      className="cursor-pointer hover:bg-muted/30 transition-colors text-xs"
                    >
                      <TableCell className="font-semibold text-foreground">{row.material_name}</TableCell>
                      <TableCell className="text-right font-mono tabular-nums font-medium">
                        {row.quantity} {row.unit}
                      </TableCell>
                      <TableCell className="text-foreground font-medium">
                        {row.supplier ? row.supplier : <span className="text-muted-foreground/60">Direct Receipt</span>}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {row.occurred_date}
                        {row.occurred_time ? ` ${row.occurred_time}` : ''}
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
                      <TableCell className="text-right font-mono tabular-nums font-semibold">
                        <span className={row.total_cost ? '' : 'text-muted-foreground font-normal'}>
                          {formatMoney(row.total_cost)}
                        </span>
                        {row.is_reversed && (
                          <span className="ml-1.5 text-[10px] font-normal text-amber-700 dark:text-amber-400">
                            corrected
                          </span>
                        )}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        {row.invoice_id ? (
                          <button
                            type="button"
                            onClick={() => openInvoice(row.invoice_id!)}
                            className="inline-flex items-center gap-1 text-primary font-semibold hover:underline"
                          >
                            <FileText className="size-3" />
                            View
                          </button>
                        ) : (
                          // Typed in by hand rather than read off a document.
                          // Not a gap to chase — plenty of purchases have no
                          // paperwork to attach.
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px]">
                          {row.movement_reason}
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

      {/* Read-Only Purchase Details Sheet */}
      <PurchaseDetailsSheet id={selectedId} open={sheetOpen} onOpenChange={setSheetOpen} />

      <InvoiceDetailsSheet
        invoiceId={selectedInvoiceId}
        open={invoiceSheetOpen}
        onOpenChange={setInvoiceSheetOpen}
      />
    </div>
  )
}
