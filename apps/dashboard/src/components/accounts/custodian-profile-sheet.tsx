import * as React from 'react'
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
import { User, Landmark, ChevronLeft, Phone, Mail } from 'lucide-react'
import { fetchUsers, fetchAccountsApi, type User as UserItem } from '@/lib/api'

interface CustodianProfileSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  custodianIdOrName: string | null
  onOpenAccount?: (accountId: string) => void
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

export function CustodianProfileSheet({
  open,
  onOpenChange,
  custodianIdOrName,
  onOpenAccount,
  onBack,
  hasHistoryBack,
}: CustodianProfileSheetProps) {
  const [user, setUser] = React.useState<UserItem | null>(null)
  const [managedAccounts, setManagedAccounts] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    let active = true
    async function loadCustodianData() {
      if (!custodianIdOrName) return
      setLoading(true)
      try {
        const users = await fetchUsers()
        const found = users.find(
          (u) =>
            u.id === custodianIdOrName ||
            (u.full_name && u.full_name.toLowerCase() === custodianIdOrName.toLowerCase()) ||
            u.email.toLowerCase() === custodianIdOrName.toLowerCase()
        )
        if (active && found) setUser(found)

        const accs = await fetchAccountsApi()
        if (active && Array.isArray(accs)) {
          const matching = accs.filter(
            (a: any) =>
              a.owner_user_id === custodianIdOrName ||
              (found && a.owner_user_id === found.id) ||
              (a.custodian_name && a.custodian_name.toLowerCase().includes(custodianIdOrName.toLowerCase()))
          )
          setManagedAccounts(matching)
        }
      } catch (err) {
        console.warn('Failed to load custodian profile data:', err)
      } finally {
        if (active) setLoading(false)
      }
    }

    if (open) {
      loadCustodianData()
    }
    return () => {
      active = false
    }
  }, [open, custodianIdOrName])

  if (!custodianIdOrName) return null

  const displayName = user?.full_name || custodianIdOrName
  const displayRole = user?.role || 'Custodian / Manager'

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md w-full p-0 flex flex-col gap-0 bg-background overflow-hidden border-l">
        {/* Header */}
        <SheetHeader className="p-4 border-b bg-muted/30">
          <div className="flex items-center gap-2">
            {hasHistoryBack && onBack && (
              <Button
                size="icon"
                variant="ghost"
                className="size-7 text-muted-foreground hover:text-foreground"
                onClick={onBack}
              >
                <ChevronLeft className="size-4" />
              </Button>
            )}
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              <User className="size-4" />
            </div>
            <div>
              <SheetTitle className="text-sm font-bold text-foreground flex items-center gap-2">
                {displayName}
                <Badge variant="outline" className="text-[10px]">
                  {displayRole}
                </Badge>
              </SheetTitle>
              <SheetDescription className="text-[11px] text-muted-foreground">
                Money Account Custodian Profile
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        {/* Contact Info */}
        <div className="p-4 border-b bg-muted/10 space-y-1.5 text-xs">
          {user?.email && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Mail className="size-3.5 text-indigo-500" />
              <span className="font-mono">{user.email}</span>
            </div>
          )}
          {user?.whatsapp_number && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Phone className="size-3.5 text-emerald-500" />
              <span className="font-mono">{user.whatsapp_number}</span>
            </div>
          )}
        </div>

        {/* Managed Float Accounts List */}
        <div className="p-4 flex-1 overflow-y-auto space-y-3">
          <span className="text-xs font-bold text-foreground block">
            Assigned Money Accounts & Float Boxes ({managedAccounts.length})
          </span>

          {loading ? (
            <div className="p-8 text-center text-xs text-muted-foreground">Loading custodian accounts...</div>
          ) : managedAccounts.length === 0 ? (
            <Card className="p-4 border-dashed text-center text-xs text-muted-foreground">
              No money accounts currently assigned to {displayName}.
            </Card>
          ) : (
            <div className="space-y-2">
              {managedAccounts.map((acc: any) => (
                <Card
                  key={acc.id}
                  onClick={() => onOpenAccount?.(String(acc.id))}
                  className="p-3 border hover:border-emerald-500/50 cursor-pointer transition-all flex items-center justify-between group bg-card"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded bg-muted text-foreground">
                      <Landmark className="size-4" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-xs text-foreground group-hover:text-emerald-600 transition-colors">
                        {acc.name}
                      </h4>
                      <span className="text-[10px] text-muted-foreground capitalize">{acc.account_type}</span>
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="font-mono font-bold text-xs text-foreground block">
                      {formatCurrency(parseFloat(acc.current_balance || acc.opening_balance || 0))}
                    </span>
                    <Badge variant="outline" className="text-[9px] px-1 py-0">
                      Active
                    </Badge>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
