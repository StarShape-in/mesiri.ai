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
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Calendar,
  Image as ImageIcon,
} from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { BulkActionBar } from '@/components/ui/bulk-action-bar'
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
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RecordExpenseDialog } from '@/components/expenses/record-expense-dialog'
import { ExpenseDetailSheet } from '@/components/expenses/expense-detail-sheet'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

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
  receipt_url?: string
}

type SortField = 'date' | 'amount' | 'number' | 'category'
type SortOrder = 'asc' | 'desc'

import { fetchExpensesApi } from '@/lib/api'

export default function ExpensesPage() {
  const { scope } = useScope()

  const [expenses, setExpenses] = React.useState<ExpenseItem[]>([])
  const [search, setSearch] = React.useState('')
  const [categoryFilter, setCategoryFilter] = React.useState('ALL')
  const [paymentStatusFilter, setPaymentStatusFilter] = React.useState('ALL')
  const [sourceFilter, setSourceFilter] = React.useState('ALL')
  const [datePreset, setDatePreset] = React.useState('ALL')

  React.useEffect(() => {
    let active = true
    async function loadBackendExpenses() {
      try {
        const rawData = await fetchExpensesApi({
          project_id: scope.mode !== 'portfolio' ? scope.projectId : undefined,
          site_id: scope.mode === 'site' ? scope.siteId : undefined,
        })
        if (active && Array.isArray(rawData)) {
          const mapped: ExpenseItem[] = rawData.map((item: any, idx: number) => ({
            id: String(item.id) || `exp_real_${idx}`,
            expense_number: `EXP-${String(item.id || '').slice(0, 4).toUpperCase() || String(1000 + idx)}`,
            amount: parseFloat(item.amount) || 0,
            currency: item.currency || 'INR',
            category_name: item.category_name || item.category_id || 'General Expense',
            category_id: String(item.category_id || 'general'),
            description: item.description || 'Recorded Expense',
            vendor_name: 'Direct Payee',
            occurred_date: item.occurred_date || new Date().toISOString().split('T')[0],
            payment_status: item.payment_status === 'paid' ? 'paid' : item.payment_status === 'partially_paid' ? 'partially_paid' : 'unpaid',
            workflow_status: item.workflow_status === 'reversed' ? 'reversed' : item.workflow_status === 'pending' ? 'pending' : 'confirmed',
            source: item.source === 'whatsapp' ? 'whatsapp' : 'web',
            project_name: scope.mode === 'portfolio' ? 'Org Wide' : scope.projectName,
            site_name: scope.mode === 'site' ? scope.siteName : 'All Sites',
          }))
          setExpenses(mapped)
        }
      } catch (err) {
        console.warn('Live backend expenses fetch error:', err)
        if (active) setExpenses([])
      }
    }
    loadBackendExpenses()
    return () => {
      active = false
    }
  }, [scope])

  // Selection & Bulk Action state
  const [selectedIds, setSelectedIds] = React.useState<string[]>([])

  // Sorting state
  const [sortField, setSortField] = React.useState<SortField>('date')
  const [sortOrder, setSortOrder] = React.useState<SortOrder>('desc')

  // Pagination state
  const [currentPage, setCurrentPage] = React.useState(1)
  const [pageSize, setPageSize] = React.useState(10)

  // Dialog & Sheet state
  const [recordDialogOpen, setRecordDialogOpen] = React.useState(false)
  const [selectedExpense, setSelectedExpense] = React.useState<ExpenseItem | null>(null)
  const [sheetOpen, setSheetOpen] = React.useState(false)
  const [previewReceiptUrl, setPreviewReceiptUrl] = React.useState<string | null>(null)

  const handleExpenseCreated = (newExpense: ExpenseItem) => {
    setExpenses((prev) => [newExpense, ...prev])
  }

  // Handle Sort Toggle
  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }

  // Filtered & Sorted expenses
  const filteredExpenses = React.useMemo(() => {
    const today = new Date().toISOString().split('T')[0]

    return expenses
      .filter((item) => {
        const matchesSearch =
          item.expense_number.toLowerCase().includes(search.toLowerCase()) ||
          item.description.toLowerCase().includes(search.toLowerCase()) ||
          item.vendor_name.toLowerCase().includes(search.toLowerCase()) ||
          item.category_name.toLowerCase().includes(search.toLowerCase())

        if (!matchesSearch) return false

        if (categoryFilter !== 'ALL' && item.category_id !== categoryFilter) return false
        if (paymentStatusFilter !== 'ALL' && item.payment_status !== paymentStatusFilter) return false
        if (sourceFilter !== 'ALL' && item.source !== sourceFilter) return false

        // Date Preset filter
        if (datePreset === 'TODAY' && item.occurred_date !== today) return false
        if (datePreset === 'THIS_MONTH') {
          const itemMonth = item.occurred_date.substring(0, 7)
          const currentMonth = today.substring(0, 7)
          if (itemMonth !== currentMonth) return false
        }

        return true
      })
      .sort((a, b) => {
        let modifier = sortOrder === 'asc' ? 1 : -1
        if (sortField === 'date') return a.occurred_date.localeCompare(b.occurred_date) * modifier
        if (sortField === 'amount') return (a.amount - b.amount) * modifier
        if (sortField === 'number') return a.expense_number.localeCompare(b.expense_number) * modifier
        if (sortField === 'category') return a.category_name.localeCompare(b.category_name) * modifier
        return 0
      })
  }, [expenses, search, categoryFilter, paymentStatusFilter, sourceFilter, datePreset, sortField, sortOrder])

  // Pagination calculation
  const totalPages = Math.ceil(filteredExpenses.length / pageSize) || 1
  const paginatedExpenses = React.useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredExpenses.slice(start, start + pageSize)
  }, [filteredExpenses, currentPage, pageSize])

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

  // Filtered total sum
  const filteredSum = React.useMemo(() => {
    return filteredExpenses.reduce((acc, curr) => acc + curr.amount, 0)
  }, [filteredExpenses])

  // Bulk Selection Handlers
  const isAllSelected = paginatedExpenses.length > 0 && paginatedExpenses.every((e) => selectedIds.includes(e.id))
  
  const toggleSelectAll = () => {
    if (isAllSelected) {
      setSelectedIds([])
    } else {
      setSelectedIds(paginatedExpenses.map((e) => e.id))
    }
  }

  const toggleSelectRow = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    )
  }

  const handleBulkMarkAsPaid = () => {
    setExpenses((prev) =>
      prev.map((item) => (selectedIds.includes(item.id) ? { ...item, payment_status: 'paid' as const } : item))
    )
    setSelectedIds([])
  }

  const handleBulkVoid = () => {
    if (confirm(`Are you sure you want to void ${selectedIds.length} selected expenses?`)) {
      setExpenses((prev) => prev.filter((item) => !selectedIds.includes(item.id)))
      setSelectedIds([])
    }
  }

  const handleBulkExport = () => {
    const selectedRecords = expenses.filter((e) => selectedIds.includes(e.id))
    alert(`Exporting ${selectedRecords.length} selected expenses to CSV...`)
  }

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

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) return <ArrowUpDown className="size-3 text-muted-foreground/60 ml-1 inline" />
    return sortOrder === 'asc' ? (
      <ArrowUp className="size-3 text-emerald-500 ml-1 inline" />
    ) : (
      <ArrowDown className="size-3 text-emerald-500 ml-1 inline" />
    )
  }

  return (
    <div className="flex flex-col gap-4 w-full max-w-full relative pb-12">
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

      {/* KPI Cards Grid */}
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
        <div className="flex flex-wrap gap-2 w-full sm:w-auto flex-1 items-center">
          <div className="relative w-full sm:w-64">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Search expenses, vendors, number..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>

          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-40">
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

          <Select value={datePreset} onValueChange={setDatePreset}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-36">
              <Calendar className="size-3.5 mr-1 text-muted-foreground" />
              <SelectValue placeholder="All Dates" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All Dates</SelectItem>
              <SelectItem value="TODAY">Today</SelectItem>
              <SelectItem value="THIS_MONTH">This Month</SelectItem>
            </SelectContent>
          </Select>

          <Select value={sourceFilter} onValueChange={setSourceFilter}>
            <SelectTrigger className="h-9 text-xs w-full sm:w-32">
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

      {/* Filter Summary Banner */}
      <div className="flex items-center justify-between text-xs px-1 text-muted-foreground font-medium">
        <div>
          Showing <span className="text-foreground font-semibold">{filteredExpenses.length}</span> of {expenses.length} records
          {filteredExpenses.length !== expenses.length && (
            <span> • Filtered Total: <span className="font-mono text-emerald-600 dark:text-emerald-400 font-semibold">{formatCurrency(filteredSum)}</span></span>
          )}
        </div>
        {selectedIds.length > 0 && (
          <span className="text-emerald-600 font-semibold text-xs">
            {selectedIds.length} items checked
          </span>
        )}
      </div>

      {/* Main Expense Table */}
      <div className="border rounded-lg overflow-hidden bg-card shadow-2xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[40px] px-3">
                <input
                  type="checkbox"
                  checked={isAllSelected}
                  onChange={toggleSelectAll}
                  className="size-4 rounded border-border text-emerald-600 focus:ring-emerald-500 cursor-pointer accent-emerald-600"
                  title="Select All"
                />
              </TableHead>
              <TableHead
                className="text-xs font-semibold h-10 w-[110px] cursor-pointer select-none"
                onClick={() => toggleSort('number')}
              >
                Expense # {renderSortIcon('number')}
              </TableHead>
              <TableHead
                className="text-xs font-semibold h-10 cursor-pointer select-none"
                onClick={() => toggleSort('date')}
              >
                Date {renderSortIcon('date')}
              </TableHead>
              <TableHead
                className="text-xs font-semibold h-10 cursor-pointer select-none"
                onClick={() => toggleSort('category')}
              >
                Category {renderSortIcon('category')}
              </TableHead>
              <TableHead className="text-xs font-semibold h-10">Description / Payee</TableHead>
              <TableHead className="text-xs font-semibold h-10">Channel</TableHead>
              <TableHead
                className="text-xs font-semibold h-10 text-right cursor-pointer select-none"
                onClick={() => toggleSort('amount')}
              >
                Amount (₹) {renderSortIcon('amount')}
              </TableHead>
              <TableHead className="text-xs font-semibold h-10 text-center">Status</TableHead>
              <TableHead className="text-xs font-semibold h-10 text-right w-[60px]">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedExpenses.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="h-32 text-center text-xs text-muted-foreground">
                  No expense records match your search or filter criteria.
                </TableCell>
              </TableRow>
            ) : (
              paginatedExpenses.map((row) => {
                const isSelected = selectedIds.includes(row.id)
                return (
                  <TableRow
                    key={row.id}
                    className={`hover:bg-muted/40 cursor-pointer transition-colors ${isSelected ? 'bg-emerald-500/5' : ''}`}
                    onClick={() => {
                      setSelectedExpense(row)
                      setSheetOpen(true)
                    }}
                  >
                    <TableCell className="px-3" onClick={(e) => toggleSelectRow(row.id, e)}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        className="size-4 rounded border-border text-emerald-600 focus:ring-emerald-500 cursor-pointer accent-emerald-600"
                      />
                    </TableCell>
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
                      <div className="font-medium text-foreground truncate max-w-[200px] flex items-center gap-1.5">
                        {row.description}
                        {row.receipt_url && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              setPreviewReceiptUrl(row.receipt_url || null)
                            }}
                            className="text-muted-foreground hover:text-emerald-600"
                            title="View Receipt"
                          >
                            <ImageIcon className="size-3.5" />
                          </button>
                        )}
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
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-rose-600"
                            onClick={() => {
                              if (confirm(`Void expense ${row.expense_number}?`)) {
                                setExpenses((prev) => prev.filter((e) => e.id !== row.id))
                              }
                            }}
                          >
                            <Trash2 className="size-3.5 mr-1.5" /> Void Expense
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>

        {/* Pagination Bar */}
        <div className="flex items-center justify-between px-3 py-2 border-t bg-muted/20 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Rows per page:</span>
            <Select value={pageSize.toString()} onValueChange={(val) => setPageSize(Number(val))}>
              <SelectTrigger className="h-7 text-xs w-16">
                <SelectValue placeholder="10" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="5">5</SelectItem>
                <SelectItem value="10">10</SelectItem>
                <SelectItem value="25">25</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-muted-foreground font-mono">
              Page {currentPage} of {totalPages}
            </span>
            <div className="flex gap-1">
              <Button
                variant="outline"
                size="sm"
                className="h-7 size-7 p-0"
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => p - 1)}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 size-7 p-0"
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => p + 1)}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Bulk Action Bar */}
      <BulkActionBar selectedCount={selectedIds.length} onClear={() => setSelectedIds([])}>
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs gap-1.5 font-semibold text-emerald-600 border-emerald-500/40 hover:bg-emerald-500/10"
          onClick={handleBulkMarkAsPaid}
        >
          <CheckCircle2 className="size-3.5" />
          Mark as Paid
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs gap-1.5 font-semibold"
          onClick={handleBulkExport}
        >
          <Download className="size-3.5" />
          Export Selected
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs gap-1.5 font-semibold text-rose-600 border-rose-500/40 hover:bg-rose-500/10"
          onClick={handleBulkVoid}
        >
          <Trash2 className="size-3.5" />
          Void Selected
        </Button>
      </BulkActionBar>

      {/* Receipt Image Lightbox Dialog */}
      <Dialog open={!!previewReceiptUrl} onOpenChange={() => setPreviewReceiptUrl(null)}>
        <DialogContent className="sm:max-w-[500px] p-2">
          <DialogHeader className="px-3 pt-2">
            <DialogTitle className="text-sm font-semibold flex items-center gap-1.5">
              <ImageIcon className="size-4 text-emerald-500" />
              Receipt / Invoice Attachment
            </DialogTitle>
          </DialogHeader>
          {previewReceiptUrl && (
            <div className="p-2 flex items-center justify-center bg-black/90 rounded-md overflow-hidden">
              <img
                src={previewReceiptUrl}
                alt="Receipt Attachment"
                className="max-h-[400px] w-auto object-contain rounded"
              />
            </div>
          )}
        </DialogContent>
      </Dialog>

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
