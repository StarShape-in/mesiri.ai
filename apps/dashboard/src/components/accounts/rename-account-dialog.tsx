import * as React from 'react'
import { Pencil } from 'lucide-react'
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

interface RenameAccountDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  accountId: string | null
  currentName: string
  onRenamed?: (accountId: string, newName: string) => void
}

import { renameAccountApi } from '@/lib/api'

export function RenameAccountDialog({
  open,
  onOpenChange,
  accountId,
  currentName,
  onRenamed,
}: RenameAccountDialogProps) {
  const [name, setName] = React.useState(currentName)
  const [submitting, setSubmitting] = React.useState(false)

  React.useEffect(() => {
    if (open) setName(currentName)
  }, [open, currentName])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!accountId || !trimmed) return

    setSubmitting(true)
    try {
      await renameAccountApi(accountId, trimmed)
      onRenamed?.(accountId, trimmed)
      onOpenChange(false)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      const msg = Array.isArray(detail) ? detail.join(', ') : detail || err.message || 'Rename failed'
      alert(`Rename account failed: ${msg}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[420px] gap-4">
        <form onSubmit={handleSubmit}>
          <DialogHeader className="pb-2 border-b">
            <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400">
              <div className="p-1.5 rounded-md bg-indigo-500/10 border border-indigo-500/20">
                <Pencil className="size-4" />
              </div>
              <DialogTitle className="text-base font-bold">Rename Account</DialogTitle>
            </div>
            <DialogDescription className="text-xs">
              Update the display name for this money account.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 py-4 text-xs">
            <div className="space-y-1.5">
              <Label htmlFor="acc_name" className="text-xs font-semibold">
                Account Name *
              </Label>
              <Input
                id="acc_name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-9 text-xs"
                required
                autoFocus
              />
            </div>
          </div>

          <DialogFooter className="pt-2 border-t">
            <Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={submitting || !name.trim()}
              className="bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5 font-semibold"
            >
              <Pencil className="size-3.5" />
              {submitting ? 'Saving...' : 'Save Name'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
