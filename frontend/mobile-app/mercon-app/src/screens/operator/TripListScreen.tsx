import React, { useMemo, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, SafeAreaView,
  StatusBar, FlatList, ActivityIndicator, RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { User, Package, Calendar, Truck } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { StatusBadge, SearchInput, FilterChip } from '../../components';
import { useOperatorTrips, type OperatorTrip } from '../../lib/operator';
import { statusLabel, type TripStatus } from '../../lib/trips';

const FILTERS: { label: string; statuses: string[] | null }[] = [
  { label: 'All', statuses: null },
  { label: 'Active', statuses: ['Dispatched', 'AtPickup', 'InTransit', 'AtDelivery'] },
  { label: 'In Transit', statuses: ['InTransit'] },
  { label: 'Completed', statuses: ['Completed', 'Invoiced'] },
  { label: 'Cancelled', statuses: ['Cancelled'] },
];

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

const driverName = (t: OperatorTrip) =>
  t.driver ? `${t.driver.first_name} ${t.driver.last_name}` : 'Unassigned';

const TripCard = ({ item, onPress }: { item: OperatorTrip; onPress: () => void }) => (
  <TouchableOpacity style={styles.card} activeOpacity={0.8} onPress={onPress}>
    <View style={styles.cardTop}>
      <Text style={styles.tripId}>#{item.ref_id ?? item.id.slice(0, 8)}</Text>
      <StatusBadge status={statusLabel(item.status as TripStatus)} />
    </View>
    <Text style={styles.tripRoute}>{item.customer?.name ?? 'Customer'}</Text>
    <View style={styles.cardMeta}>
      <View style={styles.metaItem}>
        <User size={13} color={Colors.gray500} strokeWidth={2} />
        <Text style={styles.metaText}>{driverName(item)}</Text>
      </View>
      <View style={styles.metaItem}>
        <Package size={13} color={Colors.gray500} strokeWidth={2} />
        <Text style={styles.metaText}>{item.cargo_type}</Text>
      </View>
    </View>
    <View style={styles.metaItem}>
      <Calendar size={13} color={Colors.gray400} strokeWidth={2} />
      <Text style={styles.tripDate}>{formatDate(item.planned_start ?? item.createdAt)}</Text>
    </View>
  </TouchableOpacity>
);

const TripListScreen = () => {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('All');
  const { trips, loading, error, refetch } = useOperatorTrips();

  const count = (statuses: string[] | null) =>
    statuses ? trips.filter((t) => statuses.includes(t.status)).length : trips.length;

  const KPI_CHIPS = FILTERS.map((f) => ({ label: f.label, value: String(count(f.statuses)) }));

  const filtered = useMemo(() => {
    const active = FILTERS.find((f) => f.label === filter) ?? FILTERS[0];
    const q = search.trim().toLowerCase();
    return trips.filter((t) => {
      const okStatus = !active.statuses || active.statuses.includes(t.status);
      if (!okStatus) return false;
      if (!q) return true;
      return (
        (t.ref_id ?? '').toLowerCase().includes(q) ||
        (t.customer?.name ?? '').toLowerCase().includes(q) ||
        driverName(t).toLowerCase().includes(q) ||
        t.cargo_type.toLowerCase().includes(q)
      );
    });
  }, [trips, filter, search]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <View style={styles.headerRow}>
        <Text style={styles.headerTitle}>Trips</Text>
      </View>

      {/* KPI Chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.kpiRow}>
        {KPI_CHIPS.map((chip) => (
          <View key={chip.label} style={styles.kpiChip}>
            <Text style={styles.kpiValue}>{chip.value}</Text>
            <Text style={styles.kpiLabel}>{chip.label}</Text>
          </View>
        ))}
      </ScrollView>

      <SearchInput
        value={search}
        onChangeText={setSearch}
        placeholder="Search trips, drivers, customers..."
        style={styles.search}
      />

      {/* Filter Pills */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filtersRow}>
        {FILTERS.map((f) => (
          <FilterChip
            key={f.label}
            label={f.label}
            active={filter === f.label}
            onPress={() => setFilter(f.label)}
          />
        ))}
      </ScrollView>

      <FlatList
        data={filtered}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading && trips.length > 0} onRefresh={refetch} />}
        renderItem={({ item }) => (
          <TripCard
            item={item}
            onPress={() => router.push({ pathname: '/operator/trip-details', params: { id: item.id } })}
          />
        )}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
          ) : (
            <View style={styles.emptyState}>
              <Truck size={44} color={Colors.gray400} strokeWidth={1.6} />
              <Text style={styles.emptyText}>{error ?? 'No trips match your filters'}</Text>
            </View>
          )
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  headerRow: {
    backgroundColor: Colors.white,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  headerTitle: {
    fontSize: Typography.xl,
    fontWeight: '800',
    color: Colors.gray900,
  },
  kpiRow: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    gap: Spacing.sm,
  },
  kpiChip: {
    backgroundColor: Colors.white,
    borderRadius: Radius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    alignItems: 'center',
    minWidth: 70,
    ...Shadows.sm,
  },
  kpiValue: {
    fontSize: Typography.lg,
    fontWeight: '800',
    color: Colors.gray900,
  },
  kpiLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
  search: {
    marginHorizontal: Spacing.lg,
    marginBottom: Spacing.sm,
  },
  filtersRow: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
    gap: Spacing.xs,
  },
  list: {
    padding: Spacing.lg,
    gap: Spacing.md,
    paddingBottom: 80,
    flexGrow: 1,
  },
  card: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    ...Shadows.sm,
    gap: Spacing.xs,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  tripId: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  tripRoute: {
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
  tripDate: {
    fontSize: Typography.xs,
    color: Colors.gray400,
  },
  emptyState: {
    alignItems: 'center',
    paddingTop: Spacing['3xl'],
    gap: Spacing.sm,
  },
  emptyIcon: {
    fontSize: 40,
  },
  emptyText: {
    fontSize: Typography.base,
    color: Colors.gray500,
  },
});

export default TripListScreen;
