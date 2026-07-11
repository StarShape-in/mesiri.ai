import { useScope } from '@/lib/ScopeContext'
import { ProjectOverview } from '@/components/project-overview'
import { PortfolioOverview } from '@/components/portfolio-overview'
import { SiteOverview } from '@/components/site-overview'

export default function Overview() {
  const { scope } = useScope()

  if (scope.mode === 'project') {
    return <ProjectOverview projectId={scope.projectId} />
  }

  if (scope.mode === 'site') {
    return <SiteOverview projectId={scope.projectId} siteId={scope.siteId} />
  }

  return <PortfolioOverview />
}
