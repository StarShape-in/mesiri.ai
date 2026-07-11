import { Hammer, MapPin } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useScope } from '@/lib/ScopeContext'
import { ProjectOverview } from '@/components/project-overview'
import { PortfolioOverview } from '@/components/portfolio-overview'

export default function Overview() {
  const { scope } = useScope()

  if (scope.mode === 'project') {
    return <ProjectOverview projectId={scope.projectId} />
  }

  if (scope.mode === 'site') {
    return <SiteOverviewPlaceholder />
  }

  return <PortfolioOverview />
}

function SiteOverviewPlaceholder() {
  const { scope } = useScope()
  return (
    <Card className="rounded-md border-border/70 border-l-4 border-l-sky-500 overflow-hidden">
      <CardHeader className="bg-sky-500/[0.02] pb-3">
        <CardTitle className="text-sm font-bold text-sky-600 dark:text-sky-400 flex items-center gap-2">
          <MapPin className="size-4 text-sky-500" />
          Site Overview
        </CardTitle>
        <CardDescription className="text-xs">
          Active Site Context: <strong className="text-foreground">{scope.mode === 'site' ? `${scope.projectName} / ${scope.siteName}` : ''}</strong>
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-4 text-xs text-muted-foreground leading-relaxed space-y-2">
        <p>
          The operational dashboard for individual Site scope is currently under construction.
        </p>
        <p className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 font-semibold bg-amber-500/5 px-2.5 py-1.5 rounded border border-amber-500/10 w-fit mt-2">
          <Hammer className="size-4 animate-pulse shrink-0" />
          Database schemas and daily report ingestion maps for this site are active. Full analytics integration is pending backend deployment.
        </p>
      </CardContent>
    </Card>
  )
}
