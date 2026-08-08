import React from 'react';
import {
  View, Text, ScrollView, StyleSheet, SafeAreaView, StatusBar, ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Check } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { Button, Badge } from '../../components';
import { useTripHistory } from '../../lib/use-trip-history';

function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

function formatDuration(startIso?: string | null, endIso?: string | null): string {
  if (!startIso || !endIso) return '—';
  const start = new Date(startIso).getTime();
  const end = new Date(endIso).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return '—';
  const mins = Math.round((end - start) / 60000);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

const TripCompletedScreen = () => {
  const router = useRouter();
  const { trips, loading } = useTripHistory();
  const trip = trips[0] ?? null; // most recent completed trip

  const onTime =
    trip?.planned_end && trip?.actual_end
      ? new Date(trip.actual_end).getTime() <= new Date(trip.planned_end).getTime()
      : null;

  const summaryItems = trip
    ? [
        { label: 'Trip ID', value: `#${trip.ref_id ?? trip.id.slice(0, 8)}` },
        { label: 'Customer', value: trip.customer?.name ?? '—' },
        { label: 'Cargo', value: trip.cargo_type },
        { label: 'Distance', value: trip.planned_distance ? `${trip.planned_distance} km` : '—' },
        { label: 'Duration', value: formatDuration(trip.actual_start, trip.actual_end) },
        { label: 'Completed', value: formatDate(trip.actual_end) },
      ]
    : [];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.gray100} />
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Success Header */}
        <View style={styles.successSection}>
          <View style={styles.checkCircle}>
            <Check size={44} color={Colors.white} strokeWidth={3} />
          </View>
          {onTime !== null && (
            <Badge
              label={onTime ? 'On Time' : 'Late'}
              variant={onTime ? 'success' : 'warning'}
              style={styles.onTimeBadge}
            />
          )}
          <Text style={styles.heading}>Trip Completed!</Text>
          <Text style={styles.subheading}>
            The delivery has been confirmed and your trip is now complete.
          </Text>
        </View>

        {loading && !trip && <ActivityIndicator color={Colors.primary} />}

        {/* Trip Summary */}
        {trip && (
          <View style={styles.summaryCard}>
            <Text style={styles.summaryTitle}>Trip Summary</Text>
            {summaryItems.map((item, i) => (
              <View
                key={item.label}
                style={[styles.summaryRow, i < summaryItems.length - 1 ? styles.summaryRowBorder : null]}
              >
                <Text style={styles.summaryLabel}>{item.label}</Text>
                <Text style={styles.summaryValue}>{item.value}</Text>
              </View>
            ))}
          </View>
        )}

        <Button title="Back to Home" onPress={() => router.replace('/')} />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  scroll: {
    padding: Spacing.lg,
    paddingBottom: Spacing['3xl'],
    gap: Spacing.lg,
  },
  successSection: {
    alignItems: 'center',
    paddingVertical: Spacing.xl,
  },
  checkCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: Colors.success,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.md,
    ...Shadows.lg,
  },
  onTimeBadge: {
    marginBottom: Spacing.md,
  },
  heading: {
    fontSize: 28,
    fontWeight: '800',
    color: Colors.gray900,
    marginBottom: Spacing.sm,
  },
  subheading: {
    fontSize: Typography.sm,
    color: Colors.gray500,
    textAlign: 'center',
    lineHeight: 20,
    maxWidth: 280,
  },
  ratingCard: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    alignItems: 'center',
    ...Shadows.sm,
  },
  ratingTitle: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.gray900,
    marginBottom: 2,
  },
  ratingSubtitle: {
    fontSize: Typography.sm,
    color: Colors.gray500,
    marginBottom: Spacing.md,
  },
  starsRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  star: {
    fontSize: 36,
    color: '#F59E0B',
  },
  summaryCard: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    ...Shadows.sm,
  },
  summaryTitle: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.gray900,
    marginBottom: Spacing.md,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: Spacing.sm,
  },
  summaryRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  summaryLabel: {
    fontSize: Typography.sm,
    color: Colors.gray500,
  },
  summaryValue: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
  },
  earningsValue: {
    color: Colors.success,
    fontSize: Typography.base,
  },
  performanceRow: {
    flexDirection: 'row',
    gap: Spacing.md,
  },
  perfCard: {
    flex: 1,
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    padding: Spacing.md,
    alignItems: 'center',
    gap: 4,
    ...Shadows.sm,
  },
  perfIcon: {
    fontSize: 24,
  },
  perfValue: {
    fontSize: Typography.lg,
    fontWeight: '800',
    color: Colors.gray900,
  },
  perfLabel: {
    fontSize: Typography.xs,
    color: Colors.gray500,
  },
  viewTripsBtn: {
    alignItems: 'center',
    paddingVertical: Spacing.sm,
  },
  viewTripsBtnText: {
    fontSize: Typography.sm,
    color: Colors.primary,
    fontWeight: '700',
  },
});

export default TripCompletedScreen;
