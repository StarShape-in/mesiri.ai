import * as React from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface BulkActionBarProps {
  selectedCount: number
  onClear: () => void
  children: React.ReactNode
  className?: string
}

export function BulkActionBar({ selectedCount, onClear, children, className }: BulkActionBarProps) {
  if (selectedCount === 0) return null

  return (
    <div className={cn("fixed bottom-4 left-[50%] translate-x-[-50%] z-40 flex items-center gap-3 bg-card border border-border shadow-xl px-4 py-2.5 rounded-lg text-sm animate-in fade-in slide-in-from-bottom-2 duration-200", className)}>
      <span className="font-mono text-xs font-semibold bg-muted px-2 py-0.5 rounded text-muted-foreground">
        {selectedCount} Selected
      </span>
      <div className="h-4 w-px bg-border" />
      <div className="flex gap-2 items-center">{children}</div>
      <div className="h-4 w-px bg-border" />
      <Button variant="ghost" size="sm" onClick={onClear} className="size-8 p-0">
        <X className="size-4" />
      </Button>
    </div>
  )
}
