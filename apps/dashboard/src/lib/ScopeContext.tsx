import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { allowedScopes } from './permissions'
import { fetchProjects, fetchSites } from './projects'
import type { AppScope, ProjectItem, SiteItem } from './scope-types'

// Mirrors apps/mobile/state/ScopeProvider.tsx's API (useScope, setPortfolioScope,
// setProjectScope, setSiteScope, isPortfolioMode/isProjectMode/isSiteMode),
// persisted to localStorage instead of expo-secure-store.
const SCOPE_STORAGE_KEY = 'mesiri_dashboard_scope'

type ScopeContextType = {
  scope: AppScope
  setPortfolioScope: () => void
  setProjectScope: (project: ProjectItem) => void
  setSiteScope: (project: ProjectItem, site: SiteItem) => void
  isPortfolioMode: boolean
  isProjectMode: boolean
  isSiteMode: boolean
}

const ScopeContext = createContext<ScopeContextType | null>(null)

export function useScope() {
  const context = useContext(ScopeContext)
  if (!context) {
    throw new Error('useScope must be used within a ScopeProvider')
  }
  return context
}

/** Single source of truth for which scopes the current user may reach — the
 * sidebar, scope bar, and route guards should all read from this rather than
 * re-deriving role/access_policy logic themselves. */
export function useAllowedScopes() {
  const { me } = useAuth()
  if (!me) return []
  return allowedScopes(me.role, me.access_policy)
}

function isScopeAllowed(scope: AppScope, allowed: ReturnType<typeof allowedScopes>): boolean {
  return allowed.includes(scope.mode)
}

export function ScopeProvider({ children }: { children: ReactNode }) {
  const { me } = useAuth()
  const allowed = useAllowedScopes()
  const [scope, setScopeState] = useState<AppScope>({ mode: 'portfolio' })

  useEffect(() => {
    if (!me) return
    let cancelled = false

    async function resolveInitialScope(): Promise<AppScope> {
      try {
        const stored = localStorage.getItem(SCOPE_STORAGE_KEY)
        if (stored) {
          const parsed = JSON.parse(stored) as AppScope
          if (isScopeAllowed(parsed, allowed)) return parsed
        }
      } catch {
        // ignore malformed persisted scope
      }

      if (allowed.includes('portfolio')) return { mode: 'portfolio' }

      // No portfolio access (Project Manager / Site Engineer / org-restricted
      // Finance): there is no valid "default" scope without a real project,
      // so fall back to the caller's first accessible project — and, for
      // site-only roles, its first accessible site.
      try {
        const projects = await fetchProjects()
        const project = projects[0]
        if (!project) return { mode: 'portfolio' }
        if (!allowed.includes('site')) {
          return { mode: 'project', projectId: project.id, projectName: project.name }
        }
        const sites = await fetchSites(project.id)
        const site = sites[0]
        if (!site) return { mode: 'project', projectId: project.id, projectName: project.name }
        return {
          mode: 'site',
          projectId: project.id,
          projectName: project.name,
          siteId: site.id,
          siteName: site.name,
        }
      } catch {
        return { mode: 'portfolio' }
      }
    }

    resolveInitialScope().then((initial) => {
      if (!cancelled) setScopeState(initial)
    })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.user_id])

  const setScope = (next: AppScope) => {
    setScopeState(next)
    try {
      localStorage.setItem(SCOPE_STORAGE_KEY, JSON.stringify(next))
    } catch {
      // ignore storage failures (private browsing, quota, etc.)
    }
  }

  const setPortfolioScope = () => setScope({ mode: 'portfolio' })

  const setProjectScope = (project: ProjectItem) =>
    setScope({ mode: 'project', projectId: project.id, projectName: project.name })

  const setSiteScope = (project: ProjectItem, site: SiteItem) =>
    setScope({
      mode: 'site',
      projectId: project.id,
      projectName: project.name,
      siteId: site.id,
      siteName: site.name,
    })

  return (
    <ScopeContext.Provider
      value={{
        scope,
        setPortfolioScope,
        setProjectScope,
        setSiteScope,
        isPortfolioMode: scope.mode === 'portfolio',
        isProjectMode: scope.mode === 'project',
        isSiteMode: scope.mode === 'site',
      }}
    >
      {children}
    </ScopeContext.Provider>
  )
}
