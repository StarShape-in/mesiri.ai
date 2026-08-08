import React, { useMemo, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, SafeAreaView,
  StatusBar, FlatList, ActivityIndicator, RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Truck, Weight, Gauge } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { StatusBadge, SearchInput, FilterChip } from '../../components';
import { useOperatorVehicles, type OperatorVehicle } from '../../lib/operator';

const FILTERS: { label: string; status: string | null }[] = [
  { label: 'All', status: null },
  { label: 'Available', status: 'Available' },
  { label: 'On Trip', status: 'OnTrip' },
  { label: 'Maintenance', status: 'Maintenance' },
  { label: 'Inactive', status: 'Inactive' },
];

const STATUS_LABELS: Record<string, string> = {
  Available: 'Available',
  OnTrip: 'On Trip',
  Maintenance: 'Maintenance',
  Inactive: 'Inactive',
};

const VehicleCard = ({ item, onPress }: { item: OperatorVehicle; onPress: () => void }) => (
  <TouchableOpacity style={styles.card} activeOpacity={0.8} onPress={onPress}>
    <View style={styles.cardTop}>
      <View style={styles.vehicleIconBox}>
        <Truck size={26} color={Colors.primary} strokeWidth={2} />
      </View>
      <View style={styles.vehicleInfo}>
        <View style={styles.vehicleIdRow}>
          <Text style={styles.vehicleId}>{item.plate_number}</Text>
          <StatusBadge status={STATUS_LABELS[item.status] ?? item.status} />
        </View>
        <Text style={styles.vehicleModel}>
          {item.asset_type}
          {item.ref_id ? ` · ${item.ref_id}` : ''}
        </Text>
        <View style={styles.vehicleMeta}>
          <View style={styles.metaItem}>
            <Weight size={13} color={Colors.gray500} strokeWidth={2} />
            <Text style={styles.metaText}>{item.capacity_kg.toLocaleString()} kg</Text>
          </View>
          <View style={styles.metaItem}>
            <Gauge size={13} color={Colors.gray500} strokeWidth={2} />
            <Text style={styles.metaText}>{Math.round(item.current_odometer).toLocaleString()} km</Text>
          </View>
        </View>
      </View>
    </View>
  </TouchableOpacity>
);

const VehicleListScreen = () => {
  const router = useRouter();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const { vehicles, loading, error, refetch } = useOperatorVehicles();

  const count = (status: string | null) =>
    status ? vehicles.filter((v) => v.status === status).length : vehicles.length;

  const filtered = useMemo(() => {
    const active = FILTERS.find((f) => f.label === statusFilter) ?? FILTERS[0];
    const q = search.trim().toLowerCase();
    return vehicles.filter((v) => {
      if (active.status && v.status !== active.status) return false;
      if (!q) return true;
      return (
        v.plate_number.toLowerCase().includes(q) ||
        (v.ref_id ?? '').toLowerCase().includes(q) ||
        v.asset_type.toLowerCase().includes(q)
      );
    });
  }, [vehicles, statusFilter, search]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Fleet</Text>
        <Text style={styles.headerCount}>{vehicles.length} vehicles</Text>
      </View>

      {/* Stats Row */}
      <View style={styles.statsRow}>
        {[
          { label: 'Total', value: count(null), color: Colors.gray900 },
          { label: 'Available', value: count('Available'), color: Colors.success },
          { label: 'On Trip', value: count('OnTrip'), color: Colors.primary },
          { label: 'Service', value: count('Maintenance'), color: Colors.warning },
        ].map((s) => (
          <View key={s.label} style={styles.statBox}>
            <Text style={[styles.statValue, { color: s.color }]}>{s.value}</Text>
            <Text style={styles.statLabel}>{s.label}</Text>
          </View>
        ))}
      </View>

      <SearchInput
        value={search}
        onChangeText={setSearch}
        placeholder="Search by plate or type..."
        style={styles.search}
      />

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filtersRow}>
        {FILTERS.map((f) => (
          <FilterChip
            key={f.label}
            label={f.label}
            active={statusFilter === f.label}
            onPress={() => setStatusFilter(f.label)}
          />
        ))}
      </ScrollView>

      <FlatList
        data={filtered}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading && vehicles.length > 0} onRefresh={refetch} />}
        renderItem={({ item }) => (
          <VehicleCard
            item={item}
            onPress={() => router.push({ pathname: '/operator/vehicle-edit', params: { id: item.id } })}
          />
        )}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
          ) : (
            <View style={styles.empty}>
              <Truck size={44} color={Colors.gray400} strokeWidth={1.6} />
              <Text style={styles.emptyText}>{error ?? 'No vehicles match your search'}</Text>
            </View>
          )
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  header: {
    backgroundColor: Colors.white,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: Spacing.sm,
  },
  headerTitle: {
    fontSize: Typography.xl,
    fontWeight: '800',
    color: Colors.gray900,
  },
  headerCount: {
    fontSize: Typography.sm,
    color: Colors.gray500,
  },
  statsRow: {
    flexDirection: 'row',
    backgroundColor: Colors.white,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  statBox: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: Spacing.md,
    borderRightWidth: 1,
    borderRightColor: Colors.gray100,
  },
  statValue: {
    fontSize: Typography.xl,
    fontWeight: '800',
  },
  statLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
    marginTop: 1,
  },
  search: {
    marginHorizontal: Spacing.lg,
    marginTop: Spacing.md,
  },
  filtersRow: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    gap: Spacing.xs,
  },
  list: {
    padding: Spacing.lg,
    gap: Spacing.md,
    paddingBottom: 100,
    flexGrow: 1,
  },
  card: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    overflow: 'hidden',
    ...Shadows.sm,
  },
  cardTop: {
    flexDirection: 'row',
    padding: Spacing.lg,
    gap: Spacing.md,
    alignItems: 'flex-start',
  },
  vehicleIconBox: {
    width: 52,
    height: 52,
    borderRadius: Radius.lg,
    backgroundColor: Colors.gray100,
    alignItems: 'center',
    justifyContent: 'center',
  },
  vehicleInfo: {
    flex: 1,
    gap: 3,
  },
  vehicleIdRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  vehicleId: {
    fontSize: Typography.base,
    fontWeight: '800',
    color: Colors.gray900,
    letterSpacing: 1,
  },
  vehicleModel: {
    fontSize: Typography.sm,
    color: Colors.gray600,
  },
  vehicleMeta: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginTop: 2,
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
  empty: {
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

export default VehicleListScreen;
