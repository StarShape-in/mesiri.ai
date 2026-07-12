import * as React from 'react'
import { Check, ChevronsUpDown, Search } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface ComboboxOption {
  value: string
  label: string
}

interface ComboboxProps {
  options: ComboboxOption[]
  value: string
  onValueChange: (value: string) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  disabled?: boolean
  className?: string
}

export function Combobox({
  options,
  value,
  onValueChange,
  placeholder = 'Select option...',
  searchPlaceholder = 'Search...',
  emptyText = 'No options found.',
  disabled = false,
  className,
}: ComboboxProps) {
  const [open, setOpen] = React.useState(false)
  const [search, setSearch] = React.useState('')
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Close dropdown when clicking outside
  React.useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Clear search query when dropdown closes
  React.useEffect(() => {
    if (!open) {
      setSearch('')
    }
  }, [open])

  const filteredOptions = React.useMemo(() => {
    if (!search.trim()) return options
    const s = search.toLowerCase()
    return options.filter((o) => o.label.toLowerCase().includes(s))
  }, [options, search])

  const selectedOption = options.find((o) => o.value === value)

  return (
    <div ref={containerRef} className={cn('relative w-full', className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen(!open)}
        className={cn(
          'flex h-9 w-full items-center justify-between border border-input bg-transparent px-3 py-2 text-xs shadow-xs focus:outline-hidden focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50 text-left cursor-pointer rounded-md border-border/80 text-foreground',
          !value && 'text-muted-foreground'
        )}
      >
        <span className="truncate">{selectedOption ? selectedOption.label : placeholder}</span>
        <ChevronsUpDown className="h-4 w-4 opacity-50 shrink-0 ml-2" />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 max-h-60 w-full overflow-hidden border border-border bg-popover text-popover-foreground shadow-md rounded-md p-1 animate-in fade-in-0 duration-100">
          <div className="flex items-center border-b px-2 pb-1 pt-0.5">
            <Search className="h-3.5 w-3.5 opacity-50 shrink-0 mr-2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={searchPlaceholder}
              className="flex h-7 w-full rounded-md bg-transparent text-xs outline-hidden placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
              autoFocus
            />
          </div>
          <div className="overflow-y-auto max-h-[180px] p-1 space-y-0.5">
            {filteredOptions.length === 0 ? (
              <div className="py-3 text-center text-xs text-muted-foreground">{emptyText}</div>
            ) : (
              filteredOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => {
                    onValueChange(option.value)
                    setOpen(false)
                  }}
                  className={cn(
                    'relative flex w-full cursor-pointer select-none items-center py-1.5 pl-8 pr-2 text-xs outline-hidden rounded-sm text-left hover:bg-accent hover:text-accent-foreground',
                    option.value === value && 'bg-accent/50 font-semibold'
                  )}
                >
                  {option.value === value && (
                    <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                      <Check className="h-4 w-4" />
                    </span>
                  )}
                  <span className="truncate">{option.label}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
