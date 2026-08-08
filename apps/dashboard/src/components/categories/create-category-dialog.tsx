import * as React from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
import { createCategoryApi, updateCategoryApi, type CategoryItem } from '@/lib/api'

interface CreateCategoryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  categoryToEdit?: CategoryItem | null
  onSuccess: () => void
}

export function CreateCategoryDialog({
  open,
  onOpenChange,
  categoryToEdit,
  onSuccess,
}: CreateCategoryDialogProps) {
  const [name, setName] = React.useState('')
  const [code, setCode] = React.useState('')
  const [status, setStatus] = React.useState<'active' | 'inactive'>('active')
  const [submitting, setSubmitting] = React.useState(false)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    if (categoryToEdit) {
      setName(categoryToEdit.name || '')
      setCode(categoryToEdit.code || '')
      setStatus(categoryToEdit.status || 'active')
    } else {
      setName('')
      setCode('')
      setStatus('active')
    }
    setError('')
  }, [categoryToEdit, open])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Category name is required')
      return
    }

    setSubmitting(true)
    setError('')

    try {
      if (categoryToEdit) {
        await updateCategoryApi(categoryToEdit.id, {
          name: name.trim(),
          code: code.trim() || undefined,
          status,
        })
      } else {
        await createCategoryApi({
          name: name.trim(),
          code: code.trim() || undefined,
        })
      }
      onSuccess()
      onOpenChange(false)
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err.message || 'Failed to save category'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-base font-bold">
            {categoryToEdit ? 'Edit Expense Category' : 'Create New Expense Category'}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 py-2 text-xs">
          {error && (
            <div className="p-2.5 rounded-md bg-rose-500/10 border border-rose-500/20 text-rose-600 text-xs">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cat-name" className="text-xs font-semibold">
              Category Name <span className="text-rose-500">*</span>
            </Label>
            <Input
              id="cat-name"
              placeholder="e.g. Fuel & Transportation, Labor Wages..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 text-xs"
              required
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cat-code" className="text-xs font-semibold">
              Category Code / Short Tag (Optional)
            </Label>
            <Input
              id="cat-code"
              placeholder="e.g. FUEL, LABOR, MATS"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="h-9 text-xs font-mono uppercase"
            />
          </div>

          {categoryToEdit && (
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs font-semibold">Status</Label>
              <Select value={status} onValueChange={(val: any) => setStatus(val)}>
                <SelectTrigger className="h-9 text-xs">
                  <SelectValue placeholder="Select status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active" className="text-xs">
                    Active
                  </SelectItem>
                  <SelectItem value="inactive" className="text-xs">
                    Inactive
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
              className="h-8 text-xs"
            >
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={submitting} className="h-8 text-xs font-semibold">
              {submitting ? 'Saving...' : categoryToEdit ? 'Update Category' : 'Create Category'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
