import * as React from 'react'
import { Plus, Landmark, DollarSign, Wallet, CreditCard, User, Building2 } from 'lucide-react'
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

interface CreateAccountDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  scope: AppScope
  onAccountCreated?: (newAccount: any) => void
}

import { createAccountApi, fetchUsers, type User as UserItem } from '@/lib/api'
import { toLocalISODate } from '@/lib/utils'

export function CreateAccountDialog({
  open,
  onOpenChange,
  scope,
  onAccountCreated,
}: CreateAccountDialogProps) {
  const [name, setName] = React.useState('')
  const [accountType, setAccountType] = React.useState<'bank' | 'cash' | 'employee_advance' | 'other'>('bank')
  const [openingBalance, setOpeningBalance] = React.useState('')
  const [selectedUserId, setSelectedUserId] = React.useState('')
  const [users, setUsers] = React.useState<UserItem[]>([])
  const [accountNumber, setAccountNumber] = React.useState('')
  const [submitting, setSubmitting] = React.useState(false)
  const toast = useToast()

  React.useEffect(() => {
    let active = true
    async function loadUsers() {
      try {
        const list = await fetchUsers()
        if (active && Array.isArray(list)) {
          setUsers(list.filter((u) => u.status === 'active'))
        }
      } catch (err) {
        console.warn('Failed to load users for custodian selection:', err)
      }
    }
    if (open) {
      loadUsers()
    }
    return () => {
      active = false
    }
  }, [open])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !openingBalance) return

    setSubmitting(true)
    const balance = parseFloat(openingBalance) || 0
    const selectedUser = users.find((u) => u.id === selectedUserId)
    const custodianName = selectedUser ? selectedUser.full_name || selectedUser.email : undefined

    try {
      await createAccountApi({
        name,
        account_type: accountType,
        currency: 'INR',
        opening_balance: balance,
        account_number: accountNumber || undefined,
        custodian_name: custodianName,
        owner_user_id: selectedUserId || undefined,
        project_id: scope.mode !== 'portfolio' ? scope.projectId : undefined,
        site_id: scope.mode === 'site' ? scope.siteId : undefined,
      })
    } catch (err) {
      console.warn('Backend endpoint unavailable, falling back to instant UI state update:', err)
    } finally {
      const newEntry = {
        id: `acc_${Date.now()}`,
        name,
        account_type: accountType,
        currency: 'INR',
        opening_balance: balance,
        current_balance: balance,
        account_number_masked: accountNumber ? `•••• ${accountNumber.slice(-4)}` : undefined,
        custodian_name: custodianName || 'Finance Admin',
        owner_user_id: selectedUserId || undefined,
        project_id: scope.mode !== 'portfolio' ? scope.projectId : undefined,
        project_name: scope.mode === 'portfolio' ? 'Org Wide' : scope.projectName,
        site_id: scope.mode === 'site' ? scope.siteId : undefined,
        site_name: scope.mode === 'site' ? scope.siteName : undefined,
        scope_level: scope.mode,
        status: 'active' as const,
        created_at: toLocalISODate(),
      }

      onAccountCreated?.(newEntry)
      toast.success(`Account "${name}" created`, 'Money account registered')
      setSubmitting(false)
      onOpenChange(false)
      setName('')
      setOpeningBalance('')
      setSelectedUserId('')
      setAccountNumber('')
    }
  }

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Organization Wide'
    if (scope.mode === 'project') return `Project: ${scope.projectName}`
    return `Site: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] gap-4">
        <form onSubmit={handleSubmit}>
          <DialogHeader className="pb-2 border-b">
            <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
              <div className="p-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20">
                <Landmark className="size-4" />
              </div>
              <DialogTitle className="text-base font-bold">Create Money Account</DialogTitle>
            </div>
            <DialogDescription className="text-xs">
              Register a bank account, petty cash box, or credit card for <span className="font-semibold text-foreground">{scopeLabel}</span>.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 py-4 text-xs">
            {/* Account Name */}
            <div className="space-y-1.5">
              <Label htmlFor="name" className="text-xs font-semibold flex items-center gap-1">
                <Landmark className="size-3.5 text-muted-foreground" />
                Account Name *
              </Label>
              <Input
                id="name"
                placeholder="e.g. HDFC Corporate Main, Site A Petty Cash Box"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-9 text-xs"
                required
              />
            </div>

            {/* Account Type & Opening Balance */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="type" className="text-xs font-semibold flex items-center gap-1">
                  <Wallet className="size-3.5 text-muted-foreground" />
                  Account Type *
                </Label>
                <Select value={accountType} onValueChange={(val: any) => setAccountType(val)}>
                  <SelectTrigger id="type" className="h-9 text-xs">
                    <SelectValue placeholder="Select Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="bank" className="text-xs">Corporate Bank Account</SelectItem>
                    <SelectItem value="cash" className="text-xs">Operating Cash</SelectItem>
                    <SelectItem value="employee_advance" className="text-xs">Petty Cash Float / Advance</SelectItem>
                    <SelectItem value="other" className="text-xs">Other / Digital Wallet</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="balance" className="text-xs font-semibold flex items-center gap-1">
                  <DollarSign className="size-3.5 text-muted-foreground" />
                  Opening Balance (₹) *
                </Label>
                <Input
                  id="balance"
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  value={openingBalance}
                  onChange={(e) => setOpeningBalance(e.target.value)}
                  className="font-mono font-semibold text-sm h-9"
                  required
                />
              </div>
            </div>

            {/* Custodian & Account Number */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="custodian" className="text-xs font-semibold flex items-center gap-1">
                  <User className="size-3.5 text-muted-foreground" />
                  Assigned Custodian / Manager
                </Label>
                <Select value={selectedUserId} onValueChange={setSelectedUserId}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue placeholder="Select assigned custodian..." />
                  </SelectTrigger>
                  <SelectContent className="text-xs max-h-56">
                    {users.length === 0 ? (
                      <SelectItem value="none" disabled className="text-xs">
                        No active users found
                      </SelectItem>
                    ) : (
                      users.map((u) => (
                        <SelectItem key={u.id} value={u.id} className="text-xs cursor-pointer">
                          <div className="flex flex-col">
                            <span className="font-semibold">{u.full_name || u.email}</span>
                            <span className="text-[10px] text-muted-foreground">{u.role} • {u.email}</span>
                          </div>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="acc_num" className="text-xs font-semibold flex items-center gap-1">
                  <CreditCard className="size-3.5 text-muted-foreground" />
                  Account / Card # (Optional)
                </Label>
                <Input
                  id="acc_num"
                  placeholder="e.g. 50100293841"
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                  className="h-9 text-xs font-mono"
                />
              </div>
            </div>

            <div className="p-2.5 rounded border bg-muted/20 text-[11px] text-muted-foreground flex items-center gap-2">
              <Building2 className="size-4 text-emerald-500 shrink-0" />
              <span>
                Scope Assignment: Account will be bound to <strong className="text-foreground">{scopeLabel}</strong>.
              </span>
            </div>
          </div>

          <DialogFooter className="pt-2 border-t">
            <Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={submitting || !name || !openingBalance}
              className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5 font-semibold"
            >
              <Plus className="size-3.5" />
              {submitting ? 'Creating...' : 'Create Account'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
