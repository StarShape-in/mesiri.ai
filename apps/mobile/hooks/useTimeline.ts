import { useState, useEffect, useCallback, useRef } from 'react';
import { timelineService, TimelineEvent, TimelineDaySummary } from '../src/services/timelineService';

const PAGE_SIZE = 30;

export type UseTimelineParams = {
  projectId?: string;
  siteId?: string;
  dateFrom?: string;
  dateTo?: string;
};

// Plain useState/useEffect/useCallback (no React Query in this app — see
// hooks/useProjects.ts). Timeline is the first genuinely unbounded list in
// the app (portfolio-scope, all-time), so it paginates via offset + loadMore
// rather than the fixed-limit ScrollView.map() pattern materials lists use.
export function useTimeline({ projectId, siteId, dateFrom, dateTo }: UseTimelineParams) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [daySummaries, setDaySummaries] = useState<TimelineDaySummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [hasMore, setHasMore] = useState(true);

  // Avoids stale-closure races: loadMore reads the latest offset via a ref
  // rather than the `events.length` captured at callback-creation time.
  const offsetRef = useRef(0);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    offsetRef.current = 0;
    try {
      const [eventsRes, daySummaryRes] = await Promise.all([
        timelineService.getEvents({
          project_id: projectId,
          site_id: siteId,
          date_from: dateFrom,
          date_to: dateTo,
          limit: PAGE_SIZE,
          offset: 0,
        }),
        timelineService.getDaySummary({
          project_id: projectId,
          site_id: siteId,
          date_from: dateFrom,
          date_to: dateTo,
        }),
      ]);
      setEvents(eventsRes.items);
      setDaySummaries(daySummaryRes);
      setHasMore(eventsRes.items.length === PAGE_SIZE);
      offsetRef.current = eventsRes.items.length;
    } catch (err: any) {
      setError(err instanceof Error ? err : new Error('Failed to load timeline'));
    } finally {
      setIsLoading(false);
    }
  }, [projectId, siteId, dateFrom, dateTo]);

  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore || isLoading) {
      return;
    }
    setIsLoadingMore(true);
    try {
      const res = await timelineService.getEvents({
        project_id: projectId,
        site_id: siteId,
        date_from: dateFrom,
        date_to: dateTo,
        limit: PAGE_SIZE,
        offset: offsetRef.current,
      });
      setEvents((prev) => [...prev, ...res.items]);
      setHasMore(res.items.length === PAGE_SIZE);
      offsetRef.current += res.items.length;
    } catch (err: any) {
      setError(err instanceof Error ? err : new Error('Failed to load more timeline events'));
    } finally {
      setIsLoadingMore(false);
    }
  }, [projectId, siteId, dateFrom, dateTo, isLoadingMore, hasMore, isLoading]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { events, daySummaries, isLoading, isLoadingMore, error, refetch, loadMore, hasMore };
}
