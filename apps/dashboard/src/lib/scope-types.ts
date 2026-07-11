// Mirrors apps/mobile/components/scope/scope.types.ts — keep the shape and
// naming in sync across web/mobile. "Scope" is the data context (Portfolio /
// Project / Site), never called "Mode" in code or UI copy.
export type AppScope =
  | {
      mode: 'portfolio'
    }
  | {
      mode: 'project'
      projectId: string
      projectName: string
    }
  | {
      mode: 'site'
      projectId: string
      projectName: string
      siteId: string
      siteName: string
    }

export type ScopeKind = AppScope['mode']

export type ProjectItem = {
  id: string
  name: string
}

export type SiteItem = {
  id: string
  name: string
  projectId: string
}
