import { api } from './api'

// Typed boundary for organization-wide (Portfolio Scope) operational reads.
// These call the existing /timeline endpoints with no project_id, which the
// backend already resolves to "every project the caller can see" — see
// backend/src/mesiri/domains/timeline/router.py::_resolve_project_ids.
// There is currently no dedicated /portfolio/overview aggregation endpoint;
// see the capability matrix in the Portfolio Overview PR description for
// the gaps (site counts, reporting coverage, DPR status, workforce/equipment/
// expenses aggregation) that would require one.

export interface FieldActivitySummaryItem {
  eventType: string
  count: number
}

/** Org-wide field-activity counts for today, grouped by event type. */
export async function fetchTodayFieldActivity(): Promise<FieldActivitySummaryItem[]> {
  const today = new Date().toISOString().slice(0, 10)
  const res = await api.get<{ items: Array<{ day: string; event_type: string; count: number }> }>(
    '/timeline/day-summary',
    { params: { date_from: today, date_to: today } }
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

/** Org-wide recent timeline entries (no project/site filter), newest first. */
export async function fetchPortfolioTimeline(limit = 50): Promise<PortfolioTimelineEntry[]> {
  const res = await api.get<{
    items: Array<{
      id: string
      project_id: string | null
      site_id: string | null
      event_type: string
      summary: string
      occurred_at: string
    }>
  }>('/timeline', { params: { limit } })
  return res.data.items.map((e) => ({
    id: e.id,
    projectId: e.project_id,
    siteId: e.site_id,
    eventType: e.event_type,
    summary: e.summary,
    occurredAt: e.occurred_at,
  }))
}
