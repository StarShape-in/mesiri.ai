import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  ShoppingBag,
  Building2,
  Calendar,
  User,
  FileText,
  MapPin,
  DollarSign,
  Hash,
  ChevronDown,
} from 'lucide-react'
import { fetchInflow } from '@/lib/materials'
import { fetchProjects, fetchSites } from '@/lib/projects'

interface PurchaseDetailsSheetProps {
  id: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function PurchaseDetailsSheet({ id, open, onOpenChange }: PurchaseDetailsSheetProps) {
  const { data: item, isLoading, isError } = useQuery({
    queryKey: ['materials', 'purchase-detail', id],
    queryFn: () => fetchInflow(id!),
    enabled: !!id && open,
  })

  const projectId = item?.project_id
  const { data: projects = [] } = useQuery({
    queryKey: ['scope-projects'],
    queryFn: fetchProjects,
    staleTime: 60_000,
    enabled: open,
  })

  const { data: sites = [] } = useQuery({
    queryKey: ['scope-sites', projectId],
    queryFn: () => fetchSites(projectId!),
    enabled: !!projectId && open,
    staleTime: 60_000,
  })

  const projectName = React.useMemo(() => {
    if (!item?.project_id) return '—'
    return projects.find((p) => p.id === item.project_id)?.name ?? item.project_id.slice(0, 8)
  }, [projects, item?.project_id])

  const siteName = React.useMemo(() => {
    if (!item?.site_id) return 'Portfolio / All Sites'
    return sites.find((s) => s.id === item.site_id)?.name ?? item.site_id.slice(0, 8)
  }, [sites, item?.site_id])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md overflow-y-auto">
        <SheetHeader className="border-b pb-3">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-full border border-primary/20 bg-primary/10 flex items-center justify-center text-primary shrink-0">
              <ShoppingBag className="size-4" />
            </div>
            <div>
              <SheetTitle className="text-base font-bold">Purchase Record</SheetTitle>
              <SheetDescription className="text-xs">Read-only purchase receipt details</SheetDescription>
            </div>
          </div>
        </SheetHeader>

        {isLoading ? (
          <div className="space-y-4 py-4">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : isError || !item ? (
          <div className="py-8 text-center text-xs text-muted-foreground">
            Failed to load purchase record details.
          </div>
        ) : (
          <div className="space-y-5 py-4 text-xs">
            {/* Header Banner */}
            <div className="rounded-lg border bg-muted/40 p-3 flex items-center justify-between">
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">
                  Material
                </span>
                <p className="text-sm font-bold text-foreground">{item.material_name}</p>
              </div>
              <div className="text-right">
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">
                  Quantity
                </span>
                <p className="text-sm font-bold font-mono text-primary">
                  {item.quantity} {item.unit}
                </p>
              </div>
            </div>

            {/* General Information */}
            <div className="space-y-2">
              <h4 className="font-bold text-foreground flex items-center gap-1.5 text-xs border-b pb-1">
                <Calendar className="size-3.5 text-primary" />
                General Information
              </h4>
              <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                <div>
                  <span className="text-[10px] uppercase font-bold block text-muted-foreground/70">
                    Purchase Date
                  </span>
                  <span className="font-medium text-foreground">
                    {item.occurred_date} {item.occurred_time ? `at ${item.occurred_time}` : ''}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold block text-muted-foreground/70">
                    Source
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {item.source}
                  </Badge>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold block text-muted-foreground/70">
                    Recorded By
                  </span>
                  <span className="font-medium text-foreground flex items-center gap-1">
                    <User className="size-3" />
                    {item.created_by ? item.created_by.slice(0, 8) : 'System / User'}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold block text-muted-foreground/70">
                    Reason / Purpose
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {item.movement_reason}
                  </Badge>
                </div>
              </div>
            </div>

            {/* Supplier Information */}
            <div className="space-y-2">
              <h4 className="font-bold text-foreground flex items-center gap-1.5 text-xs border-b pb-1">
                <Building2 className="size-3.5 text-primary" />
                Supplier / Vendor Information
              </h4>
              <div className="rounded-md border p-2.5 bg-background">
                <span className="text-[10px] uppercase font-bold block text-muted-foreground/70">
                  Supplier Name
                </span>
                <p className="font-bold text-foreground text-xs mt-0.5">
                  {item.supplier || 'Not Specified (Direct Receipt)'}
                </p>
              </div>
            </div>

            {/* Site & Project Scope */}
            <div className="space-y-2">
              <h4 className="font-bold text-foreground flex items-center gap-1.5 text-xs border-b pb-1">
                <MapPin className="size-3.5 text-primary" />
                Site & Project Scope
              </h4>
              <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                <div>
                  <span className="text-[10px] uppercase font-bold block text-muted-foreground/70">
                    Project
                  </span>
                  <span className="font-medium text-foreground">{projectName}</span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold block text-muted-foreground/70">
                    Site
                  </span>
                  <span className="font-medium text-foreground">{siteName}</span>
                </div>
              </div>
            </div>

            {/* Cost Information (If Available) */}
            <div className="space-y-2">
              <h4 className="font-bold text-foreground flex items-center gap-1.5 text-xs border-b pb-1">
                <DollarSign className="size-3.5 text-primary" />
                Cost Information
              </h4>
              <div className="grid grid-cols-2 gap-2 text-muted-foreground">
                <div>
                  <span className="text-[10px] uppercase font-bold block text-muted-foreground/70">
                    Unit Cost
                  </span>
                  <span className="font-medium text-foreground">
                    {item.unit_cost ? `₹${item.unit_cost}` : 'Not Specified'}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold block text-muted-foreground/70">
                    Total Cost
                  </span>
                  <span className="font-medium text-foreground font-mono font-bold">
                    {item.total_cost ? `₹${item.total_cost}` : 'Not Specified'}
                  </span>
                </div>
              </div>
            </div>

            {/* Additional Notes */}
            {item.notes && (
              <div className="space-y-1.5">
                <h4 className="font-bold text-foreground flex items-center gap-1.5 text-xs border-b pb-1">
                  <FileText className="size-3.5 text-primary" />
                  Additional Notes
                </h4>
                <p className="text-xs text-muted-foreground bg-muted/30 p-2 rounded border">
                  {item.notes}
                </p>
              </div>
            )}

            {/* Technical Identifiers (Collapsed details for Storekeeper UX) */}
            <details className="group rounded-md border bg-muted/20 p-2 text-[11px] text-muted-foreground">
              <summary className="cursor-pointer font-semibold flex items-center justify-between text-muted-foreground hover:text-foreground">
                <span className="flex items-center gap-1">
                  <Hash className="size-3 text-primary" />
                  Advanced Technical Metadata
                </span>
                <ChevronDown className="size-3 transition-transform group-open:rotate-180" />
              </summary>
              <div className="space-y-1 font-mono text-[11px] mt-2 pt-2 border-t border-border/40">
                <div className="flex justify-between border-b border-border/40 pb-0.5">
                  <span>Receipt ID:</span>
                  <span className="text-foreground">{item.id}</span>
                </div>
                {item.correlation_id && (
                  <div className="flex justify-between border-b border-border/40 pb-0.5">
                    <span>Correlation ID:</span>
                    <span className="text-foreground">{item.correlation_id}</span>
                  </div>
                )}
                {item.material_id && (
                  <div className="flex justify-between border-b border-border/40 pb-0.5">
                    <span>Catalog Material ID:</span>
                    <span className="text-foreground">{item.material_id}</span>
                  </div>
                )}
                {item.unit_id && (
                  <div className="flex justify-between">
                    <span>Stock Unit ID:</span>
                    <span className="text-foreground">{item.unit_id}</span>
                  </div>
                )}
              </div>
            </details>

            {item.reverses_movement_id && (
              <div className="p-2 bg-rose-500/10 border border-rose-500/30 rounded text-rose-600 dark:text-rose-400 font-semibold text-[11px]">
                ⚠️ Reversal Note: This purchase is an adjustment row reversing movement {item.reverses_movement_id.slice(0, 8)}.
              </div>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
