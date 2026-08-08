import { useNavigate } from 'react-router-dom'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import {
  Receipt,
  User,
  Tag,
  Store,
  Landmark,
  MessageSquare,
  ExternalLink,
  ChevronLeft,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Hash,
} from 'lucide-react'

export interface ExpenseDetailData {
  id: string
  amount: number
  category_name?: string
  category_id?: string
  vendor_name?: string
  vendor_id?: string
  account_name?: string
  account_id?: string
  custodian_name?: string
  custodian_user_id?: string
  project_name?: string
  site_name?: string
  recorded_date?: string
  payment_method?: string
  status?: string
  receipt_url?: string
  description?: string
  correlation_id?: string
  whatsapp_sender?: string
  raw_message_text?: string
}

interface ExpenseDetailSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  expense: ExpenseDetailData | null
  onOpenAccount?: (accountId: string) => void
  onOpenVendor?: (vendorId: string) => void
  onOpenCategory?: (categoryId: string) => void
  onOpenCustodian?: (custodianIdOrName: string) => void
  onOpenWhatsAppTrace?: (correlationId: string) => void
  onBack?: () => void
  hasHistoryBack?: boolean
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

export function ExpenseDetailSheet({
  open,
  onOpenChange,
  expense,
  onOpenAccount,
  onOpenVendor,
  onOpenCategory,
  onOpenCustodian,
  onOpenWhatsAppTrace,
  onBack,
  hasHistoryBack,
}: ExpenseDetailSheetProps) {
  const navigate = useNavigate()
  if (!expense) return null

  const isConfirmed = expense.status === 'confirmed' || expense.status === 'approved' || !expense.status
  const isVoided = expense.status === 'voided' || expense.status === 'reversed'

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md w-full p-0 flex flex-col gap-0 bg-background overflow-hidden border-l">
        {/* Drawer Header */}
        <SheetHeader className="p-4 border-b bg-muted/30">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {hasHistoryBack && onBack && (
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-7 text-muted-foreground hover:text-foreground"
                  onClick={onBack}
                  title="Back to previous detail"
                >
                  <ChevronLeft className="size-4" />
                </Button>
              )}
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                <Receipt className="size-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <SheetTitle className="text-sm font-bold text-foreground">
                    Expense #{expense.id.slice(0, 8)}
                  </SheetTitle>
                  {isConfirmed ? (
                    <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-[10px]">
                      <CheckCircle2 className="size-3 mr-1" />
                      Confirmed
                    </Badge>
                  ) : isVoided ? (
                    <Badge variant="destructive" className="text-[10px]">
                      <XCircle className="size-3 mr-1" />
                      Voided
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px]">
                      <AlertCircle className="size-3 mr-1" />
                      {expense.status}
                    </Badge>
                  )}
                </div>
                <SheetDescription className="text-[11px] text-muted-foreground">
                  Recorded on {expense.recorded_date || 'Today'}
                </SheetDescription>
              </div>
            </div>

            <Button
              size="sm"
              variant="outline"
              className="h-7 text-[11px] font-semibold gap-1 text-emerald-600 border-emerald-500/30 hover:bg-emerald-500/10"
              onClick={() => {
                onOpenChange(false)
                navigate(`/finance/expenses/${expense.id}`)
              }}
            >
              Open Page →
            </Button>
          </div>
        </SheetHeader>

        {/* Amount Banner */}
        <div className="px-5 py-4 bg-muted/20 border-b flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground block">
              Expense Amount
            </span>
            <span className="text-2xl font-black font-mono tracking-tight text-foreground">
              {formatCurrency(expense.amount)}
            </span>
          </div>
          <Badge variant="outline" className="font-mono text-xs capitalize bg-background">
            {expense.payment_method || 'UPI / Bank'}
          </Badge>
        </div>

        {/* Body Content */}
        <div className="p-5 flex-1 overflow-y-auto flex flex-col gap-4 text-xs">
          {/* Attached Receipt Image */}
          <div className="space-y-1.5">
            <span className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1.5">
              <Receipt className="size-3.5 text-emerald-500" />
              Attached Receipt Document
            </span>
            {expense.receipt_url ? (
              <div className="relative group rounded-lg overflow-hidden border bg-muted/40 max-h-48 flex items-center justify-center">
                <img
                  src={expense.receipt_url}
                  alt="Expense Receipt"
                  className="object-cover w-full h-full max-h-48 transition-transform group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <a
                    href={expense.receipt_url}
                    target="_blank"
                    rel="noreferrer"
                    className="p-2 rounded-full bg-white text-black hover:bg-white/90 shadow-md"
                  >
                    <ExternalLink className="size-4" />
                  </a>
                </div>
              </div>
            ) : (
              <Card className="p-4 border-dashed text-center text-muted-foreground flex flex-col items-center gap-1 bg-muted/10">
                <Receipt className="size-6 text-muted-foreground/40" />
                <span className="text-[11px] font-medium">No receipt photo attached</span>
              </Card>
            )}
          </div>

          {/* Connected Entities Links */}
          <div className="grid grid-cols-2 gap-2.5">
            {/* Category */}
            <div className="p-2.5 rounded-lg border bg-card flex flex-col gap-1">
              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                <Tag className="size-3 text-indigo-500" />
                Category
              </span>
              <button
                type="button"
                onClick={() => expense.category_id && onOpenCategory?.(expense.category_id)}
                className="font-bold text-xs text-foreground hover:text-indigo-600 text-left transition-colors truncate"
              >
                {expense.category_name || 'General Operations'}
              </button>
            </div>

            {/* Vendor */}
            <div className="p-2.5 rounded-lg border bg-card flex flex-col gap-1">
              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                <Store className="size-3 text-emerald-500" />
                Vendor / Payee
              </span>
              <button
                type="button"
                onClick={() => expense.vendor_id && onOpenVendor?.(expense.vendor_id)}
                className="font-bold text-xs text-foreground hover:text-emerald-600 text-left transition-colors truncate"
              >
                {expense.vendor_name || 'Direct Disbursement'}
              </button>
            </div>

            {/* Paid Account */}
            <div className="p-2.5 rounded-lg border bg-card flex flex-col gap-1">
              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                <Landmark className="size-3 text-blue-500" />
                Paid Account
              </span>
              <button
                type="button"
                onClick={() => expense.account_id && onOpenAccount?.(expense.account_id)}
                className="font-bold text-xs text-foreground hover:text-blue-600 text-left transition-colors truncate"
              >
                {expense.account_name || 'Main Bank Account'}
              </button>
            </div>

            {/* Custodian */}
            <div className="p-2.5 rounded-lg border bg-card flex flex-col gap-1">
              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                <User className="size-3 text-amber-500" />
                Custodian / User
              </span>
              <button
                type="button"
                onClick={() =>
                  (expense.custodian_user_id || expense.custodian_name) &&
                  onOpenCustodian?.(expense.custodian_user_id || expense.custodian_name || '')
                }
                className="font-bold text-xs text-foreground hover:text-amber-600 text-left transition-colors truncate"
              >
                {expense.custodian_name || 'Finance Custodian'}
              </button>
            </div>
          </div>

          {/* Description */}
          {expense.description && (
            <div className="p-3 rounded-lg border bg-muted/20 space-y-1">
              <span className="text-[10px] font-semibold text-muted-foreground block">Description / Notes</span>
              <p className="text-xs text-foreground">{expense.description}</p>
            </div>
          )}

          {/* WhatsApp Channel Audit Trace */}
          {(expense.correlation_id || expense.whatsapp_sender) && (
            <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                  <MessageSquare className="size-3.5 text-emerald-500" />
                  WhatsApp Origin Audit Trace
                </span>
                {expense.correlation_id && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-[10px] font-mono gap-1 text-emerald-600 hover:bg-emerald-500/10 px-2"
                    onClick={() => onOpenWhatsAppTrace?.(expense.correlation_id!)}
                  >
                    <Hash className="size-3" />
                    {expense.correlation_id.slice(0, 10)}...
                  </Button>
                )}
              </div>
              {expense.whatsapp_sender && (
                <div className="text-[11px] text-muted-foreground">
                  Sender Phone: <span className="font-mono font-semibold text-foreground">{expense.whatsapp_sender}</span>
                </div>
              )}
              {expense.raw_message_text && (
                <div className="p-2 rounded bg-background border text-[11px] italic font-mono text-muted-foreground">
                  "{expense.raw_message_text}"
                </div>
              )}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
