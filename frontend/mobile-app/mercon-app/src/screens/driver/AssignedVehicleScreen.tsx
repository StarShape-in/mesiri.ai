import React from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, SafeAreaView,
  StatusBar, ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { ArrowLeft, Truck } from 'lucide-react-native';
import { Colors, Spacing, Radius, Typography, Shadows } from '../../theme/tokens';
import { useAssignedVehicle } from '../../lib/vehicle';

const AssignedVehicleScreen = () => {
  const router = useRouter();
  const { vehicle, loading, error } = useAssignedVehicle();

  const specs = vehicle
    ? [
        { label: 'Plate', value: vehicle.plate_number },
        { label: 'Type', value: vehicle.asset_type },
        { label: 'Status', value: vehicle.status },
        { label: 'Capacity', value: `${vehicle.capacity_kg.toLocaleString()} kg` },
        { label: 'Odometer', value: `${Math.round(vehicle.current_odometer).toLocaleString()} km` },
        ...(vehicle.trailer_number
          ? [{ label: 'Trailer', value: `${vehicle.trailer_number}${vehicle.trailer_type ? ` (${vehicle.trailer_type})` : ''}` }]
          : []),
        ...(vehicle.trip_ref_id ? [{ label: 'On Trip', value: `#${vehicle.trip_ref_id}` }] : []),
      ]
    : [];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: Colors.gray100 }}>
      <StatusBar barStyle="light-content" backgroundColor="#1A1A1A" />
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Dark Header */}
        <View style={styles.darkHeader}>
          <TouchableOpacity style={styles.backBtn} activeOpacity={0.8} onPress={() => router.back()}>
            <ArrowLeft size={24} color={Colors.white} strokeWidth={2.2} />
          </TouchableOpacity>
          <View style={styles.headerContent}>
            <View style={styles.vehicleIconBox}>
              <Truck size={30} color={Colors.white} strokeWidth={2} />
            </View>
            <Text style={styles.vehicleId}>
              {vehicle ? (vehicle.ref_id ? `#${vehicle.ref_id}` : vehicle.plate_number) : 'Assigned Vehicle'}
            </Text>
            {vehicle && <Text style={styles.vehicleModel}>{vehicle.asset_type}</Text>}
            {vehicle && (
              <View style={styles.headerBadges}>
                <View style={styles.statusChip}>
                  <View style={styles.statusDot} />
                  <Text style={styles.statusChipText}>{vehicle.status}</Text>
                </View>
                <View style={styles.plateChip}>
                  <Text style={styles.plateText}>{vehicle.plate_number}</Text>
                </View>
              </View>
            )}
          </View>
        </View>

        {loading ? (
          <ActivityIndicator color={Colors.primary} style={{ marginTop: Spacing['3xl'] }} />
        ) : !vehicle ? (
          <View style={styles.emptyCard}>
            <Truck size={48} color={Colors.gray400} strokeWidth={1.6} />
            <Text style={styles.emptyTitle}>{error ? 'Could not load vehicle' : 'No vehicle assigned'}</Text>
            <Text style={styles.emptyText}>
              {error ?? "You'll see your truck here once you're dispatched on a trip."}
            </Text>
          </View>
        ) : (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Vehicle Details</Text>
            <View style={styles.specsGrid}>
              {specs.map((spec, i) => (
                <View
                  key={spec.label}
                  style={[styles.specRow, i < specs.length - 1 ? styles.specRowBorder : null]}
                >
                  <Text style={styles.specLabel}>{spec.label}</Text>
                  <Text style={styles.specValue}>{spec.value}</Text>
                </View>
              ))}
            </View>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  scroll: {
    paddingBottom: Spacing['3xl'],
    flexGrow: 1,
  },
  darkHeader: {
    backgroundColor: '#1A1A1A',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing['2xl'],
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: Radius.full,
    backgroundColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.lg,
  },
  headerContent: {
    alignItems: 'center',
  },
  vehicleIconBox: {
    width: 72,
    height: 72,
    borderRadius: Radius.xl,
    backgroundColor: 'rgba(255,255,255,0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.md,
  },
  vehicleId: {
    fontSize: Typography.xl,
    fontWeight: '800',
    color: Colors.white,
  },
  vehicleModel: {
    fontSize: Typography.sm,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 2,
  },
  headerBadges: {
    flexDirection: 'row',
    gap: Spacing.sm,
    marginTop: Spacing.md,
  },
  statusChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(34,197,94,0.2)',
    borderRadius: Radius.full,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#22C55E',
  },
  statusChipText: {
    fontSize: Typography.xs,
    color: Colors.white,
    fontWeight: '600',
  },
  plateChip: {
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: Radius.full,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
  },
  plateText: {
    fontSize: Typography.xs,
    color: Colors.white,
    fontWeight: '700',
  },
  section: {
    padding: Spacing.lg,
  },
  sectionTitle: {
    fontSize: Typography.base,
    fontWeight: '700',
    color: Colors.gray900,
    marginBottom: Spacing.md,
  },
  specsGrid: {
    backgroundColor: Colors.white,
    borderRadius: Radius.xl,
    paddingHorizontal: Spacing.lg,
    ...Shadows.sm,
  },
  specRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: Spacing.md,
  },
  specRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: Colors.gray100,
  },
  specLabel: {
    fontSize: Typography.sm,
    color: Colors.gray500,
  },
  specValue: {
    fontSize: Typography.sm,
    fontWeight: '700',
    color: Colors.gray900,
    flexShrink: 1,
    textAlign: 'right',
  },
  emptyCard: {
    backgroundColor: Colors.white,
    margin: Spacing.lg,
    borderRadius: Radius.xl,
    padding: Spacing.xl,
    alignItems: 'center',
    gap: Spacing.sm,
    ...Shadows.sm,
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

export default AssignedVehicleScreen;
