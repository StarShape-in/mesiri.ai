import * as React from 'react'
import {
  DollarSign,
  Landmark,
  ArrowLeftRight,
  Plus,
  Store,
  Tags,
  Receipt,
  AlertTriangle,
  PieChart as PieChartIcon,
  Activity,
  ChevronRight,
} from 'lucide-react'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Link } from 'react-router-dom'
import { useScope } from '@/lib/ScopeContext'
import { KpiCard } from '@/components/ui/kpi-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  fetchFinanceSummaryApi,
  fetchAccountsApi,
  fetchTransactionsApi,
  type FinanceSummaryItem,
  type MoneyTransactionItem,
} from '@/lib/api'
import { RecordExpenseDialog } from '@/components/expenses/record-expense-dialog'
import { TransferMoneyDialog } from '@/components/accounts/transfer-money-dialog'
import { CreateCategoryDialog } from '@/components/categories/create-category-dialog'
import { CreateVendorDialog } from '@/components/vendors/create-vendor-dialog'

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

const CATEGORY_COLORS = [
  '#10b981', // emerald
  '#3b82f6', // blue
  '#8b5cf6', // purple
  '#f59e0b', // amber
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#6366f1', // indigo
]

export default function FinanceOverviewPage() {
  const { scope } = useScope()

  const [summary, setSummary] = React.useState<FinanceSummaryItem | null>(null)
  const [accounts, setAccounts] = React.useState<any[]>([])
  const [recentTransactions, setRecentTransactions] = React.useState<MoneyTransactionItem[]>([])
  const [loading, setLoading] = React.useState(true)

  // Dialog States
  const [recordExpenseOpen, setRecordExpenseOpen] = React.useState(false)
  const [transferOpen, setTransferOpen] = React.useState(false)
  const [createCategoryOpen, setCreateCategoryOpen] = React.useState(false)
  const [createVendorOpen, setCreateVendorOpen] = React.useState(false)

  const loadData = React.useCallback(async () => {
    setLoading(true)
    try {
      const [sumData, accData, txData] = await Promise.all([
        fetchFinanceSummaryApi(),
        fetchAccountsApi(),
        fetchTransactionsApi({ limit: 6 }),
      ])
      if (sumData) setSummary(sumData)
      if (Array.isArray(accData)) setAccounts(accData)
      if (Array.isArray(txData)) setRecentTransactions(txData)
    } catch (err) {
      console.warn('Failed to load finance overview summary:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  React.useEffect(() => {
    loadData()
  }, [loadData])

  const pieChartData = React.useMemo(() => {
    if (!summary?.category_breakdown) return []
    return summary.category_breakdown
      .filter((c) => (parseFloat(String(c.amount)) || 0) > 0)
      .map((c, i) => ({
        name: c.name,
        value: parseFloat(String(c.amount)) || 0,
        color: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
      }))
  }, [summary])

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (Executive CFO Financial Command Center)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  return (
    <div className="flex flex-col gap-5 w-full max-w-full relative pb-12">
      {/* Page Header & Quick Action Hub */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b pb-4">
        <div className="flex items-center gap-3">
          <div className="size-11 rounded-xl border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0 shadow-2xs">
            <Activity className="size-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              Finance Overview
              <Badge variant="outline" className="text-[10px] font-mono border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
                Executive Cockpit
              </Badge>
            </h1>
            <p className="text-xs text-muted-foreground font-medium">{scopeLabel}</p>
          </div>
        </div>

        {/* Action Hub Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            className="h-8 text-xs font-semibold gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white shadow-2xs"
            onClick={() => setRecordExpenseOpen(true)}
          >
            <Plus className="size-3.5" />
            Record Expense
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs font-semibold gap-1.5 shadow-2xs"
            onClick={() => setTransferOpen(true)}
          >
            <ArrowLeftRight className="size-3.5 text-blue-500" />
            Transfer Funds
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs font-semibold gap-1.5 shadow-2xs"
            onClick={() => setCreateVendorOpen(true)}
          >
            <Store className="size-3.5 text-indigo-500" />
            Add Vendor
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-8 text-xs font-semibold gap-1.5 shadow-2xs"
            onClick={() => setCreateCategoryOpen(true)}
          >
            <Tags className="size-3.5 text-purple-500" />
            Add Category
          </Button>
        </div>
      </div>

      {/* Top Executive KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          title="Total Cash & Bank Liquidity"
          value={
            <span className="text-emerald-600 dark:text-emerald-400">
              {formatCurrency(parseFloat(String(summary?.total_liquidity || 0)))}
            </span>
          }
          trend="up"
          trendValue={`${summary?.active_accounts_count || 0} Accounts`}
          description="Available cash across all balances"
          icon={<Landmark className="text-emerald-500" />}
        />
        <KpiCard
          title="Total Confirmed Expenses"
          value={
            <span className="text-foreground">
              {formatCurrency(parseFloat(String(summary?.total_expenses || 0)))}
            </span>
          }
          trend="neutral"
          trendValue={`${summary?.active_categories_count || 0} Categories`}
          description="Cumulative recorded disbursements"
          icon={<DollarSign className="text-blue-500" />}
        />
        <KpiCard
          title="Unpaid Liabilities"
          value={
            <span className="text-amber-600 dark:text-amber-400">
              {formatCurrency(parseFloat(String(summary?.unpaid_expenses || 0)))}
            </span>
          }
          trend="down"
          trendValue="Pending Payout"
          description="Unpaid vendor invoices"
          icon={<AlertTriangle className="text-amber-500" />}
        />
        <KpiCard
          title="Verified Payees & Suppliers"
          value={
            <span className="text-indigo-600 dark:text-indigo-400">
              {summary?.active_vendors_count || 0} Vendors
            </span>
          }
          trend="up"
          trendValue="WhatsApp Live"
          description="Active contractor & supplier accounts"
          icon={<Store className="text-indigo-500" />}
        />
      </div>

      {/* Analytics & Distribution Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Category Spend Distribution Chart (2 cols) */}
        <Card className="lg:col-span-2 p-5 flex flex-col gap-4 border shadow-2xs">
          <div className="flex items-center justify-between border-b pb-3">
            <div className="flex items-center gap-2">
              <PieChartIcon className="size-4 text-emerald-500" />
              <h3 className="font-bold text-sm text-foreground">Expense Category Breakdown</h3>
            </div>
            <Link
              to="/finance/categories"
              className="text-xs text-emerald-600 dark:text-emerald-400 hover:underline font-medium flex items-center gap-1"
            >
              All Categories <ChevronRight className="size-3" />
            </Link>
          </div>

          {loading ? (
            <div className="h-64 flex items-center justify-center text-xs text-muted-foreground">
              Loading financial breakdown...
            </div>
          ) : pieChartData.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-xs text-muted-foreground gap-2">
              <PieChartIcon className="size-8 text-muted-foreground/30" />
              <span>No categorized expenses recorded yet.</span>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 items-center gap-4">
              <div className="h-60 w-full relative">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieChartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(val: any) => formatCurrency(Number(val))}
                      contentStyle={{
                        fontSize: '12px',
                        backgroundColor: 'var(--card)',
                        borderColor: 'var(--border)',
                        borderRadius: '8px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              <div className="flex flex-col gap-2 font-xs">
                {pieChartData.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded-md bg-muted/30 border text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="size-3 rounded-full shrink-0"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="font-semibold text-foreground truncate">{item.name}</span>
                    </div>
                    <span className="font-mono font-bold text-foreground">
                      {formatCurrency(item.value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        {/* Account Balances & Float Levels (1 col) */}
        <Card className="p-5 flex flex-col gap-4 border shadow-2xs">
          <div className="flex items-center justify-between border-b pb-3">
            <div className="flex items-center gap-2">
              <Landmark className="size-4 text-blue-500" />
              <h3 className="font-bold text-sm text-foreground">Accounts Liquidity</h3>
            </div>
            <Link
              to="/finance/accounts"
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium flex items-center gap-1"
            >
              Accounts Page <ChevronRight className="size-3" />
            </Link>
          </div>

          <div className="flex flex-col gap-2.5 overflow-y-auto max-h-[300px]">
            {loading ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                Loading accounts...
              </div>
            ) : accounts.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                No active accounts registered.
              </div>
            ) : (
              accounts.map((acc: any) => {
                const bal = parseFloat(String(acc.current_balance || acc.opening_balance || 0))
                const isLow = bal < 50000
                return (
                  <div
                    key={acc.id}
                    className="p-3 rounded-lg border bg-card/60 flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="size-8 rounded-full bg-blue-500/10 text-blue-600 flex items-center justify-center font-bold text-xs shrink-0">
                        <Landmark className="size-4" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="font-semibold text-foreground truncate">{acc.name}</span>
                        <span className="text-[10px] text-muted-foreground uppercase font-mono">
                          {acc.account_type}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-col items-end shrink-0">
                      <span className={`font-mono font-bold text-xs ${isLow ? 'text-rose-600 dark:text-rose-400' : 'text-foreground'}`}>
                        {formatCurrency(bal)}
                      </span>
                      {isLow && (
                        <Badge className="bg-rose-500/15 text-rose-600 text-[9px] px-1 py-0">
                          Low Float
                        </Badge>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </Card>
      </div>

      {/* Recent Activity Ticker */}
      <Card className="p-5 flex flex-col gap-4 border shadow-2xs">
        <div className="flex items-center justify-between border-b pb-3">
          <div className="flex items-center gap-2">
            <Activity className="size-4 text-purple-500" />
            <h3 className="font-bold text-sm text-foreground">Recent General Ledger Activity</h3>
          </div>
          <Link
            to="/finance/transactions"
            className="text-xs text-purple-600 dark:text-purple-400 hover:underline font-medium flex items-center gap-1"
          >
            All Ledger Transactions <ChevronRight className="size-3" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
          {recentTransactions.length === 0 ? (
            <div className="col-span-full py-8 text-center text-xs text-muted-foreground">
              No recent general ledger transactions.
            </div>
          ) : (
            recentTransactions.map((tx: any, idx: number) => {
              const amount = parseFloat(String(tx.amount)) || 0
              return (
                <div
                  key={tx.id || idx}
                  className="p-3 rounded-lg border bg-card/60 flex items-center justify-between gap-3 text-xs"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="size-8 rounded-lg bg-muted text-foreground flex items-center justify-center font-bold text-xs shrink-0">
                      <Receipt className="size-4 text-emerald-500" />
                    </div>
                    <div className="flex flex-col min-w-0">
                      <span className="font-semibold text-foreground truncate">
                        {tx.description || 'Ledger Transaction'}
                      </span>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {tx.occurred_date} • {tx.transaction_type?.toUpperCase()}
                      </span>
                    </div>
                  </div>

                  <span className="font-mono font-bold text-xs text-foreground shrink-0">
                    {formatCurrency(amount)}
                  </span>
                </div>
              )
            })
          )}
        </div>
      </Card>

      {/* Dialog Modals */}
      <RecordExpenseDialog
        open={recordExpenseOpen}
        onOpenChange={setRecordExpenseOpen}
        scope={scope}
        onExpenseCreated={loadData}
      />

      <TransferMoneyDialog
        open={transferOpen}
        onOpenChange={setTransferOpen}
        accounts={accounts}
        onTransferCompleted={loadData}
      />

      <CreateCategoryDialog
        open={createCategoryOpen}
        onOpenChange={setCreateCategoryOpen}
        onSuccess={loadData}
      />

      <CreateVendorDialog
        open={createVendorOpen}
        onOpenChange={setCreateVendorOpen}
        onSuccess={loadData}
      />
    </div>
  )
}
