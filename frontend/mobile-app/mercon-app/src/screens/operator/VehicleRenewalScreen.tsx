import React, { useMemo, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, SafeAreaView, StatusBar, FlatList, Alert,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { useRouter } from 'expo-router';
import { ArrowLeft, Calendar, ArrowRight, CircleCheck } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { StatusBadge, FilterChip, Button } from '../../components';
import { useOperatorVehicleRenewals, type VehicleRenewal } from '../../lib/operator';

type Bucket = 'due' | 'critical' | 'overdue' | 'ok';

function bucketOf(r: VehicleRenewal): Bucket {
  if (r.daysLeft == null) return 'ok';
  if (r.daysLeft < 0) return 'overdue';
  if (r.daysLeft <= 7) return 'critical';
  if (r.daysLeft <= 30) return 'due';
  return 'ok';
}

const BUCKET_LABEL: Record<Bucket, string> = {
  due: 'Due Soon',
  critical: 'Critical',
  overdue: 'Overdue',
  ok: 'OK',
};

const BUCKET_BADGE_STATUS: Record<Bucket, string> = {
  due: 'Expiring',
  critical: 'Expiring',
  overdue: 'Expired',
  ok: 'Active',
};

/** Splits "VehicleRegistration" → "Vehicle Registration" for display. */
function formatDocType(docType: string): string {
  return docType.replace(/([a-z])([A-Z])/g, '$1 $2');
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

const FILTER_TABS: { label: string; bucket: Bucket | 'All' }[] = [
  { label: 'All', bucket: 'All' },
  { label: 'Due Soon', bucket: 'due' },
  { label: 'Critical', bucket: 'critical' },
  { label: 'Overdue', bucket: 'overdue' },
];

const RenewalCard = ({ item }: { item: VehicleRenewal }) => {
  const bucket = bucketOf(item);
  const isUrgent = bucket === 'overdue' || bucket === 'critical';

  return (
    <View style={[styles.card, isUrgent ? styles.cardUrgent : null]}>
      <View style={styles.cardHeader}>
        <View>
          <Text style={styles.vehicleId}>{item.vehiclePlate}</Text>
          <Text style={styles.docType}>{formatDocType(item.docType)}</Text>
        </View>
        <StatusBadge status={BUCKET_BADGE_STATUS[bucket]} />
      </View>

      <View style={styles.expiryRow}>
        <View style={styles.expiryItem}>
          <Calendar size={18} color={Colors.gray500} strokeWidth={2} />
          <View>
            <Text style={styles.expiryLabel}>Expiry Date</Text>
            <Text style={[styles.expiryDate, bucket === 'overdue' ? styles.overdueDate : null]}>
              {formatDate(item.expiryDate)}
            </Text>
          </View>
        </View>
        {item.daysLeft != null && (
          <View style={styles.daysLeftBox}>
            <Text style={[
              styles.daysLeftValue,
              bucket === 'overdue' ? styles.overdueDays : bucket === 'critical' ? styles.criticalDays : null,
            ]}>
              {item.daysLeft < 0 ? `${Math.abs(item.daysLeft)}d overdue` : `${item.daysLeft}d left`}
            </Text>
          </View>
        )}
      </View>

      <View style={styles.cardFooter}>
        <Text style={styles.statusText}>Status: {item.status}</Text>
        {bucket !== 'ok' && (
          <Button
            variant="primary"
            size="sm"
            label="Renew Now"
            iconRight={<ArrowRight size={16} color={Colors.white} strokeWidth={2.4} />}
            onPress={() => Alert.alert('Coming Soon', 'Uploading a renewed document will be available in a future update.')}
          />
        )}
      </View>
    </View>
  );
};

const VehicleRenewalScreen = () => {
  const router = useRouter();
  const [filter, setFilter] = useState('All');
  const { renewals, loading, error, refetch } = useOperatorVehicleRenewals();

  const stats = useMemo(() => ({
    due: renewals.filter((r) => bucketOf(r) === 'due').length,
    critical: renewals.filter((r) => bucketOf(r) === 'critical').length,
    overdue: renewals.filter((r) => bucketOf(r) === 'overdue').length,
  }), [renewals]);

  const filtered = useMemo(() => {
    const active = FILTER_TABS.find((f) => f.label === filter) ?? FILTER_TABS[0];
    if (active.bucket === 'All') return renewals;
    return renewals.filter((r) => bucketOf(r) === active.bucket);
  }, [renewals, filter]);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.white} />

      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} activeOpacity={0.8} onPress={() => router.back()}>
          <ArrowLeft size={22} color={Colors.gray900} strokeWidth={2.2} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Vehicle Renewals</Text>
        <View style={styles.placeholder} />
      </View>

      {/* Stat Chips */}
      <View style={styles.statsRow}>
        {[
          { label: 'Due Soon', value: stats.due, color: Colors.warning, bg: Colors.warningLight },
          { label: 'Critical', value: stats.critical, color: Colors.error, bg: Colors.errorLight },
          { label: 'Overdue', value: stats.overdue, color: Colors.error, bg: Colors.errorLight },
        ].map((s) => (
          <View key={s.label} style={[styles.statChip, { backgroundColor: s.bg }]}>
            <Text style={[styles.statValue, { color: s.color }]}>{s.value}</Text>
            <Text style={[styles.statLabel, { color: s.color }]}>{s.label}</Text>
          </View>
        ))}
      </View>

      {/* Filter Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filtersRow}>
        {FILTER_TABS.map((tab) => (
          <FilterChip
            key={tab.label}
            label={tab.label}
            active={filter === tab.label}
            onPress={() => setFilter(tab.label)}
          />
        ))}
      </ScrollView>

      <FlatList
        data={filtered}
        keyExtractor={(item) => item.documentId}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={loading && renewals.length > 0} onRefresh={refetch} />}
        renderItem={({ item }) => <RenewalCard item={item} />}
        ListEmptyComponent={
          loading ? (
            <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
          ) : (
            <View style={styles.empty}>
              <CircleCheck size={44} color={Colors.success} strokeWidth={1.8} />
              <Text style={styles.emptyText}>{error ?? 'No vehicle documents in this category'}</Text>
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: Colors.gray100,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: Typography.lg,
    fontWeight: '700',
    color: Colors.gray900,
  },
  placeholder: {
    width: 40,
  },
  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    gap: Spacing.sm,
  },
  statChip: {
    flex: 1,
    borderRadius: Radius.lg,
    paddingVertical: Spacing.sm,
    alignItems: 'center',
    gap: 2,
  },
  statValue: {
    fontSize: Typography.xl,
    fontWeight: '800',
  },
  statLabel: {
    fontSize: Typography.xs,
    fontWeight: '600',
  },
  filtersRow: {
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
    gap: Spacing.xs,
  },
  list: {
    padding: Spacing.lg,
    gap: Spacing.md,
    paddingBottom: Spacing['3xl'],
    flexGrow: 1,
  },
  card: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    ...Shadows.sm,
    gap: Spacing.md,
  },
  cardUrgent: {
    borderLeftWidth: 3,
    borderLeftColor: Colors.error,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  vehicleId: {
    fontSize: Typography.base,
    fontWeight: '800',
    color: Colors.gray900,
    letterSpacing: 1,
  },
  docType: {
    fontSize: Typography.sm,
    color: Colors.gray600,
    marginTop: 2,
  },
  expiryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: Colors.gray50,
    borderRadius: Radius.lg,
    padding: Spacing.md,
  },
  expiryItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  expiryLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
  expiryDate: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  overdueDate: {
    color: Colors.error,
  },
  daysLeftBox: {},
  daysLeftValue: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.warning,
  },
  overdueDays: {
    color: Colors.error,
  },
  criticalDays: {
    color: Colors.error,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statusText: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
  empty: {
    alignItems: 'center',
    paddingTop: Spacing['3xl'],
    gap: Spacing.sm,
  },
  emptyText: {
    fontSize: Typography.base,
    color: Colors.gray500,
  },
});

export default VehicleRenewalScreen;
