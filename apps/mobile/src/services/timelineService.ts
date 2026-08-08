import { api } from '@mesiri/auth';

export interface TimelineEvent {
  id: string;
  organizationId: string;
  projectId: string | null;
  siteId: string | null;
  eventType: string;
  summary: string;
  payload: Record<string, any>;
  occurredAt: string;
  correlationId: string | null;
  sourceAggregateType: string;
  sourceAggregateId: string;
  createdAt: string;
}

export interface TimelineDaySummary {
  day: string;
  eventType: string;
  count: number;
}

export interface TimelineQueryParams {
  project_id?: string;
  site_id?: string;
  event_type?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface TimelineDaySummaryQueryParams {
  project_id?: string;
  site_id?: string;
  date_from?: string;
  date_to?: string;
}

export const timelineService = {
  async getEvents(params: TimelineQueryParams): Promise<{ items: TimelineEvent[]; total: number }> {
    const { data } = await api.get('/timeline', { params });
    const items = (data.items || []).map((item: any) => ({
      id: item.id,
      organizationId: item.organization_id,
      projectId: item.project_id,
      siteId: item.site_id,
      eventType: item.event_type,
      summary: item.summary,
      payload: item.payload,
      occurredAt: item.occurred_at,
      correlationId: item.correlation_id,
      sourceAggregateType: item.source_aggregate_type,
      sourceAggregateId: item.source_aggregate_id,
      createdAt: item.created_at,
    }));
    return { items, total: data.total || 0 };
  },

  async getDaySummary(params: TimelineDaySummaryQueryParams): Promise<TimelineDaySummary[]> {
    const { data } = await api.get('/timeline/day-summary', { params });
    return (data.items || []).map((item: any) => ({
      day: item.day,
      eventType: item.event_type,
      count: Number(item.count),
    }));
  },
};
