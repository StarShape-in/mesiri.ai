import { api } from './api'

// Typed boundary for organization-wide and scoped (Project/Site) operational
// timeline reads. These call the existing /timeline endpoints — the backend
// already resolves an omitted project_id to "every project the caller can
// see" (see backend/src/mesiri/domains/timeline/router.py::_resolve_project_ids)
// and accepts an optional site_id to narrow further to one Site. There is no
// dedicated /portfolio/overview or /sites/{id}/overview aggregation endpoint;
// see the capability matrices in the Portfolio/Site Overview PR descriptions
// for the gaps (site counts, reporting coverage, DPR status, workforce/
// equipment/expenses aggregation) that would require one.

export interface TimelineScopeFilter {
  projectId?: string
  siteId?: string
}

export interface FieldActivitySummaryItem {
  eventType: string
  count: number
}

/** Field-activity counts for today, grouped by event type, within scope. */
export async function fetchTodayFieldActivity(
  scope: TimelineScopeFilter = {}
): Promise<FieldActivitySummaryItem[]> {
  const today = new Date().toISOString().slice(0, 10)
  const res = await api.get<{ items: Array<{ day: string; event_type: string; count: number }> }>(
    '/timeline/day-summary',
    {
      params: {
        date_from: today,
        date_to: today,
        project_id: scope.projectId,
        site_id: scope.siteId,
      },
    }
  )
  const totals = new Map<string, number>()
  for (const item of res.data.items) {
    totals.set(item.event_type, (totals.get(item.event_type) ?? 0) + item.count)
  }
  return Array.from(totals, ([eventType, count]) => ({ eventType, count }))
}

export interface PortfolioTimelineEntry {
  id: string
  projectId: string | null
  siteId: string | null
  eventType: string
  summary: string
  occurredAt: string
}

/** Recent timeline entries within scope (no filter = org-wide), newest first. */
export async function fetchPortfolioTimeline(
  limit = 50,
  scope: TimelineScopeFilter = {}
): Promise<PortfolioTimelineEntry[]> {
  const res = await api.get<{
    items: Array<{
      id: string
      project_id: string | null
      site_id: string | null
      event_type: string
      summary: string
      occurred_at: string
    }>
  }>('/timeline', {
    params: { limit, project_id: scope.projectId, site_id: scope.siteId },
  })
  return res.data.items.map((e) => ({
    id: e.id,
    projectId: e.project_id,
    siteId: e.site_id,
    eventType: e.event_type,
    summary: e.summary,
    occurredAt: e.occurred_at,
  }))
}
