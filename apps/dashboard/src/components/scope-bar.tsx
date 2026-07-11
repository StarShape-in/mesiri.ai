import { useQuery } from '@tanstack/react-query'
import { Building2, ChevronsUpDown, Globe, MapPin } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAllowedScopes, useScope } from '@/lib/ScopeContext'
import { fetchProjects, fetchSites } from '@/lib/projects'
import type { ProjectItem } from '@/lib/scope-types'

/** The one UI surface that communicates the current data context. It never
 * spells out "Portfolio Mode" / "Project Mode" / "Site Mode" — the current
 * scope is shown as a breadcrumb-style label instead. */
export function ScopeBar() {
  const { scope, setPortfolioScope, setProjectScope, setSiteScope } = useScope()
  const allowed = useAllowedScopes()

  const { data: projects } = useQuery({
    queryKey: ['scope-projects'],
    queryFn: fetchProjects,
    enabled: allowed.includes('project') || allowed.includes('site'),
    staleTime: 60_000,
  })

  const label =
    scope.mode === 'portfolio'
      ? 'All Projects'
      : scope.mode === 'project'
        ? scope.projectName
        : `${scope.projectName} / ${scope.siteName}`

  const Icon = scope.mode === 'portfolio' ? Globe : scope.mode === 'project' ? Building2 : MapPin

  if (allowed.length <= 1) {
    // Nothing to switch between — show context without a picker.
    return (
      <div className="flex items-center gap-2 text-sm font-medium">
        <Icon className="size-4 text-muted-foreground" />
        {label}
      </div>
    )
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Icon className="size-4 text-muted-foreground" />
          {label}
          <ChevronsUpDown className="size-3.5 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel>Switch scope</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {allowed.includes('portfolio') && (
          <DropdownMenuItem onSelect={setPortfolioScope}>
            <Globe />
            All Projects
          </DropdownMenuItem>
        )}
        {(projects ?? []).map((project) => (
          <ProjectMenuEntry
            key={project.id}
            project={project}
            allowSiteDrilldown={allowed.includes('site')}
            onSelectProject={() => setProjectScope(project)}
            onSelectSite={(site) => setSiteScope(project, site)}
          />
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ProjectMenuEntry({
  project,
  allowSiteDrilldown,
  onSelectProject,
  onSelectSite,
}: {
  project: ProjectItem
  allowSiteDrilldown: boolean
  onSelectProject: () => void
  onSelectSite: (site: { id: string; name: string; projectId: string }) => void
}) {
  const { data: sites } = useQuery({
    queryKey: ['scope-sites', project.id],
    queryFn: () => fetchSites(project.id),
    enabled: allowSiteDrilldown,
    staleTime: 60_000,
  })

  if (!allowSiteDrilldown) {
    return (
      <DropdownMenuItem onSelect={onSelectProject}>
        <Building2 />
        {project.name}
      </DropdownMenuItem>
    )
  }

  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <Building2 />
        {project.name}
      </DropdownMenuSubTrigger>
      <DropdownMenuSubContent>
        <DropdownMenuItem onSelect={onSelectProject}>All sites (project-wide)</DropdownMenuItem>
        <DropdownMenuSeparator />
        {(sites ?? []).map((site) => (
          <DropdownMenuItem key={site.id} onSelect={() => onSelectSite(site)}>
            <MapPin />
            {site.name}
          </DropdownMenuItem>
        ))}
      </DropdownMenuSubContent>
    </DropdownMenuSub>
  )
}
