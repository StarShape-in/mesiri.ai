import * as React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ChevronDown, CircleSlash2, ShieldAlert, Plus, Pencil, Trash2, X } from 'lucide-react'
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  fetchMaterials,
  fetchUnitsOfMeasure,
  createMaterial,
  deleteMaterial,
  updateMaterial,
  type MaterialCatalog,
} from '@/lib/materials'
import { BulkActionBar } from '@/components/ui/bulk-action-bar'

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

  const [editingMaterial, setEditingMaterial] = React.useState<MaterialCatalog | null>(null)
  const [name, setName] = React.useState('')
  const [unitId, setUnitId] = React.useState('')
  const [category, setCategory] = React.useState('')
  const [sku, setSku] = React.useState('')
  const [error, setError] = React.useState('')
  const [selectedIds, setSelectedIds] = React.useState<string[]>([])

  React.useEffect(() => {
    if (open) {
      setEditingMaterial(null)
      setName('')
      setUnitId('')
      setCategory('')
      setSku('')
      setError('')
      setSelectedIds([])
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

  const updateMutation = useMutation({
    mutationFn: () =>
      updateMaterial(editingMaterial!.id, {
        name: name.trim(),
        default_unit_id: unitId,
        category: category.trim() || undefined,
        sku: sku.trim() || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] })
      setEditingMaterial(null)
      setName('')
      setUnitId('')
      setCategory('')
      setSku('')
      setError('')
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to update material.')
    },
  })

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      updateMaterial(id, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteMaterial,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] })
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to delete material.')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
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
    if (editingMaterial) {
      updateMutation.mutate()
    } else {
      createMutation.mutate()
    }
  }

  const handleEditClick = (m: MaterialCatalog) => {
    setEditingMaterial(m)
    setName(m.name)
    setUnitId(m.default_unit_id)
    setCategory(m.category ?? '')
    setSku(m.sku ?? '')
    setError('')
  }

  const handleCancelEdit = () => {
    setEditingMaterial(null)
    setName('')
    setUnitId('')
    setCategory('')
    setSku('')
    setError('')
  }

  // Row selection helpers
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds((catalog?.items ?? []).map((m) => m.id))
    } else {
      setSelectedIds([])
    }
  }

  const handleSelectRow = (id: string, checked: boolean) => {
    if (checked) {
      setSelectedIds((prev) => [...prev, id])
    } else {
      setSelectedIds((prev) => prev.filter((item) => item !== id))
    }
  }

  const handleBulkStatus = async (isActive: boolean) => {
    const actionLabel = isActive ? 'activate' : 'deactivate'
    if (confirm(`Are you sure you want to ${actionLabel} ${selectedIds.length} selected materials?`)) {
      setError('')
      try {
        for (const id of selectedIds) {
          await toggleActiveMutation.mutateAsync({ id, isActive })
        }
        setSelectedIds([])
      } catch (err: any) {
        setError(err.response?.data?.detail || `Failed to bulk ${actionLabel} materials.`)
      }
    }
  }

  const handleDelete = async (material: MaterialCatalog) => {
    if (
      confirm(
        `Delete "${material.name}" from the materials catalog? This only works for materials with no recorded movements.`
      )
    ) {
      setError('')
      try {
        await deleteMutation.mutateAsync(material.id)
      } catch {
        // React Query onError already surfaces the API message in the dialog.
      }
    }
  }

  const handleBulkDelete = async () => {
    if (
      confirm(
        `Delete ${selectedIds.length} selected materials? Materials with recorded movements must be deactivated instead.`
      )
    ) {
      setError('')
      try {
        for (const id of selectedIds) {
          await deleteMutation.mutateAsync(id)
        }
        setSelectedIds([])
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to delete selected materials.')
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            Manage Materials Catalog
            {editingMaterial && (
              <span className="text-xs font-normal text-muted-foreground ml-2">
                (Editing: {editingMaterial.name})
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3 py-2 text-xs border-b pb-4">
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
          <div className="flex gap-2">
            <Button
              type="submit"
              size="sm"
              className="gap-1.5 text-xs font-bold"
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {editingMaterial ? (
                <>
                  <Pencil className="size-3.5" />
                  {updateMutation.isPending ? 'Updating...' : 'Update Material'}
                </>
              ) : (
                <>
                  <Plus className="size-3.5" />
                  {createMutation.isPending ? 'Adding...' : 'Add Material'}
                </>
              )}
            </Button>
            {editingMaterial && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-1.5 text-xs font-bold"
                onClick={handleCancelEdit}
              >
                <X className="size-3.5" />
                Cancel Edit
              </Button>
            )}
          </div>
        </form>

        <div className="pt-2">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12 px-4">
                  <input
                    type="checkbox"
                    checked={catalog && catalog.items.length > 0 && selectedIds.length === catalog.items.length}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    className="rounded border-border/80 text-primary focus:ring-primary size-4"
                  />
                </TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Stock Unit</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {catalog?.items.map((m: MaterialCatalog) => {
                const isSelected = selectedIds.includes(m.id)
                return (
                  <TableRow key={m.id} data-state={isSelected ? 'selected' : undefined}>
                    <TableCell className="px-4">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => handleSelectRow(m.id, e.target.checked)}
                        className="rounded border-border/80 text-primary focus:ring-primary size-4"
                      />
                    </TableCell>
                    <TableCell className="font-semibold">{m.name}</TableCell>
                    <TableCell>
                      {units?.items.find((u) => u.id === m.default_unit_id)?.display_name ?? m.default_unit ?? '—'}
                    </TableCell>
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
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button type="button" variant="ghost" size="icon" className="size-7 hover:bg-muted">
                            <ChevronDown className="size-3.5 text-muted-foreground" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-44">
                          <DropdownMenuItem onClick={() => handleEditClick(m)}>
                            <Pencil className="size-3.5 mr-2" />
                            Edit Material
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              toggleActiveMutation.mutate({ id: m.id, isActive: !m.is_active })
                            }
                          >
                            {m.is_active ? (
                              <>
                                <CircleSlash2 className="size-3.5 mr-2 text-rose-500" />
                                Deactivate
                              </>
                            ) : (
                              <>
                                <CheckCircle2 className="size-3.5 mr-2 text-emerald-500" />
                                Activate
                              </>
                            )}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => handleDelete(m)}
                            className="text-destructive hover:bg-destructive/10"
                          >
                            <Trash2 className="size-3.5 mr-2" />
                            Delete Material
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                )
              })}
              {catalog && catalog.items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No materials yet — add one above.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        <BulkActionBar selectedCount={selectedIds.length} onClear={() => setSelectedIds([])} className="z-[100]">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleBulkStatus(true)}
            className="h-8 text-xs text-emerald-600 dark:text-emerald-400 gap-1 font-bold"
          >
            <CheckCircle2 className="size-3.5" />
            Activate Selected
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleBulkStatus(false)}
            className="h-8 text-xs text-rose-600 dark:text-rose-400 gap-1 font-bold"
          >
            <CircleSlash2 className="size-3.5" />
            Deactivate Selected
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleBulkDelete}
            className="h-8 text-xs text-destructive hover:bg-destructive/10 gap-1 font-bold"
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="size-3.5" />
            Delete Selected
          </Button>
        </BulkActionBar>
      </DialogContent>
    </Dialog>
  )
}
