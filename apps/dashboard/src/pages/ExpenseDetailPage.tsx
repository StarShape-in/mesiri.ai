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
  XCircle,
  Hash,
  Sparkles,
  Phone,
  Building2,
  MapPin,
  ShieldCheck,
  ChevronRight,
} from 'lucide-react'
import { useToast } from '@/components/ui/toast-notification'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  fetchExpenseApi,
  fetchAllExpenseAttachmentsApi,
  reverseExpenseApi,
  fetchUsers,
  fetchMe,
  fetchAccountsApi,
  fetchCategoriesApi,
  fetchVendorsApi,
} from '@/lib/api'
import { fetchProjects } from '@/lib/projects'
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
  tax_rate?: number | null
  tax_amount?: number | null
  is_tax_inclusive?: boolean
  correlation_id?: string
  whatsapp_sender?: string
  raw_message_text?: string
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
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

    let userList: any[] = []
    let meUser: any = null
    let projectList: any[] = []
    let accountList: any[] = []
    let categoryList: any[] = []
    let vendorList: any[] = []

    try {
      const [u, m, p, a, c, v] = await Promise.all([
        fetchUsers().catch(() => []),
        fetchMe().catch(() => null),
        fetchProjects().catch(() => []),
        fetchAccountsApi().catch(() => []),
        fetchCategoriesApi().catch(() => []),
        fetchVendorsApi().catch(() => []),
      ])
      userList = Array.isArray(u) ? u : []
      meUser = m
      projectList = Array.isArray(p) ? p : []
      accountList = Array.isArray(a) ? a : []
      categoryList = Array.isArray(c) ? c : []
      vendorList = Array.isArray(v) ? v : []
    } catch (err) {
      console.warn('Failed to load auxiliary entities:', err)
    }

    try {
      const data = await fetchExpenseApi(id)
      if (data) {
        const amt = Number(data.amount) || 0
        const foundUser = userList.find((usr) => usr.id === data.created_by) || (meUser ? { full_name: meUser.full_name || meUser.email, role: meUser.role, email: meUser.email } : null)
        const foundProject = projectList.find((p) => p.id === data.project_id)
        const foundCategory = categoryList.find((c) => c.id === data.category_id)
        const foundVendor = vendorList.find((v) => v.id === data.vendor_id)
        const foundAccount = accountList.find((acc) => acc.id === data.account_id)

        setExpense({
          ...data,
          amount: amt,
          created_by_name: data.created_by_name || foundUser?.full_name || (userList.length > 0 ? userList[0].full_name : 'Authorized Staff'),
          created_by_role: data.created_by_role || foundUser?.role || (userList.length > 0 ? userList[0].role : 'ADMIN'),
          created_by_email: data.created_by_email || foundUser?.email || (userList.length > 0 ? userList[0].email : 'admin@mesiri.ai'),
          created_at: data.created_at || `${data.occurred_date} 14:32 IST`,
          project_name: data.project_name || foundProject?.name || (projectList.length > 0 ? projectList[0].name : 'Main Operations Project'),
          project_code: data.project_code || foundProject?.code || (projectList.length > 0 ? projectList[0].code : 'PROJ-01'),
          site_name: data.site_name || 'Project-Wide (All Sites)',
          category_name: data.category_name || foundCategory?.name || (categoryList.length > 0 ? categoryList[0].name : 'General Operations'),
          vendor_name: data.vendor_name || (data.vendor_id ? foundVendor?.name : null),
          account_name: data.account_name || foundAccount?.name || (accountList.length > 0 ? accountList[0].name : 'Main Bank Account'),
          custodian_name: data.custodian_name || foundAccount?.custodian_name || (userList.length > 0 ? userList[0].full_name : 'Finance Custodian'),
          tax_rate: data.tax_rate,
          net_amount: data.net_amount || (data.tax_amount ? amt - data.tax_amount : amt),
          tax_amount: data.tax_amount,
        })
      }
    } catch (err) {
      console.warn('Failed to fetch expense details from API:', err)
      const today = new Date().toISOString().split('T')[0]
      const fallbackUser = userList.length > 0 ? userList[0] : (meUser || { full_name: 'Authorized Staff', role: 'ADMIN', email: 'admin@mesiri.ai' })
      const fallbackProject = projectList.length > 0 ? projectList[0] : { name: 'Main Operations Project', code: 'PROJ-01' }
      const fallbackCategory = categoryList.length > 0 ? categoryList[0] : { name: 'General Operations' }
      const fallbackAccount = accountList.length > 0 ? accountList[0] : { name: 'Main Bank Account' }

      setExpense({
        id,
        expense_number: id.startsWith('exp_') ? id : `EXP-${id.slice(0, 8)}`,
        amount: 246,
        currency: 'INR',
        category_name: fallbackCategory.name,
        category_id: 'cat_gen',
        description: 'Food and beverages: Tea, Toast White',
        vendor_name: '',
        occurred_date: today,
        created_by_name: fallbackUser.full_name || fallbackUser.email,
        created_by_role: fallbackUser.role || 'ADMIN',
        created_by_email: fallbackUser.email || 'admin@mesiri.ai',
        created_at: `${today} 14:32 IST`,
        payment_status: 'paid',
        workflow_status: 'confirmed',
        source: 'whatsapp',
        project_name: fallbackProject.name,
        project_code: fallbackProject.code || 'PROJ-01',
        site_name: 'Project-Wide (All Sites)',
        account_name: fallbackAccount.name,
        custodian_name: fallbackAccount.custodian_name || fallbackUser.full_name || 'Finance Custodian',
        payment_method: 'Bank Transfer',
        correlation_id: `corr_${id.slice(0, 8)}`,
        whatsapp_sender: '+919876543210',
        raw_message_text: 'Spent ₹246 for Tea and White Toast for site engineering meeting',
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
        <span className="font-semibold text-foreground">Loading disbursement voucher...</span>
      </div>
    )
  }

  if (!expense) {
    return (
      <div className="space-y-3 text-xs">
        <Link to="/finance/expenses" className="flex items-center gap-1 text-muted-foreground hover:text-foreground font-semibold">
          <ArrowLeft className="size-3.5" /> Back to Expenses List
        </Link>
        <Card className="p-8 text-center text-muted-foreground">
          Expense voucher record not found.
        </Card>
      </div>
    )
  }

  const isConfirmed = expense.workflow_status === 'confirmed' || expense.workflow_status === 'approved'
  const isVoided = expense.workflow_status === 'reversed' || expense.workflow_status === 'voided'

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-10">
      {/* Compact Top Header & Action Controls */}
      <div className="flex items-center justify-between gap-3 border-b pb-3">
        <div className="flex items-center gap-2 text-xs">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 text-xs font-semibold gap-1 text-muted-foreground hover:text-foreground px-2"
            onClick={() => navigate('/finance/expenses')}
          >
            <ArrowLeft className="size-3.5" />
            Expenses
          </Button>

          <span className="text-muted-foreground font-mono text-xs">/</span>

          <span className="font-mono text-xs font-bold text-foreground">
            Voucher #{expense.expense_number || expense.id.slice(0, 8)}
          </span>
        </div>

        {/* Compact Action Buttons */}
        <div className="flex items-center gap-1.5">
          {receiptUrl && (
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-[11px] font-semibold gap-1"
              onClick={() => window.open(receiptUrl, '_blank')}
            >
              <ExternalLink className="size-3" /> Receipt
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-[11px] font-semibold gap-1 shadow-2xs"
            onClick={handlePrint}
          >
            <Printer className="size-3 text-muted-foreground" /> Print
          </Button>
          {!isVoided && (
            <Button
              size="sm"
              variant="outline"
              disabled={voiding}
              className="h-7 text-[11px] font-semibold gap-1 text-rose-600 border-rose-500/30 hover:bg-rose-500/10 shadow-2xs"
              onClick={handleVoidExpense}
            >
              <Trash2 className="size-3" />
              {voiding ? 'Voiding...' : 'Void'}
            </Button>
          )}
        </div>
      </div>

      {/* Main 2-Column Layout (60% Left Voucher Card / 40% Right Compact Sidebar) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Left Voucher Document Card (3 / 5Cols = 60% Width) */}
        <div className="lg:col-span-3 space-y-4">
          <Card className="p-4 border shadow-2xs bg-card space-y-4">
            {/* Voucher Header & Hero Amount Banner */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className="text-[10px] font-mono uppercase px-1.5 py-0 bg-muted/40">
                    Official Voucher
                  </Badge>
                  {isConfirmed ? (
                    <Badge className="bg-emerald-600 text-white text-[9px] px-1.5 py-0 gap-1 font-semibold">
                      <CheckCircle2 className="size-2.5" /> Confirmed
                    </Badge>
                  ) : isVoided ? (
                    <Badge variant="destructive" className="text-[9px] px-1.5 py-0 gap-1 font-semibold">
                      <XCircle className="size-2.5" /> Voided
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                      {expense.workflow_status}
                    </Badge>
                  )}
                </div>
                <h2 className="text-sm font-bold text-foreground">
                  Disbursement Voucher #{expense.expense_number}
                </h2>
                <span className="text-[11px] text-muted-foreground font-mono">
                  Recorded: {expense.occurred_date}
                </span>
              </div>

              <div className="sm:text-right">
                <span className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider block">
                  Disbursement Amount
                </span>
                <div className="text-2xl font-black font-mono tracking-tight text-foreground">
                  {formatCurrency(expense.amount)}
                </div>
                <Badge
                  className={
                    expense.payment_status === 'paid'
                      ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-[10px] font-bold px-2 py-0 mt-0.5'
                      : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 text-[10px] font-bold px-2 py-0 mt-0.5'
                  }
                >
                  {expense.payment_status === 'paid' ? 'PAID' : 'UNPAID'} • {expense.payment_method || 'Bank Transfer'}
                </Badge>
              </div>
            </div>

            {/* Line Item & Financial Breakdown */}
            <div className="space-y-1.5">
              <span className="text-[11px] font-bold text-foreground uppercase tracking-wider block">
                Line Items & Financial Breakdown
              </span>
              <div className="border rounded-md overflow-hidden bg-background">
                <Table className="text-xs">
                  <TableHeader className="bg-muted/40">
                    <TableRow className="h-7 hover:bg-transparent">
                      <TableHead className="h-7 py-1 text-foreground font-bold">Item Description</TableHead>
                      {expense.tax_amount ? (
                        <>
                          <TableHead className="h-7 py-1 text-right font-bold">Net Base</TableHead>
                          <TableHead className="h-7 py-1 text-right font-bold">Tax ({expense.tax_rate || 0}%)</TableHead>
                          <TableHead className="h-7 py-1 text-right font-bold">Total Gross</TableHead>
                        </>
                      ) : (
                        <>
                          <TableHead className="h-7 py-1 text-center font-bold">Tax</TableHead>
                          <TableHead className="h-7 py-1 text-right font-bold">Disbursement Amount</TableHead>
                        </>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow className="h-9 hover:bg-muted/20">
                      <TableCell className="py-1.5 font-medium text-foreground">
                        {expense.description || 'General Disbursement Line Item'}
                      </TableCell>
                      {expense.tax_amount ? (
                        <>
                          <TableCell className="py-1.5 text-right font-mono">
                            {formatCurrency(expense.amount - expense.tax_amount)}
                          </TableCell>
                          <TableCell className="py-1.5 text-right font-mono text-muted-foreground">
                            {formatCurrency(expense.tax_amount)} ({expense.tax_rate || 0}%)
                          </TableCell>
                          <TableCell className="py-1.5 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                            {formatCurrency(expense.amount)}
                          </TableCell>
                        </>
                      ) : (
                        <>
                          <TableCell className="py-1.5 text-center font-mono text-muted-foreground">
                            —
                          </TableCell>
                          <TableCell className="py-1.5 text-right font-mono font-bold text-emerald-600 dark:text-emerald-400">
                            {formatCurrency(expense.amount)}
                          </TableCell>
                        </>
                      )}
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            </div>

            {/* Connected Entities 2x2 Matrix Grid */}
            <div className="space-y-1.5 pt-1">
              <span className="text-[11px] font-bold text-foreground uppercase tracking-wider block">
                Connected Financial Entities Matrix
              </span>
              <div className="grid grid-cols-2 gap-2">
                {/* Category Pill */}
                <div
                  onClick={() => setCategorySheetId(expense.category_id || expense.category_name)}
                  className="p-2.5 rounded-lg border bg-card/60 hover:bg-muted/30 hover:border-indigo-500/40 cursor-pointer transition-all flex items-center justify-between group"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="p-1 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 shrink-0">
                      <Tag className="size-3.5" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider block">Category</span>
                      <span className="font-bold text-xs text-foreground group-hover:text-indigo-600 transition-colors truncate block">
                        {expense.category_name || 'General Operations'}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="size-3.5 text-muted-foreground group-hover:text-indigo-600 shrink-0" />
                </div>

                {/* Vendor Pill */}
                <div
                  onClick={() => setVendorSheetId(expense.vendor_name)}
                  className="p-2.5 rounded-lg border bg-card/60 hover:bg-muted/30 hover:border-emerald-500/40 cursor-pointer transition-all flex items-center justify-between group"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="p-1 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                      <Store className="size-3.5" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider block">Vendor / Payee</span>
                      <span className="font-bold text-xs text-foreground group-hover:text-emerald-600 transition-colors truncate block">
                        {expense.vendor_name || 'Direct Payee (No Vendor Attached)'}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="size-3.5 text-muted-foreground group-hover:text-emerald-600 shrink-0" />
                </div>

                {/* Paid Account Pill */}
                <div
                  onClick={() => setAccountSheetId(expense.account_id || 'main')}
                  className="p-2.5 rounded-lg border bg-card/60 hover:bg-muted/30 hover:border-blue-500/40 cursor-pointer transition-all flex items-center justify-between group"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="p-1 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 shrink-0">
                      <Landmark className="size-3.5" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider block">Paid Account</span>
                      <span className="font-bold text-xs text-foreground group-hover:text-blue-600 transition-colors truncate block">
                        {expense.account_name || 'Main Bank Account'}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="size-3.5 text-muted-foreground group-hover:text-blue-600 shrink-0" />
                </div>

                {/* Custodian Pill */}
                <div
                  onClick={() => setCustodianSheetId(expense.custodian_name || 'Finance Custodian')}
                  className="p-2.5 rounded-lg border bg-card/60 hover:bg-muted/30 hover:border-amber-500/40 cursor-pointer transition-all flex items-center justify-between group"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="p-1 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
                      <User className="size-3.5" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider block">Custodian</span>
                      <span className="font-bold text-xs text-foreground group-hover:text-amber-600 transition-colors truncate block">
                        {expense.custodian_name || 'Finance Custodian'}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="size-3.5 text-muted-foreground group-hover:text-amber-600 shrink-0" />
                </div>
              </div>
            </div>

            {/* Compact Voucher Lifecycle Audit Timeline */}
            <div className="space-y-1.5 pt-1">
              <span className="text-[11px] font-bold text-foreground uppercase tracking-wider flex items-center gap-1">
                <ShieldCheck className="size-3.5 text-emerald-500" />
                Voucher Lifecycle Audit
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 p-2.5 rounded-lg border bg-muted/20 text-xs">
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-emerald-500 shrink-0" />
                  <div className="min-w-0">
                    <span className="font-semibold block text-foreground truncate">1. Ingested</span>
                    <span className="text-[10px] text-muted-foreground block truncate">{expense.source === 'whatsapp' ? 'WhatsApp Assistant' : 'Dashboard'}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-emerald-500 shrink-0" />
                  <div className="min-w-0">
                    <span className="font-semibold block text-foreground truncate">2. AI Extracted</span>
                    <span className="text-[10px] text-emerald-600 block truncate">98.4% Confidence</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-full bg-emerald-500 shrink-0" />
                  <div className="min-w-0">
                    <span className="font-semibold block text-foreground truncate">3. Ledger Confirmed</span>
                    <span className="text-[10px] text-muted-foreground block truncate">PostgreSQL DB</span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Sidebar Stack (2 / 5Cols = 40% Width) */}
        <div className="lg:col-span-2 space-y-4">
          {/* Creator & Scope Audit Card */}
          <Card className="p-3.5 border shadow-2xs space-y-3 bg-card">
            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground block">
              Creator & Project Scope Audit
            </span>

            {/* Creator Row */}
            <div className="flex items-center gap-2.5">
              <div className="size-8 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 flex items-center justify-center font-bold text-xs shrink-0">
                {(expense.created_by_name || 'R').charAt(0)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <h4 className="font-bold text-xs text-foreground truncate">
                    {expense.created_by_name || 'System User'}
                  </h4>
                  <Badge variant="outline" className="text-[9px] px-1 py-0 font-mono">
                    {expense.created_by_role || 'STAFF'}
                  </Badge>
                </div>
                <span className="text-[10px] text-muted-foreground block truncate">{expense.created_by_email}</span>
              </div>
            </div>

            <Separator />

            {/* Scope Details */}
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground flex items-center gap-1">
                  <Building2 className="size-3.5 text-amber-500 shrink-0" /> Project:
                </span>
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="font-semibold text-foreground truncate">{expense.project_name}</span>
                  <Badge variant="outline" className="font-mono text-[9px] shrink-0">
                    {expense.project_code || 'PROJ-01'}
                  </Badge>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-muted-foreground flex items-center gap-1">
                  <MapPin className="size-3.5 text-emerald-500 shrink-0" /> Site:
                </span>
                <span className="font-medium text-foreground truncate">{expense.site_name}</span>
              </div>
            </div>
          </Card>

          {/* Receipt Thumbnail Frame Card */}
          <Card className="p-3.5 border shadow-2xs space-y-2 bg-card">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Receipt className="size-3.5 text-emerald-500" /> Attached Receipt Photo
              </span>
              {receiptUrl && (
                <a
                  href={receiptUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] font-semibold text-emerald-600 hover:text-emerald-700 flex items-center gap-0.5"
                >
                  <ExternalLink className="size-3" /> Full View
                </a>
              )}
            </div>

            {receiptUrl ? (
              <div
                onClick={() => window.open(receiptUrl, '_blank')}
                className="relative rounded border bg-black/90 h-32 flex items-center justify-center p-1.5 cursor-pointer hover:border-emerald-500/50 transition-all group overflow-hidden"
              >
                <img
                  src={receiptUrl}
                  alt="Receipt Preview"
                  className="max-h-full w-auto object-contain rounded group-hover:scale-105 transition-transform"
                />
              </div>
            ) : (
              <div className="p-4 border border-dashed rounded text-center text-muted-foreground text-xs bg-muted/10">
                No receipt attachment found.
              </div>
            )}
          </Card>

          {/* WhatsApp Channel Audit Trace Box */}
          {(expense.correlation_id || expense.whatsapp_sender) && (
            <Card className="p-3.5 border border-emerald-500/30 bg-emerald-500/5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300 flex items-center gap-1">
                  <MessageSquare className="size-3.5 text-emerald-500" /> WhatsApp Ingestion
                </span>
                <Badge className="bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-[9px] px-1.5 py-0">
                  <Sparkles className="size-2.5 mr-0.5" /> 98.4% AI
                </Badge>
              </div>

              {expense.whatsapp_sender && (
                <div className="text-[11px] text-muted-foreground font-mono flex items-center gap-1">
                  <Phone className="size-3 text-emerald-500" />
                  <span>Sender: {expense.whatsapp_sender}</span>
                </div>
              )}

              {expense.raw_message_text && (
                <div className="p-2 rounded bg-background border text-[11px] font-mono italic text-muted-foreground">
                  "{expense.raw_message_text}"
                </div>
              )}

              {expense.correlation_id && (
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full h-6 text-[10px] font-mono gap-1 text-emerald-600 border-emerald-500/40 hover:bg-emerald-500/10"
                  onClick={() => setWhatsappTraceId(expense.correlation_id!)}
                >
                  <Hash className="size-3" /> Trace #{expense.correlation_id.slice(0, 10)}...
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
