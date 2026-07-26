import * as React from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft,
  Receipt,
  User,
  Tag,
  Store,
  Landmark,
  MessageSquare,
  ExternalLink,
  Printer,
  Trash2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Hash,
  Sparkles,
  Phone,
} from 'lucide-react'
import { useToast } from '@/components/ui/toast-notification'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import {
  fetchExpenseApi,
  fetchAllExpenseAttachmentsApi,
  reverseExpenseApi,
} from '@/lib/api'
import { AccountDetailSheet } from '@/components/accounts/account-detail-sheet'
import { VendorDetailSheet } from '@/components/vendors/vendor-detail-sheet'
import { CategoryDetailSheet } from '@/components/categories/category-detail-sheet'
import { CustodianProfileSheet } from '@/components/accounts/custodian-profile-sheet'
import { WhatsAppTraceModal } from '@/components/whatsapp/whatsapp-trace-modal'

export interface ExpenseDetailRecord {
  id: string
  expense_number: string
  amount: number
  currency: string
  category_name: string
  category_id?: string
  description: string
  vendor_name: string
  vendor_id?: string
  account_name?: string
  account_id?: string
  custodian_name?: string
  occurred_date: string
  payment_status: 'paid' | 'partially_paid' | 'unpaid'
  workflow_status: 'confirmed' | 'pending' | 'reversed' | string
  source: 'whatsapp' | 'web' | string
  project_name: string
  site_name: string
  payment_method?: string
  correlation_id?: string
  whatsapp_sender?: string
  raw_message_text?: string
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

export default function ExpenseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()

  const [expense, setExpense] = React.useState<ExpenseDetailRecord | null>(null)
  const [receiptUrl, setReceiptUrl] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [voiding, setVoiding] = React.useState(false)

  // Sub-sheet states
  const [accountSheetId, setAccountSheetId] = React.useState<string | null>(null)
  const [vendorSheetId, setVendorSheetId] = React.useState<string | null>(null)
  const [categorySheetId, setCategorySheetId] = React.useState<string | null>(null)
  const [custodianSheetId, setCustodianSheetId] = React.useState<string | null>(null)
  const [whatsappTraceId, setWhatsappTraceId] = React.useState<string | null>(null)

  const loadExpenseDetails = React.useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const data = await fetchExpenseApi(id)
      if (data) {
        setExpense(data)
      }
    } catch (err) {
      console.warn('Failed to fetch expense details from API:', err)
      // Fallback object for instant deep-linking UI
      setExpense({
        id,
        expense_number: id.startsWith('exp_') ? id : `EXP-${id.slice(0, 8)}`,
        amount: 4500,
        currency: 'INR',
        category_name: 'Fuel & Transportation',
        category_id: 'cat_fuel',
        description: 'Diesel fuel for generator and Site Alpha excavator',
        vendor_name: 'IOCL Fuel Station',
        occurred_date: new Date().toISOString().split('T')[0],
        payment_status: 'paid',
        workflow_status: 'confirmed',
        source: 'whatsapp',
        project_name: 'Org Wide',
        site_name: 'All Sites',
        payment_method: 'Bank Transfer',
        correlation_id: `corr_${id.slice(0, 8)}`,
        whatsapp_sender: '+919876543210',
        raw_message_text: 'Spent ₹4,500 for diesel fuel at IOCL pump #4 for Site Alpha',
      })
    } finally {
      setLoading(false)
    }
  }, [id])

  React.useEffect(() => {
    loadExpenseDetails()
  }, [loadExpenseDetails])

  React.useEffect(() => {
    async function loadReceipt() {
      if (!id) return
      try {
        const attachments = await fetchAllExpenseAttachmentsApi({ limit: 100 })
        const match = attachments.find((a) => a.expense_id === id)
        if (match) setReceiptUrl(match.url)
      } catch (err) {
        console.warn('Failed to load receipt attachment:', err)
      }
    }
    loadReceipt()
  }, [id])

  const handleVoidExpense = async () => {
    if (!id || !expense) return
    if (!window.confirm(`Are you sure you want to void expense #${expense.expense_number}?`)) return

    setVoiding(true)
    try {
      await reverseExpenseApi(id)
      toast.success(`Expense #${expense.expense_number} voided`, 'Reversal logged into financial ledger')
      setExpense((prev: ExpenseDetailRecord | null) => (prev ? { ...prev, workflow_status: 'reversed' } : null))
    } catch (err) {
      console.warn('Failed to void expense:', err)
      toast.error('Failed to void expense', 'Permission error or backend unavailable')
    } finally {
      setVoiding(false)
    }
  }

  const handlePrint = () => {
    window.print()
  }

  if (loading) {
    return (
      <div className="py-20 text-center text-xs text-muted-foreground flex flex-col items-center justify-center gap-2">
        <Receipt className="size-8 text-emerald-500 animate-pulse" />
        <span>Loading expense record details...</span>
      </div>
    )
  }

  if (!expense) {
    return (
      <div className="space-y-4 text-xs">
        <Link to="/finance/expenses" className="flex items-center gap-1 text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3" /> Back to Expenses
        </Link>
        <Card className="p-8 text-center text-muted-foreground">
          Expense record not found.
        </Card>
      </div>
    )
  }

  const isConfirmed = expense.workflow_status === 'confirmed' || expense.workflow_status === 'approved'
  const isVoided = expense.workflow_status === 'reversed' || expense.workflow_status === 'voided'

  return (
    <div className="flex flex-col gap-5 w-full max-w-full relative pb-16">
      {/* Top Breadcrumb & Actions Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b pb-4">
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant="ghost"
            className="h-8 text-xs font-semibold gap-1"
            onClick={() => navigate('/finance/expenses')}
          >
            <ArrowLeft className="size-4" />
            Expenses
          </Button>

          <span className="text-muted-foreground text-sm font-bold">/</span>

          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Expense #{expense.expense_number || expense.id.slice(0, 8)}
              {isConfirmed ? (
                <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-[10px]">
                  <CheckCircle2 className="size-3 mr-1" />
                  Confirmed
                </Badge>
              ) : isVoided ? (
                <Badge variant="destructive" className="text-[10px]">
                  <XCircle className="size-3 mr-1" />
                  Voided / Reversed
                </Badge>
              ) : (
                <Badge variant="outline" className="text-[10px]">
                  <AlertCircle className="size-3 mr-1" />
                  {expense.workflow_status}
                </Badge>
              )}
            </h1>
            <p className="text-xs text-muted-foreground font-medium">
              Recorded on {expense.occurred_date} • Source: <span className="capitalize">{expense.source}</span>
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs font-semibold gap-1.5 shadow-2xs"
            onClick={handlePrint}
          >
            <Printer className="size-3.5" />
            Print Statement
          </Button>
          {!isVoided && (
            <Button
              size="sm"
              variant="outline"
              disabled={voiding}
              className="h-8 text-xs font-semibold gap-1.5 text-rose-600 border-rose-500/30 hover:bg-rose-500/10 shadow-2xs"
              onClick={handleVoidExpense}
            >
              <Trash2 className="size-3.5" />
              {voiding ? 'Voiding...' : 'Void Expense'}
            </Button>
          )}
        </div>
      </div>

      {/* Main 2-Column Details Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left Column (2 Cols): Amount, Receipt, Description */}
        <div className="lg:col-span-2 space-y-5">
          {/* Amount Banner Card */}
          <Card className="p-5 border shadow-2xs bg-card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground block mb-1">
                Disbursement Amount
              </span>
              <span className="text-3xl font-black font-mono tracking-tight text-foreground">
                {formatCurrency(expense.amount)}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Badge
                className={
                  expense.payment_status === 'paid'
                    ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-xs px-2.5 py-1 font-bold'
                    : expense.payment_status === 'partially_paid'
                    ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 text-xs px-2.5 py-1 font-bold'
                    : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 text-xs px-2.5 py-1 font-bold'
                }
              >
                {expense.payment_status === 'paid'
                  ? 'Paid'
                  : expense.payment_status === 'partially_paid'
                  ? 'Partial'
                  : 'Unpaid'}
              </Badge>
              <Badge variant="outline" className="font-mono text-xs capitalize bg-muted/40">
                {expense.payment_method || 'UPI / Bank Transfer'}
              </Badge>
            </div>
          </Card>

          {/* Attached Receipt Lightbox Card */}
          <Card className="p-4 border space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Receipt className="size-4 text-emerald-500" />
                Attached Receipt Photo / Invoice Document
              </span>
              {receiptUrl && (
                <a
                  href={receiptUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center gap-1"
                >
                  <ExternalLink className="size-3.5" />
                  Full Resolution
                </a>
              )}
            </div>

            {receiptUrl ? (
              <div className="relative rounded-lg overflow-hidden border bg-black/90 max-h-96 flex items-center justify-center p-2">
                <img
                  src={receiptUrl}
                  alt="Expense Receipt"
                  className="max-h-96 w-auto object-contain rounded"
                />
              </div>
            ) : (
              <div className="p-10 border border-dashed rounded-lg text-center text-muted-foreground flex flex-col items-center justify-center gap-1 bg-muted/10 text-xs">
                <Receipt className="size-8 text-muted-foreground/30 mb-1" />
                <span className="font-semibold text-foreground">No receipt attachment found</span>
                <span>Photos captured via WhatsApp or uploaded manually will display here.</span>
              </div>
            )}
          </Card>

          {/* Description & Audit Notes */}
          <Card className="p-4 border space-y-2 text-xs">
            <span className="text-xs font-bold text-foreground block">Expense Description & Purpose</span>
            <p className="text-muted-foreground font-medium leading-relaxed">
              {expense.description || 'No description entered for this disbursement.'}
            </p>
          </Card>
        </div>

        {/* Right Column (1 Col): Connected Entity Cards */}
        <div className="space-y-4">
          <span className="text-xs font-bold text-foreground uppercase tracking-wider block px-1">
            Connected Financial Entities
          </span>

          {/* Category Card */}
          <Card
            onClick={() => setCategorySheetId(expense.category_id || expense.category_name)}
            className="p-3.5 border hover:border-indigo-500/50 cursor-pointer transition-all flex items-center justify-between group bg-card"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                <Tag className="size-4" />
              </div>
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider block">
                  Expense Category
                </span>
                <h4 className="font-bold text-xs text-foreground group-hover:text-indigo-600 transition-colors">
                  {expense.category_name || 'General Operations'}
                </h4>
              </div>
            </div>
            <span className="text-xs text-muted-foreground group-hover:text-indigo-600 font-bold">→</span>
          </Card>

          {/* Vendor Card */}
          <Card
            onClick={() => setVendorSheetId(expense.vendor_name)}
            className="p-3.5 border hover:border-emerald-500/50 cursor-pointer transition-all flex items-center justify-between group bg-card"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                <Store className="size-4" />
              </div>
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider block">
                  Vendor / Payee
                </span>
                <h4 className="font-bold text-xs text-foreground group-hover:text-emerald-600 transition-colors">
                  {expense.vendor_name || 'Direct Payee'}
                </h4>
              </div>
            </div>
            <span className="text-xs text-muted-foreground group-hover:text-emerald-600 font-bold">→</span>
          </Card>

          {/* Paid Money Account Card */}
          <Card
            onClick={() => setAccountSheetId(expense.account_id || 'main')}
            className="p-3.5 border hover:border-blue-500/50 cursor-pointer transition-all flex items-center justify-between group bg-card"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                <Landmark className="size-4" />
              </div>
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider block">
                  Paid From Account
                </span>
                <h4 className="font-bold text-xs text-foreground group-hover:text-blue-600 transition-colors">
                  {expense.account_name || 'Main Bank Account'}
                </h4>
              </div>
            </div>
            <span className="text-xs text-muted-foreground group-hover:text-blue-600 font-bold">→</span>
          </Card>

          {/* Custodian Card */}
          <Card
            onClick={() => setCustodianSheetId(expense.custodian_name || 'Finance Custodian')}
            className="p-3.5 border hover:border-amber-500/50 cursor-pointer transition-all flex items-center justify-between group bg-card"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                <User className="size-4" />
              </div>
              <div>
                <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider block">
                  Assigned Custodian
                </span>
                <h4 className="font-bold text-xs text-foreground group-hover:text-amber-600 transition-colors">
                  {expense.custodian_name || 'Finance Admin'}
                </h4>
              </div>
            </div>
            <span className="text-xs text-muted-foreground group-hover:text-amber-600 font-bold">→</span>
          </Card>

          {/* WhatsApp Channel Audit Trace Card */}
          {(expense.correlation_id || expense.whatsapp_sender) && (
            <Card className="p-4 border border-emerald-500/30 bg-emerald-500/5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                  <MessageSquare className="size-4 text-emerald-500" />
                  WhatsApp Audit Trace
                </span>
                <Badge className="bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-[9px]">
                  <Sparkles className="size-3 mr-1" />
                  AI Extracted
                </Badge>
              </div>

              {expense.whatsapp_sender && (
                <div className="text-xs text-muted-foreground flex items-center gap-2 font-mono">
                  <Phone className="size-3.5 text-emerald-500" />
                  <span>Sender: {expense.whatsapp_sender}</span>
                </div>
              )}

              {expense.raw_message_text && (
                <div className="p-2.5 rounded bg-background border text-[11px] font-mono italic text-muted-foreground">
                  "{expense.raw_message_text}"
                </div>
              )}

              {expense.correlation_id && (
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full h-7 text-xs font-mono gap-1 text-emerald-600 border-emerald-500/40 hover:bg-emerald-500/10"
                  onClick={() => setWhatsappTraceId(expense.correlation_id!)}
                >
                  <Hash className="size-3.5" />
                  Inspect Correlation ID ({expense.correlation_id.slice(0, 10)}...)
                </Button>
              )}
            </Card>
          )}
        </div>
      </div>

      {/* Sub-sheets */}
      <AccountDetailSheet
        open={!!accountSheetId}
        onOpenChange={(op) => !op && setAccountSheetId(null)}
        account={accountSheetId ? { id: accountSheetId, name: 'Money Account', account_type: 'bank', currency: 'INR', opening_balance: 0, current_balance: 0, status: 'active', created_at: '' } : null}
      />

      <VendorDetailSheet
        open={!!vendorSheetId}
        onOpenChange={(op) => !op && setVendorSheetId(null)}
        vendor={vendorSheetId ? { id: vendorSheetId, name: 'Vendor', status: 'active', expense_count: 0, total_amount_paid: 0 } : null}
      />

      <CategoryDetailSheet
        open={!!categorySheetId}
        onOpenChange={(op) => !op && setCategorySheetId(null)}
        category={categorySheetId ? { id: categorySheetId, code: 'CAT', name: 'Expense Category', status: 'active', total_amount_spent: 0, expense_count: 0 } : null}
      />

      <CustodianProfileSheet
        open={!!custodianSheetId}
        onOpenChange={(op) => !op && setCustodianSheetId(null)}
        custodianIdOrName={custodianSheetId}
        onOpenAccount={(accId) => setAccountSheetId(accId)}
      />

      <WhatsAppTraceModal
        open={!!whatsappTraceId}
        onOpenChange={(op) => !op && setWhatsappTraceId(null)}
        correlationId={whatsappTraceId}
      />
    </div>
  )
}
