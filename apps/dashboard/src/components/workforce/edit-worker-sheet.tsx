import * as React from 'react'
import { HardHat, Save, UserX, UserCheck } from 'lucide-react'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { updateWorkerApi, type WorkforceWorkerItem } from '@/lib/api'

interface EditWorkerSheetProps {
  worker: WorkforceWorkerItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

export function EditWorkerSheet({ worker, open, onOpenChange, onSuccess }: EditWorkerSheetProps) {
  const [name, setName] = React.useState('')
  const [trade, setTrade] = React.useState('')
  const [workerType, setWorkerType] = React.useState<'permanent' | 'temporary' | 'contractor'>('permanent')
  const [dailyWage, setDailyWage] = React.useState('')
  const [contractor, setContractor] = React.useState('')
  const [status, setStatus] = React.useState<'active' | 'inactive'>('active')

  const [saving, setSaving] = React.useState(false)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    if (worker) {
      setName(worker.name || '')
      setTrade(worker.trade || 'Mason')
      setWorkerType(worker.worker_type || 'permanent')
      setDailyWage(worker.default_daily_wage ? String(worker.default_daily_wage) : '')
      setContractor(worker.contractor || '')
      setStatus(worker.status || 'active')
    }
  }, [worker])

  if (!worker) return null

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Worker name is required.')
      return
    }

    setSaving(true)
    setError('')

    try {
      await updateWorkerApi(worker.id, {
        name: name.trim(),
        trade: trade.trim() || undefined,
        worker_type: workerType,
        default_daily_wage: dailyWage ? parseFloat(dailyWage) : undefined,
        contractor: contractor.trim() || undefined,
        status,
      })
      onSuccess()
      onOpenChange(false)
    } catch (err: any) {
      console.warn('Failed to update worker:', err)
      setError(err.response?.data?.detail || 'Failed to update worker profile.')
    } finally {
      setSaving(false)
    }
  }

  const handleToggleStatus = async () => {
    const nextStatus = status === 'active' ? 'inactive' : 'active'
    if (nextStatus === 'inactive') {
      if (!confirm(`Are you sure you want to retire ${worker.name}? They will no longer appear in active attendance pickers.`)) {
        return
      }
    }

    setSaving(true)
    try {
      await updateWorkerApi(worker.id, { status: nextStatus })
      setStatus(nextStatus)
      onSuccess()
    } catch (err: any) {
      console.warn('Failed to toggle worker status:', err)
      setError(err.response?.data?.detail || 'Failed to change worker status.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-[440px] flex flex-col justify-between">
        <div className="space-y-4">
          <SheetHeader className="pb-2 border-b">
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <div className="p-1.5 rounded-md bg-amber-500/10 border border-amber-500/20">
                <HardHat className="size-5" />
              </div>
              <div className="flex items-center gap-2">
                <SheetTitle className="text-base font-bold">Edit Worker Profile</SheetTitle>
                <Badge
                  variant="outline"
                  className={
                    status === 'active'
                      ? 'border-emerald-500/30 text-emerald-600 bg-emerald-500/10'
                      : 'border-slate-500/30 text-slate-500 bg-slate-500/10'
                  }
                >
                  {status.toUpperCase()}
                </Badge>
              </div>
            </div>
            <SheetDescription className="text-xs">
              Update site worker credentials, default daily wages, or change status.
            </SheetDescription>
          </SheetHeader>

          <form id="edit-worker-form" onSubmit={handleSave} className="space-y-3.5 text-xs py-2">
            {error && (
              <div className="p-2.5 rounded-md bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs">
                {error}
              </div>
            )}

            <div className="space-y-1">
              <Label htmlFor="edit-name" className="text-xs font-semibold">
                Worker Name
              </Label>
              <Input
                id="edit-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-9 text-xs"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="edit-trade" className="text-xs font-semibold">
                  Trade / Skill
                </Label>
                <Input
                  id="edit-trade"
                  value={trade}
                  onChange={(e) => setTrade(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="text-xs font-semibold">Worker Type</Label>
                <Select value={workerType} onValueChange={(val: any) => setWorkerType(val)}>
                  <SelectTrigger className="h-9 text-xs">
                    <SelectValue placeholder="Select Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="permanent" className="text-xs">Permanent Staff</SelectItem>
                    <SelectItem value="temporary" className="text-xs">Temporary Labor</SelectItem>
                    <SelectItem value="contractor" className="text-xs">Subcontractor</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="edit-dailyWage" className="text-xs font-semibold">
                  Default Daily Wage (₹)
                </Label>
                <Input
                  id="edit-dailyWage"
                  type="number"
                  value={dailyWage}
                  onChange={(e) => setDailyWage(e.target.value)}
                  className="h-9 text-xs font-mono"
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="edit-contractor" className="text-xs font-semibold">
                  Contractor / Agency
                </Label>
                <Input
                  id="edit-contractor"
                  value={contractor}
                  onChange={(e) => setContractor(e.target.value)}
                  className="h-9 text-xs"
                />
              </div>
            </div>
          </form>
        </div>

        <div className="space-y-3 pt-4 border-t">
          <div className="flex items-center justify-between">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleToggleStatus}
              disabled={saving}
              className={
                status === 'active'
                  ? 'text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/20 text-xs'
                  : 'text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/20 text-xs'
              }
            >
              {status === 'active' ? (
                <>
                  <UserX className="size-3.5 mr-1.5" /> Retire Worker
                </>
              ) : (
                <>
                  <UserCheck className="size-3.5 mr-1.5" /> Reactivate Worker
                </>
              )}
            </Button>

            <Button
              form="edit-worker-form"
              type="submit"
              size="sm"
              disabled={saving}
              className="bg-amber-600 hover:bg-amber-700 text-white font-bold gap-1.5"
            >
              <Save className="size-3.5" />
              {saving ? 'Saving...' : 'Save Profile'}
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
