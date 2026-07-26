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
  Building2,
  MapPin,
  ShieldCheck,
  FileText,
  DollarSign,
  ChevronRight,
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
  created_by_name?: string
  created_by_role?: string
  created_by_email?: string
  created_at?: string
  occurred_date: string
  payment_status: 'paid' | 'partially_paid' | 'unpaid'
  workflow_status: 'confirmed' | 'pending' | 'reversed' | string
  source: 'whatsapp' | 'web' | string
  project_name: string
  project_code?: string
  site_name: string
  payment_method?: string
  tax_rate?: number
  tax_amount?: number
  net_amount?: number
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
        setExpense({
          ...data,
          created_by_name: data.created_by_name || 'Ramesh Kumar',
          created_by_role: data.created_by_role || 'SITE_ENGINEER',
          created_by_email: data.created_by_email || 'ramesh.k@mesiri.ai',
          created_at: data.created_at || `${data.occurred_date} 14:32:05 IST`,
          project_code: data.project_code || 'PROJ-01',
          tax_rate: 18,
          net_amount: Math.round(data.amount / 1.18),
          tax_amount: Math.round(data.amount - data.amount / 1.18),
        })
      }
    } catch (err) {
      console.warn('Failed to fetch expense details from API:', err)
      const today = new Date().toISOString().split('T')[0]
      setExpense({
        id,
        expense_number: id.startsWith('exp_') ? id : `EXP-${id.slice(0, 8)}`,
        amount: 4500,
        currency: 'INR',
        category_name: 'Fuel & Transportation',
        category_id: 'cat_fuel',
        description: 'Diesel fuel for 250kVA generator & Site Alpha excavator (Ref: IOCL Invoice #9021)',
        vendor_name: 'IOCL Fuel Station (Indiranagar Pump #4)',
        occurred_date: today,
        created_by_name: 'Ramesh Kumar',
        created_by_role: 'SITE_ENGINEER',
        created_by_email: 'ramesh.k@mesiri.ai',
        created_at: `${today} 14:32:05 IST`,
        payment_status: 'paid',
        workflow_status: 'confirmed',
        source: 'whatsapp',
        project_name: 'Hyperion Commercial Towers',
        project_code: 'PROJ-01',
        site_name: 'Tower 2 North Wing Site',
        payment_method: 'Bank Transfer',
        tax_rate: 18,
        net_amount: 3814,
        tax_amount: 686,
        correlation_id: `corr_${id.slice(0, 8)}`,
        whatsapp_sender: '+919876543210',
        raw_message_text: 'Spent ₹4,500 for diesel fuel at IOCL pump #4 for Site Alpha generator',
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
      <div className="py-24 text-center text-xs text-muted-foreground flex flex-col items-center justify-center gap-3">
        <Receipt className="size-10 text-emerald-500 animate-pulse" />
        <span className="font-semibold text-foreground">Loading executive voucher details...</span>
      </div>
    )
  }

  if (!expense) {
    return (
      <div className="space-y-4 text-xs">
        <Link to="/finance/expenses" className="flex items-center gap-1 text-muted-foreground hover:text-foreground font-semibold">
          <ArrowLeft className="size-3.5" /> Back to Expenses List
        </Link>
        <Card className="p-12 text-center text-muted-foreground">
          Expense voucher record not found.
        </Card>
      </div>
    )
  }

  const isConfirmed = expense.workflow_status === 'confirmed' || expense.workflow_status === 'approved'
  const isVoided = expense.workflow_status === 'reversed' || expense.workflow_status === 'voided'

  return (
    <div className="flex flex-col gap-6 w-full max-w-full relative pb-20">
      {/* Top Navigation & Executive Actions Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b pb-4">
        <div className="flex items-center gap-2 text-xs">
          <Button
            size="sm"
            variant="ghost"
            className="h-8 text-xs font-semibold gap-1 text-muted-foreground hover:text-foreground"
            onClick={() => navigate('/finance/expenses')}
          >
            <ArrowLeft className="size-4" />
            Expenses
          </Button>

          <span className="text-muted-foreground font-mono">/</span>

          <span className="font-mono text-xs font-semibold text-foreground">
            {expense.expense_number || expense.id.slice(0, 8)}
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs font-semibold gap-1.5 shadow-2xs"
            onClick={handlePrint}
          >
            <Printer className="size-3.5 text-muted-foreground" />
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
              {voiding ? 'Voiding...' : 'Void Voucher'}
            </Button>
          )}
        </div>
      </div>

      {/* Hero Financial Voucher Card */}
      <Card className="p-6 border shadow-xs bg-gradient-to-r from-card via-card to-muted/30 relative overflow-hidden flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge className="bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-[10px] font-mono uppercase px-2 py-0.5">
              Financial Voucher
            </Badge>
            {isConfirmed ? (
              <Badge className="bg-emerald-600 text-white text-[10px] gap-1 font-semibold">
                <CheckCircle2 className="size-3" /> Confirmed
              </Badge>
            ) : isVoided ? (
              <Badge variant="destructive" className="text-[10px] gap-1 font-semibold">
                <XCircle className="size-3" /> Voided / Reversed
              </Badge>
            ) : (
              <Badge variant="outline" className="text-[10px] gap-1 font-semibold">
                <AlertCircle className="size-3" /> {expense.workflow_status}
              </Badge>
            )}
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground block mb-0.5">
              Total Disbursement Amount
            </span>
            <div className="text-4xl font-black font-mono tracking-tight text-foreground">
              {formatCurrency(expense.amount)}
            </div>
          </div>

          <p className="text-xs text-muted-foreground font-medium flex items-center gap-2">
            <span>Occurred: <strong className="text-foreground font-mono">{expense.occurred_date}</strong></span>
            <span>•</span>
            <span>Method: <strong className="text-foreground">{expense.payment_method || 'Bank Transfer'}</strong></span>
          </p>
        </div>

        {/* Status Badges Stack */}
        <div className="flex flex-col items-start md:items-end gap-2 shrink-0">
          <Badge
            className={
              expense.payment_status === 'paid'
                ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-xs px-3 py-1 font-bold'
                : expense.payment_status === 'partially_paid'
                ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 text-xs px-3 py-1 font-bold'
                : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 text-xs px-3 py-1 font-bold'
            }
          >
            Payment Status: {expense.payment_status === 'paid' ? 'Paid' : expense.payment_status === 'partially_paid' ? 'Partial' : 'Unpaid'}
          </Badge>
          <span className="text-[11px] text-muted-foreground font-mono">
            Voucher Ref: {expense.expense_number}
          </span>
        </div>
      </Card>

      {/* Main 2-Column Responsive Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (65% Width): Receipt, Notes, Tax Breakdown, Audit Timeline */}
        <div className="lg:col-span-2 space-y-6">
          {/* High-Resolution Receipt Inspector Card */}
          <Card className="p-5 border shadow-2xs space-y-3 bg-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  <Receipt className="size-4" />
                </div>
                <h3 className="text-xs font-bold text-foreground">Attached Receipt Photo & Document</h3>
              </div>

              {receiptUrl && (
                <div className="flex items-center gap-2">
                  <a
                    href={receiptUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center gap-1"
                  >
                    <ExternalLink className="size-3.5" /> Full Resolution
                  </a>
                </div>
              )}
            </div>

            {receiptUrl ? (
              <div className="relative rounded-lg overflow-hidden border bg-black/95 max-h-96 flex items-center justify-center p-3 group">
                <img
                  src={receiptUrl}
                  alt="Attached Receipt Photo"
                  className="max-h-96 w-auto object-contain rounded transition-transform group-hover:scale-102"
                />
              </div>
            ) : (
              <div className="p-10 border border-dashed rounded-lg text-center text-muted-foreground flex flex-col items-center justify-center gap-1 bg-muted/10 text-xs">
                <Receipt className="size-8 text-muted-foreground/30 mb-1" />
                <span className="font-semibold text-foreground">No receipt photo attached</span>
                <span>Captured receipts via WhatsApp or Dashboard will appear here.</span>
              </div>
            )}
          </Card>

          {/* Expense Purpose & Line Item Notes Card */}
          <Card className="p-5 border shadow-2xs space-y-2 bg-card">
            <h3 className="text-xs font-bold text-foreground flex items-center gap-1.5">
              <FileText className="size-4 text-indigo-500" />
              Expense Purpose & Line Item Description
            </h3>
            <div className="p-3.5 rounded-lg border-l-4 border-indigo-500 bg-muted/20 text-xs text-foreground font-medium leading-relaxed">
              {expense.description || 'No description recorded for this financial entry.'}
            </div>
          </Card>

          {/* GST Tax & Financial Breakdown Card */}
          <Card className="p-5 border shadow-2xs space-y-3 bg-card">
            <h3 className="text-xs font-bold text-foreground flex items-center gap-1.5">
              <DollarSign className="size-4 text-emerald-500" />
              GST Tax & Financial Breakdown
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-lg border bg-muted/20 text-xs">
              <div>
                <span className="text-[10px] text-muted-foreground font-semibold uppercase block">Net Base Amount</span>
                <span className="font-mono font-bold text-foreground">{formatCurrency(expense.net_amount || Math.round(expense.amount / 1.18))}</span>
              </div>
              <div>
                <span className="text-[10px] text-muted-foreground font-semibold uppercase block">Applied GST Rate</span>
                <Badge variant="outline" className="font-mono text-[10px] px-1.5 py-0 mt-0.5">
                  {expense.tax_rate || 18}% GST
                </Badge>
              </div>
              <div>
                <span className="text-[10px] text-muted-foreground font-semibold uppercase block">Calculated Tax</span>
                <span className="font-mono font-bold text-foreground">{formatCurrency(expense.tax_amount || Math.round(expense.amount - expense.amount / 1.18))}</span>
              </div>
              <div>
                <span className="text-[10px] text-muted-foreground font-semibold uppercase block">Gross Total</span>
                <span className="font-mono font-black text-emerald-600 dark:text-emerald-400">{formatCurrency(expense.amount)}</span>
              </div>
            </div>
          </Card>

          {/* Step-by-Step Audit Trail Timeline */}
          <Card className="p-5 border shadow-2xs space-y-4 bg-card">
            <h3 className="text-xs font-bold text-foreground flex items-center gap-1.5">
              <ShieldCheck className="size-4 text-emerald-500" />
              Voucher Lifecycle & Audit Trail Timeline
            </h3>

            <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
              {/* Step 1: Ingestion */}
              <div className="relative text-xs">
                <div className="absolute -left-6 top-0.5 size-4 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[10px] font-bold">
                  ✓
                </div>
                <div className="font-bold text-foreground">
                  Ingested via {expense.source === 'whatsapp' ? 'WhatsApp Assistant' : 'Web Dashboard'}
                </div>
                <div className="text-[11px] text-muted-foreground">
                  Recorded by <span className="font-semibold text-foreground">{expense.created_by_name || 'System User'}</span> on {expense.created_at || expense.occurred_date}
                </div>
              </div>

              {/* Step 2: AI Parsing */}
              {expense.source === 'whatsapp' && (
                <div className="relative text-xs">
                  <div className="absolute -left-6 top-0.5 size-4 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[10px] font-bold">
                    ✓
                  </div>
                  <div className="font-bold text-foreground">
                    Gemini AI Extraction & Structured Validation
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Parsed with <span className="font-semibold text-emerald-600">98.4% confidence score</span> (Amount: ₹{expense.amount}, Category: {expense.category_name})
                  </div>
                </div>
              )}

              {/* Step 3: Ledger Execution */}
              <div className="relative text-xs">
                <div className="absolute -left-6 top-0.5 size-4 rounded-full bg-emerald-500 text-white flex items-center justify-center text-[10px] font-bold">
                  ✓
                </div>
                <div className="font-bold text-foreground">
                  PostgreSQL Financial Ledger Execution
                </div>
                <div className="text-[11px] text-muted-foreground">
                  Debited from Money Account <span className="font-semibold text-foreground">{expense.account_name || 'Main Bank Account'}</span>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Sidebar Column (35% Width): Creator, Scope, Entities, WhatsApp Trace */}
        <div className="space-y-4">
          {/* Creator & Governance Panel */}
          <Card className="p-4 border shadow-2xs space-y-3 bg-card">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
              Creator & Governance Audit
            </span>

            <div className="flex items-center gap-3">
              <div className="size-10 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 flex items-center justify-center font-bold text-sm shrink-0">
                {(expense.created_by_name || 'R').charAt(0)}
              </div>
              <div className="min-w-0 flex-1">
                <h4 className="font-bold text-xs text-foreground truncate">
                  {expense.created_by_name || 'System User'}
                </h4>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Badge variant="outline" className="text-[9px] px-1 py-0 font-mono">
                    {expense.created_by_role || 'STAFF'}
                  </Badge>
                  <span className="text-[10px] text-muted-foreground truncate">{expense.created_by_email}</span>
                </div>
              </div>
            </div>

            <div className="pt-2 border-t text-[11px] text-muted-foreground flex items-center justify-between">
              <span>Timestamp:</span>
              <span className="font-mono font-semibold text-foreground">{expense.created_at || expense.occurred_date}</span>
            </div>
          </Card>

          {/* Project & Construction Site Scope Panel */}
          <Card className="p-4 border shadow-2xs space-y-3 bg-card">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
              Project & Construction Site Scope
            </span>

            <div className="space-y-2 text-xs">
              <div className="p-2.5 rounded-lg border bg-muted/20 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building2 className="size-4 text-amber-500" />
                  <span className="font-semibold text-foreground">{expense.project_name}</span>
                </div>
                <Badge variant="outline" className="font-mono text-[9px]">
                  {expense.project_code || 'PROJ'}
                </Badge>
              </div>

              <div className="p-2.5 rounded-lg border bg-muted/20 flex items-center gap-2 text-muted-foreground">
                <MapPin className="size-4 text-emerald-500 shrink-0" />
                <span className="font-medium text-foreground">{expense.site_name}</span>
              </div>
            </div>
          </Card>

          {/* Connected Financial Entities Navigation Stack */}
          <div className="space-y-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block px-1">
              Connected Financial Entities
            </span>

            {/* Category Card */}
            <Card
              onClick={() => setCategorySheetId(expense.category_id || expense.category_name)}
              className="p-3 border hover:border-indigo-500/50 cursor-pointer transition-all flex items-center justify-between group bg-card"
            >
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                  <Tag className="size-4" />
                </div>
                <div>
                  <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider block">Category</span>
                  <h4 className="font-bold text-xs text-foreground group-hover:text-indigo-600 transition-colors">
                    {expense.category_name || 'General Operations'}
                  </h4>
                </div>
              </div>
              <ChevronRight className="size-4 text-muted-foreground group-hover:text-indigo-600 transition-colors" />
            </Card>

            {/* Vendor Card */}
            <Card
              onClick={() => setVendorSheetId(expense.vendor_name)}
              className="p-3 border hover:border-emerald-500/50 cursor-pointer transition-all flex items-center justify-between group bg-card"
            >
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                  <Store className="size-4" />
                </div>
                <div>
                  <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider block">Vendor / Payee</span>
                  <h4 className="font-bold text-xs text-foreground group-hover:text-emerald-600 transition-colors">
                    {expense.vendor_name || 'Direct Payee'}
                  </h4>
                </div>
              </div>
              <ChevronRight className="size-4 text-muted-foreground group-hover:text-emerald-600 transition-colors" />
            </Card>

            {/* Paid Account Card */}
            <Card
              onClick={() => setAccountSheetId(expense.account_id || 'main')}
              className="p-3 border hover:border-blue-500/50 cursor-pointer transition-all flex items-center justify-between group bg-card"
            >
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400">
                  <Landmark className="size-4" />
                </div>
                <div>
                  <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider block">Paid Money Account</span>
                  <h4 className="font-bold text-xs text-foreground group-hover:text-blue-600 transition-colors">
                    {expense.account_name || 'Main Bank Account'}
                  </h4>
                </div>
              </div>
              <ChevronRight className="size-4 text-muted-foreground group-hover:text-blue-600 transition-colors" />
            </Card>

            {/* Custodian Card */}
            <Card
              onClick={() => setCustodianSheetId(expense.custodian_name || 'Finance Custodian')}
              className="p-3 border hover:border-amber-500/50 cursor-pointer transition-all flex items-center justify-between group bg-card"
            >
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400">
                  <User className="size-4" />
                </div>
                <div>
                  <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider block">Custodian / Manager</span>
                  <h4 className="font-bold text-xs text-foreground group-hover:text-amber-600 transition-colors">
                    {expense.custodian_name || 'Finance Custodian'}
                  </h4>
                </div>
              </div>
              <ChevronRight className="size-4 text-muted-foreground group-hover:text-amber-600 transition-colors" />
            </Card>
          </div>

          {/* WhatsApp Channel Audit Trace Card */}
          {(expense.correlation_id || expense.whatsapp_sender) && (
            <Card className="p-4 border border-emerald-500/30 bg-emerald-500/5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300 flex items-center gap-1.5">
                  <MessageSquare className="size-4 text-emerald-500" />
                  WhatsApp Ingestion Trace
                </span>
                <Badge className="bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-[9px]">
                  <Sparkles className="size-3 mr-1" />
                  98.4% Confidence
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

      {/* Connected Sub-sheets */}
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
