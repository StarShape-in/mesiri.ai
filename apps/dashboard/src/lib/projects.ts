import { api } from './api'
import type { ProjectItem, SiteItem } from './scope-types'

export async function fetchProjects(): Promise<ProjectItem[]> {
  const res = await api.get<Array<{ id: string; name: string }>>('/projects')
  return res.data.map((p) => ({ id: p.id, name: p.name }))
}

export async function fetchSites(projectId: string): Promise<SiteItem[]> {
  const res = await api.get<Array<{ id: string; name: string; project_id: string }>>(
    `/projects/${projectId}/sites`
  )
  return res.data.map((s) => ({ id: s.id, name: s.name, projectId: s.project_id }))
}
