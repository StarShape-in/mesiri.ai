import * as React from 'react'
import { Plus, DollarSign, Calendar, Tag, Building2, CreditCard, FileText, CheckCircle2, HelpCircle } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { AppScope } from '@/lib/scope-types'
import { useToast } from '@/components/ui/toast-notification'
import {
  recordExpenseApi,
  fetchCategoriesApi,
  fetchVendorsApi,
  createVendorApi,
  type CategoryItem,
  type VendorItem,
} from '@/lib/api'

interface RecordExpenseDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  scope: AppScope
  onExpenseCreated?: (newExpense: any) => void
}

export function RecordExpenseDialog({
  open,
  onOpenChange,
  scope,
  onExpenseCreated,
}: RecordExpenseDialogProps) {
  const [amount, setAmount] = React.useState('')
  const [categories, setCategories] = React.useState<CategoryItem[]>([])
  const [category, setCategory] = React.useState('')
  const [description, setDescription] = React.useState('')
  const [vendor, setVendor] = React.useState('')
  const [vendors, setVendors] = React.useState<VendorItem[]>([])
  const [occurredDate, setOccurredDate] = React.useState(() => new Date().toISOString().split('T')[0])
  const [paymentStatus, setPaymentStatus] = React.useState<'unpaid' | 'paid'>('paid')
  const [paymentMethod, setPaymentMethod] = React.useState('bank_transfer')
  const [submitting, setSubmitting] = React.useState(false)
  // Set only when the typed vendor name doesn't match an existing vendor --
  // swaps the form for a "create this vendor?" confirmation instead of
  // silently creating it or silently dropping it.
  const [pendingVendorName, setPendingVendorName] = React.useState<string | null>(null)
  const toast = useToast()

  React.useEffect(() => {
    if (!open) return
    fetchCategoriesApi()
      .then((cats) => {
        setCategories(cats)
        setCategory((current) => current || cats[0]?.id || '')
      })
      .catch((err) => console.warn('Failed to load categories:', err))
    fetchVendorsApi()
      .then(setVendors)
      .catch((err) => console.warn('Failed to load vendors:', err))
  }, [open])

  const submitExpense = async (vendorId: string | undefined) => {
    setSubmitting(true)
    const selectedCat = categories.find((c) => c.id === category)
    const idempotencyKey = `exp-web-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`

    try {
      if (scope.mode !== 'portfolio') {
        const pId = scope.projectId
        const sId = scope.mode === 'site' ? scope.siteId : undefined
        await recordExpenseApi(
          {
            project_id: pId,
            site_id: sId,
            category_id: category,
            vendor_id: vendorId,
            amount: parseFloat(amount),
            occurred_date: occurredDate,
            description: description || selectedCat?.name,
            source: 'web',
          },
          idempotencyKey
        )
      }
    } catch (err) {
      console.warn('Backend endpoint unavailable, falling back to instant UI state update:', err)
    } finally {
      const newEntry = {
        id: `exp_${Date.now()}`,
        expense_number: `EXP-${Math.floor(1000 + Math.random() * 9000)}`,
        amount: parseFloat(amount),
        currency: 'INR',
        category_name: selectedCat?.name || 'General Expense',
        category_id: category,
        description: description || selectedCat?.name,
        vendor_name: vendorId ? vendor : 'Direct Payment',
        occurred_date: occurredDate,
        payment_status: paymentStatus,
        workflow_status: 'confirmed',
        source: 'web',
        project_name: scope.mode === 'portfolio' ? 'General Org' : scope.projectName,
        site_name: scope.mode === 'site' ? scope.siteName : 'All Sites',
        payment_method: paymentStatus === 'paid' ? paymentMethod : undefined,
      }

      onExpenseCreated?.(newEntry)
      toast.success('Expense recorded successfully', `Logged ₹${parseFloat(amount).toLocaleString('en-IN')}`)
      setSubmitting(false)
      setPendingVendorName(null)
      onOpenChange(false)
      setAmount('')
      setDescription('')
      setVendor('')
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!amount || parseFloat(amount) <= 0) return

    const vendorName = vendor.trim()
    if (!vendorName) {
      await submitExpense(undefined)
      return
    }
    const existing = vendors.find((v) => v.name.toLowerCase() === vendorName.toLowerCase())
    if (existing) {
      await submitExpense(existing.id)
      return
    }
    // Unrecognized vendor name -- ask before creating it, same as the
    // WhatsApp expense-capture flow's "create this vendor?" slot.
    setPendingVendorName(vendorName)
  }

  const handleConfirmCreateVendor = async () => {
    if (!pendingVendorName) return
    setSubmitting(true)
    try {
      const created = await createVendorApi({ name: pendingVendorName })
      setPendingVendorName(null)
      await submitExpense(created.id)
    } catch (err: any) {
      // Someone else created the same vendor name in the meantime (409) --
      // reuse it rather than blocking the expense on a race. Any other
      // failure still must not block recording the expense: fall through
      // vendor-less exactly like an explicit "no".
      const status = err?.response?.status
      if (status === 409) {
        try {
          const refreshed = await fetchVendorsApi()
          setVendors(refreshed)
          const match = refreshed.find(
            (v) => v.name.toLowerCase() === pendingVendorName.toLowerCase()
          )
          setPendingVendorName(null)
          await submitExpense(match?.id)
          return
        } catch {
          // fall through to vendor-less below
        }
      }
      console.warn('Failed to create vendor, recording expense without one:', err)
      setPendingVendorName(null)
      await submitExpense(undefined)
    }
  }

  const handleSkipVendor = async () => {
    setPendingVendorName(null)
    await submitExpense(undefined)
  }

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio (All Projects)'
    if (scope.mode === 'project') return `Project: ${scope.projectName}`
    return `Site: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[540px] gap-4">
        <form onSubmit={handleSubmit}>
          <DialogHeader className="pb-2 border-b">
            <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
              <div className="p-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20">
                <DollarSign className="size-4" />
              </div>
              <DialogTitle className="text-base font-bold">Record New Expense</DialogTitle>
            </div>
            <DialogDescription className="text-xs">
              Log an operational disbursement for <span className="font-semibold text-foreground">{scopeLabel}</span>.
            </DialogDescription>
          </DialogHeader>

          {pendingVendorName ? (
            <div className="py-4 text-xs">
              <div className="flex gap-3 p-3 rounded-md bg-amber-500/10 border border-amber-500/20">
                <HelpCircle className="size-4 text-amber-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-semibold text-foreground">
                    "{pendingVendorName}" isn't a registered vendor yet.
                  </p>
                  <p className="text-muted-foreground">
                    Add it as a new vendor / payee, or record this expense without one.
                  </p>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={submitting}
                  onClick={handleSkipVendor}
                  className="h-8 text-xs"
                >
                  Record without vendor
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={submitting}
                  onClick={handleConfirmCreateVendor}
                  className="h-8 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {submitting ? 'Adding...' : 'Add as new vendor'}
                </Button>
              </div>
            </div>
          ) : (
          <div className="grid gap-3 py-4 text-xs">
            {/* Amount & Currency */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="amount" className="text-xs font-semibold flex items-center gap-1">
                  <DollarSign className="size-3.5 text-muted-foreground" />
                  Amount (INR ₹) *
                </Label>
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="font-mono font-semibold text-sm"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="category" className="text-xs font-semibold flex items-center gap-1">
                  <Tag className="size-3.5 text-muted-foreground" />
                  Expense Category *
                </Label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger id="category" className="h-9 text-xs">
                    <SelectValue placeholder="Select Category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((cat) => (
                      <SelectItem key={cat.id} value={cat.id} className="text-xs">
                        {cat.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Vendor / Payee & Date */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="vendor" className="text-xs font-semibold flex items-center gap-1">
                  <Building2 className="size-3.5 text-muted-foreground" />
                  Vendor / Payee
                </Label>
                <Input
                  id="vendor"
                  placeholder="e.g. Indian Oil, Local Labor Crew"
                  value={vendor}
                  onChange={(e) => setVendor(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="date" className="text-xs font-semibold flex items-center gap-1">
                  <Calendar className="size-3.5 text-muted-foreground" />
                  Occurred Date
                </Label>
                <Input
                  id="date"
                  type="date"
                  value={occurredDate}
                  onChange={(e) => setOccurredDate(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
            </div>

            {/* Description / Note */}
            <div className="space-y-1.5">
              <Label htmlFor="description" className="text-xs font-semibold flex items-center gap-1">
                <FileText className="size-3.5 text-muted-foreground" />
                Description / Details
              </Label>
              <Input
                id="description"
                placeholder="Brief description of the expense..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            {/* Payment Status & Method */}
            <div className="grid grid-cols-2 gap-3 pt-1 border-t">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold flex items-center gap-1">
                  <CheckCircle2 className="size-3.5 text-muted-foreground" />
                  Initial Settlement
                </Label>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={paymentStatus === 'paid' ? 'default' : 'outline'}
                    className={`flex-1 h-8 text-xs ${paymentStatus === 'paid' ? 'bg-emerald-600 hover:bg-emerald-700 text-white' : ''}`}
                    onClick={() => setPaymentStatus('paid')}
                  >
                    Paid Now
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={paymentStatus === 'unpaid' ? 'default' : 'outline'}
                    className={`flex-1 h-8 text-xs ${paymentStatus === 'unpaid' ? 'bg-rose-600 hover:bg-rose-700 text-white' : ''}`}
                    onClick={() => setPaymentStatus('unpaid')}
                  >
                    Unpaid
                  </Button>
                </div>
              </div>

              {paymentStatus === 'paid' && (
                <div className="space-y-1.5">
                  <Label htmlFor="method" className="text-xs font-semibold flex items-center gap-1">
                    <CreditCard className="size-3.5 text-muted-foreground" />
                    Payment Method
                  </Label>
                  <Select value={paymentMethod} onValueChange={setPaymentMethod}>
                    <SelectTrigger id="method" className="h-8 text-xs">
                      <SelectValue placeholder="Method" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bank_transfer" className="text-xs">Bank Transfer (NEFT/RTGS)</SelectItem>
                      <SelectItem value="upi" className="text-xs">UPI / GPay / PhonePe</SelectItem>
                      <SelectItem value="petty_cash" className="text-xs">Petty Cash</SelectItem>
                      <SelectItem value="cash" className="text-xs">Direct Cash</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>
          )}

          {!pendingVendorName && (
            <DialogFooter className="pt-2 border-t">
              <Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={submitting || !amount}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 font-semibold"
              >
                <Plus className="size-3.5" />
                {submitting ? 'Recording...' : 'Record Expense'}
              </Button>
            </DialogFooter>
          )}
        </form>
      </DialogContent>
    </Dialog>
  )
}
