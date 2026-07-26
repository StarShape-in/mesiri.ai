import * as React from 'react'
import {
  Search,
  ExternalLink,
  Calendar,
  Receipt,
  Tag,
} from 'lucide-react'
import {
  Sheet,
  SheetContent,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { fetchExpensesApi, type CategoryItem } from '@/lib/api'
import { Link } from 'react-router-dom'

interface CategoryDetailSheetProps {
  category: CategoryItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

export function CategoryDetailSheet({
  category,
  open,
  onOpenChange,
}: CategoryDetailSheetProps) {
  const [expenses, setExpenses] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(false)
  const [search, setSearch] = React.useState('')

  React.useEffect(() => {
    if (!open || !category?.id) return
    let active = true
    const categoryId = category.id
    async function loadCategoryExpenses() {
      setLoading(true)
      try {
        const data = await fetchExpensesApi({ category_id: categoryId })
        if (active && Array.isArray(data)) {
          setExpenses(data)
        }
      } catch (err) {
        console.warn('Failed to load category expenses:', err)
        if (active) setExpenses([])
      } finally {
        if (active) setLoading(false)
      }
    }
    loadCategoryExpenses()
    return () => {
      active = false
    }
  }, [open, category?.id])

  const filteredExpenses = React.useMemo(() => {
    return expenses.filter(
      (e) =>
        (e.description || '').toLowerCase().includes(search.toLowerCase()) ||
        (e.id || '').toLowerCase().includes(search.toLowerCase()) ||
        (e.source || '').toLowerCase().includes(search.toLowerCase())
    )
  }, [expenses, search])

  const totalFilteredAmount = React.useMemo(() => {
    return filteredExpenses.reduce((acc, curr) => acc + (parseFloat(curr.amount) || 0), 0)
  }, [filteredExpenses])

  if (!category) return null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md w-full p-0 flex flex-col gap-0 bg-background overflow-hidden border-l">
        {/* Header */}
        <div className="p-5 border-b bg-muted/30">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <div className="size-8 rounded-lg bg-emerald-500/10 text-emerald-600 flex items-center justify-center font-bold text-xs shrink-0">
                <Tag className="size-4" />
              </div>
              <div>
                <h2 className="text-base font-bold text-foreground leading-snug flex items-center gap-2">
                  {category.name}
                  {category.code && (
                    <Badge variant="outline" className="font-mono text-[10px] uppercase">
                      {category.code}
                    </Badge>
                  )}
                </h2>
                <span className="text-xs text-muted-foreground">
                  Category Expense Breakdown
                </span>
              </div>
            </div>
            <Badge
              className={
                category.status === 'active'
                  ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20 text-[10px]'
                  : 'bg-muted text-muted-foreground text-[10px]'
              }
            >
              {category.status.toUpperCase()}
            </Badge>
          </div>

          {/* Quick Metrics Cards */}
          <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t">
            <div className="p-2.5 rounded-lg border bg-card/60">
              <span className="text-[10px] text-muted-foreground uppercase font-semibold block">
                Total Expenses
              </span>
              <div className="font-bold font-mono text-base text-foreground mt-0.5">
                {expenses.length} Records
              </div>
            </div>
            <div className="p-2.5 rounded-lg border bg-card/60">
              <span className="text-[10px] text-muted-foreground uppercase font-semibold block">
                Total Spent
              </span>
              <div className="font-bold font-mono text-base text-emerald-600 mt-0.5">
                {formatCurrency(category.total_amount_spent || totalFilteredAmount)}
              </div>
            </div>
          </div>
        </div>

        {/* Search & Expense List */}
        <div className="p-4 flex-1 flex flex-col gap-3 overflow-hidden">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
            <Input
              placeholder="Search expenses in this category..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-8 text-xs"
            />
          </div>

          <div className="flex-1 overflow-y-auto flex flex-col gap-2 pr-0.5">
            {loading ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                Loading category expenses...
              </div>
            ) : filteredExpenses.length === 0 ? (
              <div className="py-12 text-center text-xs text-muted-foreground border rounded-lg bg-card/40">
                No expenses found for this category.
              </div>
            ) : (
              filteredExpenses.map((exp: any, idx: number) => {
                const amount = parseFloat(exp.amount) || 0
                const expNumber = `EXP-${String(exp.id || '').slice(0, 4).toUpperCase() || 1000 + idx}`
                return (
                  <div
                    key={exp.id || idx}
                    className="p-3 rounded-lg border bg-card/60 hover:bg-card transition-colors flex items-center justify-between gap-3 text-xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="size-8 rounded-full bg-emerald-500/10 text-emerald-600 flex items-center justify-center shrink-0">
                        <Receipt className="size-4" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-foreground truncate">
                            {exp.description || 'Recorded Expense'}
                          </span>
                          <span className="text-[10px] font-mono text-muted-foreground">
                            {expNumber}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-muted-foreground mt-0.5">
                          <span className="flex items-center gap-1">
                            <Calendar className="size-3" />
                            {exp.occurred_date}
                          </span>
                          <span>•</span>
                          <span className="capitalize">{exp.source || 'web'}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col items-end shrink-0">
                      <span className="font-mono font-bold text-xs text-foreground">
                        {formatCurrency(amount)}
                      </span>
                      <Badge
                        variant="outline"
                        className={
                          exp.payment_status === 'paid'
                            ? 'border-emerald-500/30 text-emerald-600 text-[9px] px-1 py-0'
                            : 'border-amber-500/30 text-amber-600 text-[9px] px-1 py-0'
                        }
                      >
                        {exp.payment_status?.toUpperCase() || 'CONFIRMED'}
                      </Badge>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t bg-muted/20 flex items-center justify-between text-xs">
          <span className="text-muted-foreground">
            Showing {filteredExpenses.length} of {expenses.length} expenses
          </span>
          <Link
            to="/finance/expenses"
            onClick={() => onOpenChange(false)}
            className="text-xs text-blue-600 dark:text-blue-400 font-semibold hover:underline flex items-center gap-1"
          >
            All Expenses <ExternalLink className="size-3" />
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  )
}
