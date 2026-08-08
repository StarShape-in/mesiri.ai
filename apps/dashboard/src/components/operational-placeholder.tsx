import * as React from 'react'
import { Hammer, Landmark, DollarSign, Images, BarChart3, History, FileText } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useScope } from '@/lib/ScopeContext'

interface OperationalPlaceholderProps {
  title: string
  description?: string
}

const ICONS = {
  'Timeline': History,
  'Analytics': BarChart3,
  'Gallery': Images,
  'Reports': FileText,
  'Expenses': DollarSign,
  'Petty Cash': Landmark,
} as const

export function OperationalPlaceholder({ title, description }: OperationalPlaceholderProps) {
  const { scope } = useScope()
  const Icon = ICONS[title as keyof typeof ICONS] || Hammer

  const scopeLabel = React.useMemo(() => {
    if (scope.mode === 'portfolio') return 'Portfolio Scope (All Projects)'
    if (scope.mode === 'project') return `Project Scope: ${scope.projectName} (All Sites)`
    return `Site Scope: ${scope.projectName} / ${scope.siteName}`
  }, [scope])

  return (
    <div className="flex flex-col gap-4 text-sm max-w-4xl mx-auto py-8">
      <div className="flex items-center gap-3 border-b pb-4">
        <div className="size-10 rounded-full border border-primary/20 bg-primary/10 flex items-center justify-center text-primary shrink-0">
          <Icon className="size-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">{title}</h1>
          <p className="text-xs text-muted-foreground">
            {description || `Manage and view ${title.toLowerCase()} operational data.`}
          </p>
        </div>
      </div>

      <Card className="rounded-md border-border/70 shadow-xs overflow-hidden border-l-4 border-l-amber-500">
        <CardHeader className="pb-3 bg-amber-500/[0.02]">
          <CardTitle className="text-sm font-bold text-amber-600 dark:text-amber-400 flex items-center gap-2">
            <Hammer className="size-4 animate-pulse" />
            Feature Under Construction
          </CardTitle>
          <CardDescription className="text-xs">
            Active Scope Context: <strong className="text-foreground">{scopeLabel}</strong>
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4 text-sm text-muted-foreground leading-relaxed">
          The operational <strong className="text-foreground">{title}</strong> panel is currently undergoing database and API integration. 
          Your selected Project/Site scope parameters are fully preserved and will be automatically applied once the operational endpoints become active.
        </CardContent>
      </Card>
    </div>
  )
}
