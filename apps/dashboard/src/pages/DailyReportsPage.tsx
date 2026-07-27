import * as React from 'react'
import { useSearchParams } from 'react-router-dom'
import { FileText, Hammer, AlertCircle } from 'lucide-react'
import { useScope } from '@/lib/ScopeContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

const CATEGORIES = [
  { value: 'all', label: 'All Categories' },
  { value: 'work-progress', label: 'Work Progress' },
  { value: 'workforce', label: 'Workforce (Labour)' },
  { value: 'equipment', label: 'Equipment & Machinery' },
  { value: 'material-in', label: 'Material In' },
  { value: 'material-out', label: 'Material Out' },
  { value: 'fuel', label: 'Fuel Usage' },
  { value: 'issues-delays', label: 'Issues & Delays' },
  { value: 'safety', label: 'Safety Reports' },
  { value: 'general', label: 'General Updates' },
]

export default function DailyReportsPage() {
  const { scope } = useScope()
  const [searchParams, setSearchParams] = useSearchParams()
  
  const activeType = searchParams.get('type') || 'all'

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Projects)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName}`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  const activeCategoryLabel = React.useMemo(() => {
    const match = CATEGORIES.find((c) => c.value === activeType)
    return match ? match.label : 'Daily Reports'
  }, [activeType])

  const selectCategory = (type: string) => {
    setSearchParams((prev) => {
      if (type === 'all') {
        prev.delete('type')
      } else {
        prev.set('type', type)
      }
      return prev
    })
  }

  return (
    <div className="flex flex-col gap-4 text-sm max-w-6xl mx-auto">
      {/* Header section */}
      <div className="flex flex-col gap-1 border-b pb-4">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-full border border-primary/20 bg-primary/10 flex items-center justify-center text-primary shrink-0">
            <FileText className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">Daily Reports</h1>
            <p className="text-xs text-muted-foreground">
              Monitor operational daily reports across active sites.
            </p>
          </div>
        </div>
      </div>

      {/* Categories Horizontal Navigation */}
      <div className="flex border-b border-border/60 gap-4 text-xs font-semibold text-muted-foreground overflow-x-auto pb-1 scrollbar-none">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => selectCategory(cat.value)}
            className={`pb-2 border-b-2 transition-all whitespace-nowrap cursor-pointer ${
              activeType === cat.value
                ? 'border-primary text-foreground font-bold'
                : 'border-transparent hover:text-foreground'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Main Content Area */}
      <div className="grid gap-4 md:grid-cols-4 pt-2">
        {/* Left Side Info Panel */}
        <Card className="rounded-md border-border/70 shadow-xs md:col-span-1 bg-muted/10 h-fit">
          <CardHeader className="pb-3 border-b">
            <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground font-bold">
              Active Context
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4 space-y-3 text-xs">
            <div>
              <span className="text-muted-foreground block font-medium">Selected Scope</span>
              <span className="font-semibold text-foreground">{scopeLabel}</span>
            </div>
            <div>
              <span className="text-muted-foreground block font-medium">Active Filter</span>
              <Badge variant="outline" className="mt-1 font-semibold border-primary/30 text-primary bg-primary/5">
                {activeCategoryLabel}
              </Badge>
            </div>
          </CardContent>
        </Card>

        {/* Right Side Records Area */}
        <Card className="rounded-md border-border/70 shadow-xs md:col-span-3 flex flex-col justify-between overflow-hidden">
          <div>
            <CardHeader className="pb-3 border-b border-l-3 border-l-amber-500 bg-amber-500/[0.01]">
              <CardTitle className="text-xs uppercase tracking-wider text-amber-600 dark:text-amber-400 font-bold flex items-center gap-2">
                <Hammer className="size-4 animate-pulse" />
                Operational Daily Reports Area
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-8 pb-12 flex flex-col items-center justify-center text-center gap-3">
              <AlertCircle className="size-8 text-muted-foreground/60" />
              <h3 className="text-sm font-semibold text-foreground">No Records Found</h3>
              <p className="text-xs text-muted-foreground max-w-sm leading-relaxed">
                There are no active records in database for <strong className="text-foreground">{activeCategoryLabel}</strong> under this scope. 
                Daily report submission APIs for this category are pending backend deployment.
              </p>
            </CardContent>
          </div>
        </Card>
      </div>
    </div>
  )
}
