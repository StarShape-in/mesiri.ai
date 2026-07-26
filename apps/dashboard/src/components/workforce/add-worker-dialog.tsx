import * as React from 'react'
import { HardHat, UserPlus } from 'lucide-react'
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
import { createWorkerApi, type CreateWorkerPayload } from '@/lib/api'

interface AddWorkerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

const COMMON_TRADES = [
  'Mason',
  'Helper',
  'Carpenter',
  'Electrician',
  'Plumber',
  'Steel Fixer',
  'Welder',
  'Painter',
  'Equipment Operator',
  'Supervisor',
]

export function AddWorkerDialog({ open, onOpenChange, onSuccess }: AddWorkerDialogProps) {
  const [name, setName] = React.useState('')
  const [trade, setTrade] = React.useState('Mason')
  const [workerType, setWorkerType] = React.useState<'permanent' | 'temporary' | 'contractor'>('permanent')
  const [dailyWage, setDailyWage] = React.useState('800')
  const [contractor, setContractor] = React.useState('')

  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Worker name is required.')
      return
    }

    setSubmitting(true)
    setError('')

    try {
      const payload: CreateWorkerPayload = {
        name: name.trim(),
        trade: trade.trim() || undefined,
        worker_type: workerType,
        default_daily_wage: dailyWage ? parseFloat(dailyWage) : undefined,
        contractor: contractor.trim() || undefined,
        status: 'active',
      }
      await createWorkerApi(payload)
      onSuccess()
      onOpenChange(false)
      setName('')
      setTrade('Mason')
      setWorkerType('permanent')
      setDailyWage('800')
      setContractor('')
    } catch (err: any) {
      console.warn('Failed to create worker:', err)
      setError(err.response?.data?.detail || 'Failed to register worker.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
            <div className="p-1.5 rounded-md bg-amber-500/10 border border-amber-500/20">
              <HardHat className="size-5" />
            </div>
            <DialogTitle className="text-base font-bold">Register Site Worker</DialogTitle>
          </div>
          <DialogDescription className="text-xs">
            Add a new worker to the organization roster for attendance tracking and daily wage calculation.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs py-2">
          {error && (
            <div className="p-2.5 rounded-md bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-xs">
              {error}
            </div>
          )}

          <div className="space-y-1">
            <Label htmlFor="name" className="text-xs font-semibold">
              Worker Full Name <span className="text-red-500">*</span>
            </Label>
            <Input
              id="name"
              placeholder="e.g. Ramesh Kumar"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 text-xs"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="trade" className="text-xs font-semibold">
                Trade / Skill
              </Label>
              <select
                id="trade"
                value={trade}
                onChange={(e) => setTrade(e.target.value)}
                className="w-full h-9 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-sans ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {COMMON_TRADES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="workerType" className="text-xs font-semibold">
                Worker Type
              </Label>
              <select
                id="workerType"
                value={workerType}
                onChange={(e) => setWorkerType(e.target.value as any)}
                className="w-full h-9 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-sans ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="permanent">Permanent Staff</option>
                <option value="temporary">Temporary Labor</option>
                <option value="contractor">Subcontractor</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="dailyWage" className="text-xs font-semibold">
                Default Daily Wage (₹)
              </Label>
              <Input
                id="dailyWage"
                type="number"
                placeholder="800"
                value={dailyWage}
                onChange={(e) => setDailyWage(e.target.value)}
                className="h-9 text-xs font-mono"
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="contractor" className="text-xs font-semibold">
                Contractor / Agency Name
              </Label>
              <Input
                id="contractor"
                placeholder="e.g. Metro Builders Ltd"
                value={contractor}
                onChange={(e) => setContractor(e.target.value)}
                className="h-9 text-xs"
              />
            </div>
          </div>

          <DialogFooter className="pt-3 border-t">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={submitting}
              className="bg-amber-600 hover:bg-amber-700 text-white font-bold gap-1.5"
            >
              <UserPlus className="size-3.5" />
              {submitting ? 'Registering...' : 'Register Worker'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
