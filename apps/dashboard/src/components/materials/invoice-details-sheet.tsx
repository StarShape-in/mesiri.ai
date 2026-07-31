import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, AlertTriangle, FileText, ExternalLink, Receipt } from 'lucide-react'
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
import {
  fetchInvoice,
  fetchInvoiceAttachment,
  formatMoney,
  type MaterialInvoice,
} from '@/lib/materials'

interface InvoiceDetailsSheetProps {
  invoiceId: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * One supplier document: who supplied it, every material on it, what it cost,
 * the Finance expense it created, and the original image or PDF.
 *
 * The document is the point. When a delivery is disputed weeks later, the
 * answer is the piece of paper the supplier sent, not our retyping of it.
 */
export function InvoiceDetailsSheet({ invoiceId, open, onOpenChange }: InvoiceDetailsSheetProps) {
  const {
    data: invoice,
    isLoading,
    isError,
    refetch,
  } = useQuery<MaterialInvoice>({
    queryKey: ['materials', 'invoice', invoiceId],
    queryFn: () => fetchInvoice(invoiceId!),
    enabled: !!invoiceId && open,
  })

  // Fetched separately and lazily: the link is short-lived, so there is no
  // point minting one until the sheet is actually open and a document exists.
  const {
    data: attachment,
    isLoading: attachmentLoading,
    isError: attachmentError,
  } = useQuery({
    queryKey: ['materials', 'invoice-attachment', invoiceId],
    queryFn: () => fetchInvoiceAttachment(invoiceId!),
    enabled: !!invoiceId && open && !!invoice?.has_attachment,
    retry: false,
  })

  const linesTotal = React.useMemo(() => {
    if (!invoice) return null
    const sum = invoice.lines.reduce((acc, l) => acc + (Number(l.total_cost) || 0), 0)
    return sum > 0 ? sum : null
  }, [invoice])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Supplier Invoice</SheetTitle>
          <SheetDescription>Every material on this document, and the original.</SheetDescription>
        </SheetHeader>

        <div className="px-4 pb-4 text-xs space-y-4">
          {isLoading && (
            <div className="flex items-center justify-center py-10 gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin text-primary" />
              Loading invoice...
            </div>
          )}

          {isError && (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <AlertTriangle className="size-6 text-rose-500" />
              <p className="text-muted-foreground">Failed to load this invoice.</p>
              <Button size="sm" variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </div>
          )}

          {invoice && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Supplier">
                  <span className="font-semibold text-foreground">
                    {invoice.vendor_name ?? invoice.supplier_name ?? '—'}
                  </span>
                  {invoice.vendor_name && invoice.supplier_name &&
                    invoice.vendor_name !== invoice.supplier_name && (
                      // The document's own words are kept even when a vendor
                      // record matched, so a later rename can't rewrite history.
                      <span className="block text-[10px] text-muted-foreground">
                        on document: {invoice.supplier_name}
                      </span>
                    )}
                </Field>
                <Field label="Invoice Date">{invoice.invoice_date ?? '—'}</Field>
                <Field label="Invoice No.">{invoice.invoice_number ?? '—'}</Field>
                <Field label="Invoice Total">
                  <span className="font-mono font-bold text-foreground">
                    {formatMoney(invoice.invoice_total)}
                  </span>
                </Field>
              </div>

              <div>
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-1.5">
                  Materials ({invoice.lines.length})
                </div>
                <div className="rounded-md border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Material</TableHead>
                        <TableHead className="text-xs text-right">Qty</TableHead>
                        <TableHead className="text-xs text-right">Rate</TableHead>
                        <TableHead className="text-xs text-right">Total</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {invoice.lines.map((line) => (
                        <TableRow key={line.id} className="text-xs">
                          <TableCell className="font-medium">{line.material_name}</TableCell>
                          <TableCell className="text-right font-mono tabular-nums">
                            {line.quantity} {line.unit}
                          </TableCell>
                          <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                            {formatMoney(line.unit_cost)}
                          </TableCell>
                          <TableCell className="text-right font-mono tabular-nums">
                            {formatMoney(line.total_cost)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                {/* Tax and freight are deliberately not extracted, so the
                    printed total is normally higher than the lines add up to.
                    Stated plainly rather than flagged as a discrepancy — the
                    gap is expected on almost every real invoice. */}
                {linesTotal !== null && invoice.invoice_total &&
                  Math.abs(Number(invoice.invoice_total) - linesTotal) > 0.5 && (
                    <p className="mt-1.5 text-[10px] text-muted-foreground">
                      Lines add up to {formatMoney(String(linesTotal))}. The difference from the
                      invoice total is normally tax and delivery, which aren't recorded separately.
                    </p>
                  )}
              </div>

              {invoice.expense_id && (
                <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-2.5 flex items-start gap-2">
                  <Receipt className="size-3.5 shrink-0 mt-0.5 text-emerald-600 dark:text-emerald-400" />
                  <div>
                    <p className="font-semibold text-emerald-700 dark:text-emerald-400">
                      Recorded in Finance as an unpaid expense
                    </p>
                    <p className="text-muted-foreground text-[10px]">
                      Nobody needs to enter this invoice again.
                    </p>
                  </div>
                </div>
              )}

              <div className="space-y-1.5 pt-2 border-t">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                  Original Document
                </span>
                {!invoice.has_attachment ? (
                  <p className="text-muted-foreground">No document was attached to this invoice.</p>
                ) : attachmentLoading ? (
                  <p className="text-muted-foreground">Preparing link...</p>
                ) : attachment ? (
                  <Button asChild size="sm" variant="outline" className="h-8 gap-1.5 text-xs">
                    <a href={attachment.url} target="_blank" rel="noreferrer">
                      <FileText className="size-3.5" />
                      View original
                      <ExternalLink className="size-3" />
                    </a>
                  </Button>
                ) : (
                  // The reference is stored and correct; only the storage
                  // provider is unreachable. Say that, rather than implying the
                  // document was lost.
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <FileText className="size-3.5" />
                    <span>
                      {attachmentError
                        ? 'Document attached — viewing is not available yet.'
                        : 'Document attached.'}
                    </span>
                  </div>
                )}
              </div>

              {invoice.notes && (
                <div className="space-y-1">
                  <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                    Notes
                  </span>
                  <p className="text-foreground leading-relaxed">{invoice.notes}</p>
                </div>
              )}

              <div className="pt-1">
                <Badge variant="outline" className="text-[10px] font-mono">
                  {invoice.id}
                </Badge>
              </div>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold block">
        {label}
      </span>
      <div className="text-foreground">{children}</div>
    </div>
  )
}
