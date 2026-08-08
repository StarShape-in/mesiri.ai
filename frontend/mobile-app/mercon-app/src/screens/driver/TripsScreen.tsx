import React, { useMemo, useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, SafeAreaView, StatusBar,
  FlatList, ActivityIndicator, RefreshControl,
} from 'react-native';
import { Building2, Package, Calendar, ClipboardList, TriangleAlert } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { StatusBadge, SearchInput } from '../../components';
import { DriverBottomNav } from '../../navigation/DriverBottomNav';
import { useCurrentTrip } from '../../lib/use-current-trip';
import { useTripHistory } from '../../lib/use-trip-history';
import { statusLabel, type MobileTrip, type TripStatus } from '../../lib/trips';

const TABS = ['Active', 'Upcoming', 'Completed'] as const;
type Tab = typeof TABS[number];

/** Statuses that count as an in-progress ("Active") trip. */
const ACTIVE_STATUSES: TripStatus[] = ['AtPickup', 'InTransit', 'AtDelivery'];

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

interface CardData {
  key: string;
  tripId: string;
  displayId: string;
  title: string;
  statusText: string;
  cargo: string;
  date: string;
}

function toCard(t: MobileTrip): CardData {
  const dateSource = t.actual_end ?? t.planned_end ?? t.actual_start ?? t.planned_start ?? null;
  return {
    key: t.id,
    tripId: t.id,
    displayId: t.ref_id ?? t.id.slice(0, 8),
    title: t.customer?.name ?? 'Unassigned customer',
    statusText: statusLabel(t.status),
    cargo: t.cargo_type,
    date: formatDate(dateSource),
  };
}

const TripCard = ({ item, onPress }: { item: CardData; onPress: () => void }) => (
  <TouchableOpacity style={styles.card} activeOpacity={0.8} onPress={onPress}>
    <View style={styles.cardHeader}>
      <Text style={styles.cardId}>#{item.displayId}</Text>
      <StatusBadge status={item.statusText} />
    </View>
    <View style={styles.cardRoute}>
      <Building2 size={16} color={Colors.gray500} strokeWidth={2} />
      <Text style={styles.routeText}>{item.title}</Text>
    </View>
    <View style={styles.cardMeta}>
      <View style={styles.metaItem}>
        <Package size={13} color={Colors.gray500} strokeWidth={2} />
        <Text style={styles.metaText}>{item.cargo}</Text>
      </View>
      <View style={styles.metaItem}>
        <Calendar size={13} color={Colors.gray500} strokeWidth={2} />
        <Text style={styles.metaText}>{item.date}</Text>
      </View>
    </View>
  </TouchableOpacity>
);

const TripsScreen = ({ navigation }: any) => {
  const [activeTab, setActiveTab] = useState('Trips');
  const [selectedTab, setSelectedTab] = useState<Tab>('Active');
  const [search, setSearch] = useState('');

  const { trip: current, loading: loadingCurrent, refetch: refetchCurrent } = useCurrentTrip();
  const { trips: history, loading: loadingHistory, error, refetch: refetchHistory } = useTripHistory();

  const loading = loadingCurrent || loadingHistory;

  const cards = useMemo(() => {
    let source: MobileTrip[] = [];
    if (selectedTab === 'Active') {
      source = current && ACTIVE_STATUSES.includes(current.status) ? [current] : [];
    } else if (selectedTab === 'Upcoming') {
      source = current && (current.status === 'Draft' || current.status === 'Dispatched') ? [current] : [];
    } else {
      source = history;
    }
    const q = search.trim().toLowerCase();
    return source
      .map(toCard)
      .filter(
        (c) =>
          !q ||
          c.displayId.toLowerCase().includes(q) ||
          c.title.toLowerCase().includes(q) ||
          c.cargo.toLowerCase().includes(q)
      );
  }, [selectedTab, current, history, search]);

  const onRefresh = () => {
    refetchCurrent();
    refetchHistory();
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <View style={styles.headerWrapper}>
        <Text style={styles.screenTitle}>My Trips</Text>
      </View>

      <SearchInput
        value={search}
        onChangeText={setSearch}
        placeholder="Search by trip ID, customer or cargo..."
        style={styles.search}
      />

      {/* Tabs */}
      <View style={styles.tabsRow}>
        {TABS.map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tab, selectedTab === tab ? styles.tabActive : null]}
            activeOpacity={0.8}
            onPress={() => setSelectedTab(tab)}
          >
            <Text style={[styles.tabText, selectedTab === tab ? styles.tabTextActive : null]}>
              {tab}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <FlatList
        data={cards}
        keyExtractor={(item) => item.key}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={loading && cards.length > 0} onRefresh={onRefresh} />
        }
        renderItem={({ item }) => (
          <TripCard
            item={item}
            onPress={() => navigation?.navigate('TripDetails', { tripId: item.tripId })}
          />
        )}
        ListEmptyComponent={
          loading ? (
            <View style={styles.emptyState}>
              <ActivityIndicator color={Colors.primary} />
            </View>
          ) : error ? (
            <View style={styles.emptyState}>
              <TriangleAlert size={44} color={Colors.gray400} strokeWidth={1.6} />
              <Text style={styles.emptyTitle}>Couldn't load trips</Text>
              <Text style={styles.emptyText}>{error}</Text>
            </View>
          ) : (
            <View style={styles.emptyState}>
              <ClipboardList size={44} color={Colors.gray400} strokeWidth={1.6} />
              <Text style={styles.emptyTitle}>No {selectedTab} Trips</Text>
              <Text style={styles.emptyText}>
                You have no {selectedTab.toLowerCase()} trips at this time.
              </Text>
            </View>
          )
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  headerWrapper: {
    backgroundColor: Colors.white,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  screenTitle: {
    fontSize: Typography.xl,
    fontWeight: '800',
    color: Colors.gray900,
  },
  search: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.md,
  },
  tabsRow: {
    flexDirection: 'row',
    marginHorizontal: Spacing.lg,
    marginVertical: Spacing.md,
    backgroundColor: Colors.gray200,
    borderRadius: Radius.lg,
    padding: 3,
  },
  tab: {
    flex: 1,
    paddingVertical: Spacing.sm,
    alignItems: 'center',
    borderRadius: Radius.md,
  },
  tabActive: {
    backgroundColor: Colors.white,
    ...Shadows.sm,
  },
  tabText: {
    fontSize: Typography.sm,
    color: Colors.gray500,
    fontWeight: '600',
  },
  tabTextActive: {
    color: Colors.gray900,
  },
  list: {
    padding: Spacing.lg,
    gap: Spacing.md,
    paddingBottom: 80,
  },
  card: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    ...Shadows.sm,
    gap: Spacing.sm,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardId: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  cardRoute: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  routeText: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.gray900,
  },
  cardMeta: {
    flexDirection: 'row',
    gap: Spacing.lg,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  metaText: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
  emptyState: {
    alignItems: 'center',
    paddingTop: Spacing['3xl'],
    gap: Spacing.sm,
  },
  emptyTitle: {
    fontSize: Typography.lg,
    fontWeight: '700',
    color: Colors.gray700,
  },
  emptyText: {
    fontSize: Typography.sm,
    color: Colors.gray500,
    textAlign: 'center',
  },
});

export default TripsScreen;
