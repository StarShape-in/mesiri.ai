import {
  DollarSign,
  Calendar,
  Tag,
  Building2,
  Laptop,
  MessageSquare,
  ShieldCheck,
} from 'lucide-react'
import {
  Sheet,
  SheetContent,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'

interface ExpenseDetailSheetProps {
  expense: any | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onRecordPayment?: (expenseId: string) => void
}

export function ExpenseDetailSheet({
  expense,
  open,
  onOpenChange,
  onRecordPayment,
}: ExpenseDetailSheetProps) {
  if (!expense) return null

  const isPaid = expense.payment_status === 'paid'
  const isPartiallyPaid = expense.payment_status === 'partially_paid'

  const formattedAmount = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: expense.currency || 'INR',
    maximumFractionDigits: 2,
  }).format(expense.amount || 0)

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-[480px] w-full p-0 flex flex-col gap-0 overflow-y-auto">
        {/* Header Banner */}
        <div className="p-5 border-b bg-muted/30 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="font-mono text-xs uppercase bg-background font-semibold">
                {expense.expense_number}
              </Badge>
              {expense.source === 'whatsapp' ? (
                <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 gap-1 text-[11px]">
                  <MessageSquare className="size-3" />
                  WhatsApp Assistant
                </Badge>
              ) : (
                <Badge className="bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border-indigo-500/20 gap-1 text-[11px]">
                  <Laptop className="size-3" />
                  Web Dashboard
                </Badge>
              )}
            </div>

            <Badge
              className={
                isPaid
                  ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-semibold'
                  : isPartiallyPaid
                  ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 font-semibold'
                  : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 font-semibold'
              }
            >
              {isPaid ? 'Settled (Paid)' : isPartiallyPaid ? 'Partially Paid' : 'Unpaid Balance'}
            </Badge>
          </div>

          <div>
            <div className="text-2xl font-bold font-mono text-foreground tracking-tight">
              {formattedAmount}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5 font-medium">
              {expense.description || expense.category_name}
            </p>
          </div>
        </div>

        {/* Main Details & Tabs */}
        <div className="p-5 flex-1 flex flex-col gap-4">
          <Tabs defaultValue="details" className="w-full">
            <TabsList className="w-full grid grid-cols-2 h-9">
              <TabsTrigger value="details" className="text-xs">
                Overview & Scope
              </TabsTrigger>
              <TabsTrigger value="payment" className="text-xs">
                Payment Breakdown
              </TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="details" className="pt-3 flex flex-col gap-3 text-xs">
              <div className="grid grid-cols-2 gap-3 p-3 rounded-lg border bg-card/60">
                <div>
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold block mb-0.5">
                    Category
                  </span>
                  <div className="font-medium flex items-center gap-1.5 text-foreground">
                    <Tag className="size-3.5 text-emerald-500" />
                    {expense.category_name}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold block mb-0.5">
                    Occurred Date
                  </span>
                  <div className="font-medium flex items-center gap-1.5 text-foreground">
                    <Calendar className="size-3.5 text-blue-500" />
                    {expense.occurred_date}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold block mb-0.5">
                    Project Context
                  </span>
                  <div className="font-medium flex items-center gap-1.5 text-foreground truncate">
                    <Building2 className="size-3.5 text-amber-500" />
                    {expense.project_name || 'Organization Wide'}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold block mb-0.5">
                    Site Location
                  </span>
                  <div className="font-medium flex items-center gap-1.5 text-foreground truncate">
                    <Building2 className="size-3.5 text-indigo-500" />
                    {expense.site_name || 'All Sites'}
                  </div>
                </div>
              </div>

              <Separator />

              {/* Vendor & Audit Metadata */}
              <div className="flex flex-col gap-2">
                <h4 className="font-semibold text-foreground text-xs flex items-center gap-1.5">
                  <ShieldCheck className="size-4 text-emerald-500" />
                  Audit & Metadata
                </h4>
                <div className="flex flex-col gap-1.5 text-muted-foreground bg-muted/20 p-2.5 rounded border text-[11px]">
                  <div className="flex justify-between">
                    <span>Payee / Vendor:</span>
                    <span className="font-semibold text-foreground">{expense.vendor_name || 'Direct'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Workflow Status:</span>
                    <span className="font-semibold text-foreground uppercase">{expense.workflow_status}</span>
                  </div>
                  {expense.payment_method && (
                    <div className="flex justify-between">
                      <span>Payment Method:</span>
                      <span className="font-semibold text-foreground uppercase">{expense.payment_method}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span>Recorded By:</span>
                    <span className="font-semibold text-foreground">{expense.recorded_by || 'Dashboard User'}</span>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* Payment History Tab */}
            <TabsContent value="payment" className="pt-3 flex flex-col gap-3 text-xs">
              <div className="p-3 border rounded-lg bg-card/60 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground">Settlement Status</span>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {isPaid ? '100% Paid' : isPartiallyPaid ? 'Partial' : '0% Paid'}
                  </Badge>
                </div>
                <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={`h-full ${isPaid ? 'bg-emerald-500' : isPartiallyPaid ? 'bg-amber-500' : 'bg-rose-500'}`}
                    style={{ width: isPaid ? '100%' : isPartiallyPaid ? '50%' : '0%' }}
                  />
                </div>
                <div className="flex justify-between text-[11px] text-muted-foreground pt-1">
                  <span>Paid: {isPaid ? formattedAmount : '₹0.00'}</span>
                  <span>Outstanding: {isPaid ? '₹0.00' : formattedAmount}</span>
                </div>
              </div>

              {!isPaid && (
                <Button
                  size="sm"
                  className="w-full bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 font-semibold"
                  onClick={() => onRecordPayment?.(expense.id)}
                >
                  <DollarSign className="size-4" />
                  Record Settlement Payment
                </Button>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  )
}
