import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { View, Text, StyleSheet, SectionList, RefreshControl, ActivityIndicator } from 'react-native';
import { Clock, AlertCircle } from 'lucide-react-native';
import { api } from '@mesiri/auth';
import { useScope } from '../../state/ScopeProvider';
import { useStyles, useTheme } from '../../src/theme';
import { useProjects } from '../../hooks/useProjects';
import { useTimeline } from '../../hooks/useTimeline';
import { EmptyState } from '../ui/EmptyState';
import { TimelineEvent } from '../../src/services/timelineService';
import { FILTER_CHIPS } from '../../src/config/timelineCategories';
import { TimelineFilterChips } from '../features/timeline/TimelineFilterChips';
import { TimelineGranularitySwitcher, TimelineGranularity } from '../features/timeline/TimelineGranularitySwitcher';
import { TimelineDayHeader } from '../features/timeline/TimelineDayHeader';
import { TimelineEventCard } from '../features/timeline/TimelineEventCard';
import { TimelineEventDetailSheet } from '../features/timeline/TimelineEventDetailSheet';

// A stable color per project/site id for the scope-aware chip (portfolio ->
// project chip, project scope -> site chip). Hashes the id into one of the
// dataviz-safe categorical ramps already used elsewhere in the design.
const CHIP_COLORS = ['#378ADD', '#D4537E', '#639922', '#BA7517', '#7F77DD', '#1D9E75'];
function colorForId(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return CHIP_COLORS[hash % CHIP_COLORS.length];
}

function bucketKey(occurredAt: string, granularity: TimelineGranularity): string {
  const d = new Date(occurredAt);
  if (granularity === 'day') {
    return d.toISOString().slice(0, 10);
  }
  if (granularity === 'month') {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  }
  // week: Monday-anchored start of week
  const day = d.getDay();
  const diff = (day === 0 ? -6 : 1) - day;
  const monday = new Date(d);
  monday.setDate(d.getDate() + diff);
  return monday.toISOString().slice(0, 10);
}

function bucketLabel(key: string, granularity: TimelineGranularity): { label: string; dateText: string } {
  const today = new Date();
  const todayKey = bucketKey(today.toISOString(), granularity);

  if (granularity === 'month') {
    const [year, month] = key.split('-').map(Number);
    const d = new Date(year, month - 1, 1);
    return { label: d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }), dateText: '' };
  }

  const d = new Date(key);
  const dateText = d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' });

  if (granularity === 'day') {
    if (key === todayKey) return { label: 'Today', dateText };
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    if (key === bucketKey(yesterday.toISOString(), granularity)) return { label: 'Yesterday', dateText };
    return { label: dateText, dateText: '' };
  }

  // week
  const end = new Date(d);
  end.setDate(d.getDate() + 6);
  const endText = end.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  return { label: `${dateText} – ${endText}`, dateText: '' };
}

const EVENT_LABEL_PLURAL: Record<string, string> = {
  MaterialReceived: 'received',
  MaterialUsed: 'used',
};

export function TimelineScreen() {
  const { scope } = useScope();
  const styles = useStyles(createStyles);
  const { theme } = useTheme();
  const { projects } = useProjects();

  const [filterKey, setFilterKey] = useState('all');
  const [granularity, setGranularity] = useState<TimelineGranularity>('day');
  const [siteNamesById, setSiteNamesById] = useState<Record<string, string>>({});
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const projectId = scope.mode !== 'portfolio' ? scope.projectId : undefined;
  const siteId = scope.mode === 'site' ? scope.siteId : undefined;

  const { events, daySummaries, isLoading, isLoadingMore, error, refetch, loadMore, hasMore } = useTimeline({
    projectId,
    siteId,
  });

  // Fetch this project's sites once (for the project-scope site chip),
  // mirroring FieldMaterialsScreen's own site lookup for its form.
  useEffect(() => {
    let active = true;
    if (scope.mode === 'project' && scope.projectId) {
      api
        .get(`/projects/${scope.projectId}/sites`)
        .then((res) => {
          if (!active) return;
          const map: Record<string, string> = {};
          (res.data || []).forEach((s: any) => {
            map[s.id] = s.name;
          });
          setSiteNamesById(map);
        })
        .catch(() => {
          if (active) setSiteNamesById({});
        });
    } else {
      setSiteNamesById({});
    }
    return () => {
      active = false;
    };
  }, [scope.mode, scope.mode === 'project' ? scope.projectId : undefined]);

  const projectNamesById = useMemo(() => {
    const map: Record<string, string> = {};
    projects.forEach((p) => {
      map[p.id] = p.name;
    });
    return map;
  }, [projects]);

  const scopeText =
    scope.mode === 'portfolio'
      ? 'All projects portfolio'
      : scope.mode === 'project'
      ? scope.projectName
      : `${scope.projectName} • ${scope.siteName}`;

  const activeEventTypes = FILTER_CHIPS.find((c) => c.key === filterKey)?.eventTypes ?? null;

  const filteredEvents = useMemo(() => {
    if (!activeEventTypes) return events;
    return events.filter((e) => activeEventTypes.includes(e.eventType));
  }, [events, activeEventTypes]);

  const sections = useMemo(() => {
    const byKey = new Map<string, TimelineEvent[]>();
    for (const event of filteredEvents) {
      const key = bucketKey(event.occurredAt, granularity);
      if (!byKey.has(key)) byKey.set(key, []);
      byKey.get(key)!.push(event);
    }
    const keys = Array.from(byKey.keys()).sort().reverse();
    return keys.map((key) => {
      const { label, dateText } = bucketLabel(key, granularity);
      const bucketEvents = byKey.get(key)!;

      let summaryText = '';
      if (granularity === 'day') {
        const forDay = daySummaries.filter((s) => s.day === key);
        summaryText = forDay
          .map((s) => `${s.count} ${EVENT_LABEL_PLURAL[s.eventType] ?? s.eventType}`)
          .join(' · ');
      } else {
        const counts: Record<string, number> = {};
        bucketEvents.forEach((e) => {
          counts[e.eventType] = (counts[e.eventType] ?? 0) + 1;
        });
        summaryText = Object.entries(counts)
          .map(([type, count]) => `${count} ${EVENT_LABEL_PLURAL[type] ?? type}`)
          .join(' · ');
      }

      return { key, label, dateText, summaryText, data: bucketEvents };
    });
  }, [filteredEvents, granularity, daySummaries]);

  const getScopeChip = useCallback(
    (event: TimelineEvent) => {
      if (scope.mode === 'portfolio' && event.projectId) {
        const name = projectNamesById[event.projectId];
        if (!name) return null;
        return { label: name, color: colorForId(event.projectId) };
      }
      if (scope.mode === 'project' && event.siteId) {
        const name = siteNamesById[event.siteId];
        if (!name) return null;
        return { label: name, color: colorForId(event.siteId) };
      }
      return null;
    },
    [scope.mode, projectNamesById, siteNamesById]
  );

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await refetch();
    setIsRefreshing(false);
  }, [refetch]);

  return (
    <View style={styles.container}>
      <View style={styles.headerContainer}>
        <Text style={styles.headerTitle}>Timeline</Text>
        <Text style={styles.headerSubtitle}>{scopeText}</Text>
      </View>

      <TimelineGranularitySwitcher value={granularity} onChange={setGranularity} />
      <TimelineFilterChips activeKey={filterKey} onChange={setFilterKey} />

      {isLoading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="small" color={theme.colors.textPrimary} />
        </View>
      ) : error ? (
        <View style={styles.centerContainer}>
          <AlertCircle size={24} color={theme.colors.statusDanger} style={{ marginBottom: 8 }} />
          <Text style={styles.errorText}>{error.message}</Text>
        </View>
      ) : sections.length === 0 ? (
        <View style={styles.emptyWrap}>
          <EmptyState
            message={
              filterKey === 'all'
                ? 'Logged materials will appear here as they happen.'
                : 'No events match this filter in range.'
            }
            Icon={Clock}
          />
        </View>
      ) : (
        <SectionList
          style={styles.list}
          contentContainerStyle={styles.listContent}
          sections={sections}
          keyExtractor={(item) => item.id}
          stickySectionHeadersEnabled
          renderSectionHeader={({ section }) => (
            <TimelineDayHeader label={section.label} dateText={section.dateText} summaryText={section.summaryText} />
          )}
          renderItem={({ item, index, section }) => (
            <TimelineEventCard
              event={item}
              scopeChip={getScopeChip(item)}
              onPress={setSelectedEvent}
              isLast={index === section.data.length - 1}
            />
          )}
          refreshControl={
            <RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} tintColor={theme.colors.textPrimary} />
          }
          onEndReachedThreshold={0.4}
          onEndReached={() => {
            if (hasMore) loadMore();
          }}
          ListFooterComponent={
            isLoadingMore ? (
              <View style={styles.footerLoading}>
                <ActivityIndicator size="small" color={theme.colors.textPrimary} />
              </View>
            ) : null
          }
        />
      )}

      <TimelineEventDetailSheet event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </View>
  );
}

const createStyles = (theme: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.backgroundApp,
  },
  headerContainer: {
    paddingHorizontal: theme.spacing.space4,
    paddingTop: theme.spacing.space4,
    paddingBottom: theme.spacing.space2,
  },
  headerTitle: {
    fontSize: theme.typography.size2xl,
    fontWeight: theme.typography.weightBold,
    color: theme.colors.textPrimary,
  },
  headerSubtitle: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textMuted,
    marginTop: 2,
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingHorizontal: theme.spacing.space4,
    paddingBottom: 40,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  errorText: {
    fontSize: theme.typography.sizeSm,
    color: theme.colors.textMuted,
    textAlign: 'center',
  },
  emptyWrap: {
    paddingHorizontal: theme.spacing.space4,
    paddingTop: theme.spacing.space4,
  },
  footerLoading: {
    paddingVertical: theme.spacing.space4,
    alignItems: 'center',
  },
});
