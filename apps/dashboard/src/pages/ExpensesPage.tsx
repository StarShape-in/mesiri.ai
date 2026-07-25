import * as React from 'react'
import {
  DollarSign,
  Plus,
  Search,
  Download,
  CheckCircle2,
  AlertCircle,
  MessageSquare,
  Laptop,
  MoreVertical,
  Eye,
  Receipt,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RecordExpenseDialog } from '@/components/expenses/record-expense-dialog'
import { ExpenseDetailSheet } from '@/components/expenses/expense-detail-sheet'

interface ExpenseItem {
  id: string
  expense_number: string
  amount: number
  currency: string
  category_name: string
  category_id: string
  description: string
  vendor_name: string
  occurred_date: string
  payment_status: 'paid' | 'partially_paid' | 'unpaid'
  workflow_status: 'confirmed' | 'pending' | 'reversed'
  source: 'whatsapp' | 'web'
  project_name: string
  site_name: string
  payment_method?: string
}

const INITIAL_EXPENSES: ExpenseItem[] = [
  {
    id: 'exp_01',
    expense_number: 'EXP-1048',
    amount: 45000,
    currency: 'INR',
    category_name: 'Fuel & Transportation',
    category_id: 'fuel',
    description: 'Diesel for Site Excavator JCB-3DX',
    vendor_name: 'Indian Oil Bunk #4',
    occurred_date: '2026-07-24',
    payment_status: 'paid',
    workflow_status: 'confirmed',
    source: 'whatsapp',
    project_name: 'Riverside Commercial Center',
    site_name: 'Tower A Excavation',
    payment_method: 'bank_transfer',
  },
  {
    id: 'exp_02',
    expense_number: 'EXP-1049',
    amount: 125000,
    currency: 'INR',
    category_name: 'Equipment & Machinery',
    category_id: 'equipment',
    description: 'Concrete Pump Hire (2 Days)',
    vendor_name: 'UltraTech Rental Services',
    occurred_date: '2026-07-23',
    payment_status: 'unpaid',
    workflow_status: 'confirmed',
    source: 'web',
    project_name: 'Riverside Commercial Center',
    site_name: 'Basement Slab',
    payment_method: undefined,
  },
  {
    id: 'exp_03',
    expense_number: 'EXP-1050',
    amount: 32000,
    currency: 'INR',
    category_name: 'Labor & Daily Wages',
    category_id: 'labor',
    description: 'Overtime Wages for Steel Fixers',
    vendor_name: 'Sub-contractor Skilled Crew',
    occurred_date: '2026-07-22',
    payment_status: 'paid',
    workflow_status: 'confirmed',
    source: 'whatsapp',
    project_name: 'Green Valley Housing',
    site_name: 'Phase 1 Structural',
    payment_method: 'petty_cash',
  },
  {
    id: 'exp_04',
    expense_number: 'EXP-1051',
    amount: 85000,
    currency: 'INR',
    category_name: 'Raw Materials & Supplies',
    category_id: 'materials',
    description: 'Scaffolding Clamps & Safety Nets',
    vendor_name: 'Apex Construction Hardware',
    occurred_date: '2026-07-21',
    payment_status: 'partially_paid',
    workflow_status: 'confirmed',
    source: 'web',
    project_name: 'Riverside Commercial Center',
    site_name: 'Tower A Structural',
    payment_method: 'upi',
  },
  {
    id: 'exp_05',
    expense_number: 'EXP-1052',
    amount: 18500,
    currency: 'INR',
    category_name: 'Site Maintenance & Repairs',
    category_id: 'maintenance',
    description: 'Temporary Site Power Distribution Repair',
    vendor_name: 'City Electric Works',
    occurred_date: '2026-07-20',
    payment_status: 'paid',
    workflow_status: 'confirmed',
    source: 'whatsapp',
    project_name: 'Green Valley Housing',
    site_name: 'Site Infrastructure',
    payment_method: 'cash',
  },
]

export default function ExpensesPage() {
  const { scope } = useScope()

  const [expenses, setExpenses] = React.useState<ExpenseItem[]>(INITIAL_EXPENSES)
  const [search, setSearch] = React.useState('')
  const [categoryFilter, setCategoryFilter] = React.useState('ALL')
  const [paymentStatusFilter, setPaymentStatusFilter] = React.useState('ALL')
  const [sourceFilter, setSourceFilter] = React.useState('ALL')

  // Dialog & Sheet state
  const [recordDialogOpen, setRecordDialogOpen] = React.useState(false)
  const [selectedExpense, setSelectedExpense] = React.useState<ExpenseItem | null>(null)
  const [sheetOpen, setSheetOpen] = React.useState(false)

  const handleExpenseCreated = (newExpense: ExpenseItem) => {
    setExpenses((prev) => [newExpense, ...prev])
  }

  // Filtered expenses
  const filteredExpenses = React.useMemo(() => {
    return expenses.filter((item) => {
      const matchesSearch =
        item.expense_number.toLowerCase().includes(search.toLowerCase()) ||
        item.description.toLowerCase().includes(search.toLowerCase()) ||
        item.vendor_name.toLowerCase().includes(search.toLowerCase()) ||
        item.category_name.toLowerCase().includes(search.toLowerCase())

      if (!matchesSearch) return false

      if (categoryFilter !== 'ALL' && item.category_id !== categoryFilter) return false
      if (paymentStatusFilter !== 'ALL' && item.payment_status !== paymentStatusFilter) return false
      if (sourceFilter !== 'ALL' && item.source !== sourceFilter) return false

      return true
    })
  }, [expenses, search, categoryFilter, paymentStatusFilter, sourceFilter])

  // Summary Metrics calculation
  const metrics = React.useMemo(() => {
    const totalSpent = expenses.reduce((acc, curr) => acc + curr.amount, 0)
    const unpaidAmount = expenses
      .filter((e) => e.payment_status === 'unpaid')
      .reduce((acc, curr) => acc + curr.amount, 0)
    const paidAmount = expenses
      .filter((e) => e.payment_status === 'paid')
      .reduce((acc, curr) => acc + curr.amount, 0)
    const whatsappCount = expenses.filter((e) => e.source === 'whatsapp').length
    const webCount = expenses.filter((e) => e.source === 'web').length

    return {
      totalSpent,
      unpaidAmount,
      paidAmount,
      count: expenses.length,
      whatsappCount,
      webCount,
    }
  }, [expenses])

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Projects)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(val)
  }

  return (
    <div className="flex flex-col gap-4 w-full max-w-full">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b pb-3.5">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0 shadow-2xs">
            <DollarSign className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Expense Management
              <Badge variant="outline" className="text-[10px] font-mono border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
                Finance Module
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-8 gap-1.5 text-xs font-medium"
            onClick={() => alert('Exporting Expense Report as CSV...')}
          >
            <Download className="size-3.5" />
            Export CSV
          </Button>
          <Button
            size="sm"
            className="h-8 gap-1.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-2xs"
            onClick={() => setRecordDialogOpen(true)}
          >
            <Plus className="size-4" />
            Record Expense
          </Button>
        </div>
      </div>

      {/* KPI Cards Grid using standard Project KpiCard */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Total Expenses"
          value={<span className="text-emerald-600 dark:text-emerald-400">{formatCurrency(metrics.totalSpent)}</span>}
          trend="up"
          trendValue="+12.4% MoM"
          description="Total recorded spend"
          icon={<Receipt className="text-emerald-500" />}
          chartData={[12, 18, 15, 22, 30, 28, 35, 42]}
        />
        <KpiCard
          title="Unpaid Balance"
          value={<span className="text-rose-600 dark:text-rose-400">{formatCurrency(metrics.unpaidAmount)}</span>}
          trend="down"
          trendValue="Action Needed"
          description="Outstanding invoices"
          icon={<AlertCircle className="text-rose-500" />}
          chartData={[8, 14, 10, 18, 12, 20, 15, 12]}
        />
        <KpiCard
          title="Settled Amount"
          value={<span className="text-blue-600 dark:text-blue-400">{formatCurrency(metrics.paidAmount)}</span>}
          trend="up"
          trendValue="85.8% Settled"
          description="Paid disbursements"
          icon={<CheckCircle2 className="text-blue-500" />}
          chartData={[10, 15, 20, 25, 30, 38, 45]}
        />
        <KpiCard
          title="Channel Ingestion"
          value={<span className="text-foreground">{metrics.count} Entries</span>}
          trend="neutral"
          trendValue={`WA: ${metrics.whatsappCount} | Web: ${metrics.webCount}`}
          description="WhatsApp & Web logs"
          icon={<MessageSquare className="text-indigo-500" />}
        />
      </div>

      {/* Filter & Toolbar */}
      <div className="flex flex-col sm:flex-row gap-2.5 items-center justify-between border border-border/80 p-2.5 rounded-lg bg-card/40">
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto flex-1 items-center">
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search expenses, vendors, number..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>

          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-44">
              <SelectValue placeholder="All Categories" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Categories</SelectItem>
              <SelectItem value="fuel">Fuel & Transportation</SelectItem>
              <SelectItem value="equipment">Equipment & Hire</SelectItem>
              <SelectItem value="labor">Labor & Wages</SelectItem>
              <SelectItem value="materials">Raw Materials</SelectItem>
              <SelectItem value="maintenance">Maintenance</SelectItem>
            </SelectContent>
          </Select>

          <Select value={sourceFilter} onValueChange={setSourceFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-36">
              <SelectValue placeholder="All Sources" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Sources</SelectItem>
              <SelectItem value="whatsapp">WhatsApp</SelectItem>
              <SelectItem value="web">Web Dashboard</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Payment Status Tab Filter */}
        <Tabs value={paymentStatusFilter} onValueChange={setPaymentStatusFilter} className="w-full sm:w-auto">
          <TabsList className="h-9 text-xs grid grid-cols-4 w-full sm:w-auto">
            <TabsTrigger value="ALL" className="text-xs px-2.5">All</TabsTrigger>
            <TabsTrigger value="paid" className="text-xs px-2.5">Paid</TabsTrigger>
            <TabsTrigger value="partially_paid" className="text-xs px-2.5">Partial</TabsTrigger>
            <TabsTrigger value="unpaid" className="text-xs px-2.5">Unpaid</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Main Expense Table */}
      <div className="border rounded-lg overflow-hidden bg-card shadow-2xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent">
              <TableHead className="text-xs font-semibold h-10 w-[110px]">Expense #</TableHead>
              <TableHead className="text-xs font-semibold h-10">Date</TableHead>
              <TableHead className="text-xs font-semibold h-10">Category</TableHead>
              <TableHead className="text-xs font-semibold h-10">Description / Payee</TableHead>
              <TableHead className="text-xs font-semibold h-10">Channel</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-right">Amount (₹)</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-center">Status</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-right w-[60px]">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredExpenses.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-32 text-center text-xs text-muted-foreground">
                  No expense records match your search query.
                </TableCell>
              </TableRow>
            ) : (
              filteredExpenses.map((row) => (
                <TableRow
                  key={row.id}
                  className="hover:bg-muted/30 cursor-pointer transition-colors"
                  onClick={() => {
                    setSelectedExpense(row)
                    setSheetOpen(true)
                  }}
                >
                  <TableCell className="font-mono text-xs font-semibold text-foreground">
                    {row.expense_number}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {row.occurred_date}
                  </TableCell>
                  <TableCell className="text-xs font-medium">
                    <Badge variant="outline" className="font-normal text-[11px] bg-background">
                      {row.category_name}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">
                    <div className="font-medium text-foreground truncate max-w-[220px]">
                      {row.description}
                    </div>
                    <div className="text-[11px] text-muted-foreground truncate">
                      {row.vendor_name}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs">
                    {row.source === 'whatsapp' ? (
                      <Badge className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-[10px] gap-1 font-normal">
                        <MessageSquare className="size-3" />
                        WhatsApp
                      </Badge>
                    ) : (
                      <Badge className="bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border-indigo-500/20 text-[10px] gap-1 font-normal">
                        <Laptop className="size-3" />
                        Web
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-xs font-mono font-bold text-right tabular-nums text-foreground">
                    {formatCurrency(row.amount)}
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge
                      className={
                        row.payment_status === 'paid'
                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 text-[10px] font-semibold'
                          : row.payment_status === 'partially_paid'
                          ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 text-[10px] font-semibold'
                          : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 text-[10px] font-semibold'
                      }
                    >
                      {row.payment_status === 'paid'
                        ? 'Paid'
                        : row.payment_status === 'partially_paid'
                        ? 'Partial'
                        : 'Unpaid'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="size-7">
                          <MoreVertical className="size-4 text-muted-foreground" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="text-xs">
                        <DropdownMenuItem
                          onClick={() => {
                            setSelectedExpense(row)
                            setSheetOpen(true)
                          }}
                        >
                          <Eye className="size-3.5 mr-1.5" /> View Details
                        </DropdownMenuItem>
                        {row.payment_status !== 'paid' && (
                          <DropdownMenuItem
                            onClick={() => {
                              setSelectedExpense(row)
                              setSheetOpen(true)
                            }}
                          >
                            <DollarSign className="size-3.5 mr-1.5 text-emerald-500" /> Record Settlement
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Dialogs & Sheets */}
      <RecordExpenseDialog
        open={recordDialogOpen}
        onOpenChange={setRecordDialogOpen}
        scope={scope}
        onExpenseCreated={handleExpenseCreated}
      />

      <ExpenseDetailSheet
        expense={selectedExpense}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
      />
    </div>
  )
}
