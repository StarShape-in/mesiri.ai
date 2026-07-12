import * as React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ShieldAlert, Plus } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import {
  fetchMaterials,
  fetchUnitsOfMeasure,
  createMaterial,
  updateMaterial,
  type MaterialCatalog,
} from '@/lib/materials'

interface ManageCatalogueDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

// Admin-only Materials Catalog management — a secondary action inside the
// Materials page (see MaterialsPage.tsx), not a top-level nav item: this is
// reference-data upkeep, not a daily operational surface like Inflows/
// Outflows/Inventory. A material's Stock Unit (default_unit_id) can't change
// once it has any recorded movement (backend PATCH /materials/{id} enforces
// this) -- the unit select is disabled for such rows rather than letting the
// user pick a value the save will just reject.
export function ManageCatalogueDialog({ open, onOpenChange }: ManageCatalogueDialogProps) {
  const queryClient = useQueryClient()

  const [name, setName] = React.useState('')
  const [unitId, setUnitId] = React.useState('')
  const [category, setCategory] = React.useState('')
  const [sku, setSku] = React.useState('')
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    if (open) {
      setName('')
      setUnitId('')
      setCategory('')
      setSku('')
      setError('')
    }
  }, [open])

  const { data: catalog } = useQuery({
    queryKey: ['materials', 'catalog', 'manage'],
    queryFn: () => fetchMaterials({ limit: 200 }),
    enabled: open,
    staleTime: 30_000,
  })

  const { data: units } = useQuery({
    queryKey: ['materials', 'units-of-measure'],
    queryFn: fetchUnitsOfMeasure,
    enabled: open,
    staleTime: 5 * 60_000,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      createMaterial({
        name: name.trim(),
        default_unit_id: unitId,
        category: category.trim() || undefined,
        sku: sku.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] })
      setName('')
      setUnitId('')
      setCategory('')
      setSku('')
      setError('')
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to add material.')
    },
  })

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      updateMaterial(id, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] })
    },
  })

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!name.trim()) {
      setError('Name is required.')
      return
    }
    if (!unitId) {
      setError('Stock Unit is required.')
      return
    }
    createMutation.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Manage Materials Catalog</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleAdd} className="space-y-3 py-2 text-xs border-b pb-4">
          {error && (
            <div className="bg-destructive/10 border border-destructive text-destructive p-2.5 rounded flex items-center gap-2">
              <ShieldAlert className="size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <div className="grid gap-3 sm:grid-cols-4">
            <div className="grid gap-1.5 sm:col-span-2">
              <Label htmlFor="newMaterialName">Name</Label>
              <Input
                id="newMaterialName"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. OPC Cement"
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Stock Unit</Label>
              <Select value={unitId} onValueChange={setUnitId}>
                <SelectTrigger className="h-9">
                  <SelectValue placeholder="Unit" />
                </SelectTrigger>
                <SelectContent>
                  {units?.items.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="newMaterialCategory">Category</Label>
              <Input
                id="newMaterialCategory"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="Optional"
              />
            </div>
          </div>
          <div className="grid gap-1.5 sm:w-1/2">
            <Label htmlFor="newMaterialSku">SKU</Label>
            <Input id="newMaterialSku" value={sku} onChange={(e) => setSku(e.target.value)} placeholder="Optional" />
          </div>
          <Button type="submit" size="sm" className="gap-1.5 text-xs font-bold" disabled={createMutation.isPending}>
            <Plus className="size-3.5" />
            {createMutation.isPending ? 'Adding...' : 'Add Material'}
          </Button>
        </form>

        <div className="pt-2">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Stock Unit</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {catalog?.items.map((m: MaterialCatalog) => (
                <TableRow key={m.id}>
                  <TableCell className="font-semibold">{m.name}</TableCell>
                  <TableCell>{m.default_unit ?? '—'}</TableCell>
                  <TableCell>{m.category ?? '—'}</TableCell>
                  <TableCell>
                    <button
                      type="button"
                      onClick={() =>
                        toggleActiveMutation.mutate({ id: m.id, isActive: !m.is_active })
                      }
                      disabled={toggleActiveMutation.isPending}
                    >
                      <Badge variant={m.is_active ? 'default' : 'outline'}>
                        {m.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </button>
                  </TableCell>
                </TableRow>
              ))}
              {catalog && catalog.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No materials yet — add one above.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  )
}
